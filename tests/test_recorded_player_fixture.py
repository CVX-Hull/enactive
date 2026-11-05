"""Original-image validation and actual stdio MCP evidence; no live game/provider."""
import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from PIL import Image
import pytest

from fixtures.recorded_player_mcp import load_packet, MAX_JSON_BYTES, MAX_PNG_BYTES
from harness.player_tools import tool_specs

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/recorded_player_mcp.py'


def make_packet(directory, count=3):
    (directory / 'sources').mkdir()
    sources, images = [], []
    for index in range(1, count + 1):
        image = BytesIO()
        Image.new('RGB', (index, 2), (index * 7, 11, 19)).save(image, format='PNG')
        png = image.getvalue()
        metadata = dict(schema='computer-source/1', source_id=f'{"a" * 32}-{index}',
                        session='a' * 32, capture_id=index, sha256=hashlib.sha256(png).hexdigest(),
                        media_type='image/png', presented_ms=1700 + index, received_wall=1234.5 + index,
                        width=index, height=2, window_width=40, window_height=20, viewport=[0, 0, index, 2])
        (directory / 'sources' / f'{metadata["source_id"]}.png').write_bytes(png)
        sources.append(metadata)
        images.append(png)
    packet = dict(current_source_id=sources[-1]['source_id'], sources=sources)
    path = directory / 'packet.json'
    path.write_text(json.dumps(packet))
    return path, packet, images


def sample(schema):
    """A minimal schema-valid proposal, never a live service invocation."""
    if 'const' in schema:
        return schema['const']
    if 'enum' in schema:
        return schema['enum'][0]
    for union in ('anyOf', 'oneOf'):
        if union in schema:
            return sample(schema[union][0])
    kind = schema.get('type')
    if kind == 'object':
        return {key: sample(schema['properties'][key]) for key in schema.get('required', [])}
    if kind == 'array':
        return [sample(schema['items']) for _ in range(schema.get('minItems', 0))]
    if kind == 'string':
        return 'x' * max(1, schema.get('minLength', 1))
    if kind in ('integer', 'number'):
        return schema.get('minimum', 1)
    if kind == 'boolean':
        return False
    return None


def test_stdio_current_schemas_exact_original_pairs_and_all_other_tools_refused(tmp_path):
    path, packet, images = make_packet(tmp_path)
    log, pid = tmp_path / 'calls.jsonl', tmp_path / 'pid'

    async def exercise():
        params = StdioServerParameters(command=sys.executable, args=[str(FIXTURE), '--packet', str(path),
            '--log', str(log), '--pid', str(pid)], cwd=str(tmp_path),
            env={'PATH': os.environ['PATH'], 'RECORDED_PLAYER_TEST_SENTINEL': 'harmless-presence-test'})
        with anyio.fail_after(15):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    initialized = await client.initialize()
                    assert 'Offline recorded-screen' in initialized.instructions
                    listed = await client.list_tools()
                    assert {tool.name: (tool.description, tool.input_schema) for tool in listed.tools} == tool_specs()
                    assert all(tool.name != 'player_finish' for tool in listed.tools)
                    observed = await client.call_tool('computer_observe', {})
                    assert not observed.is_error
                    assert json.loads(observed.content[0].text)['current_source_id'] == packet['current_source_id']
                    for index, metadata in enumerate(packet['sources']):
                        label = json.loads(observed.content[1 + index * 2].text)
                        assert label == dict(historical=True, selected_current=index == 2, source=metadata)
                        assert base64.b64decode(observed.content[2 + index * 2].data) == images[index]
                        exact = await client.call_tool('player_source', {'source_id': metadata['source_id']})
                        assert not exact.is_error
                        assert json.loads(exact.content[1].text)['source'] == metadata
                        assert base64.b64decode(exact.content[2].data) == images[index]
                    for name, (_, schema) in tool_specs().items():
                        if name not in ('computer_observe', 'player_source'):
                            refused = await client.call_tool(name, sample(schema))
                            assert refused.is_error, name
                            assert 'Proposal refused' in refused.content[0].text
                            assert len(refused.content) == 1
                    for name, args in [('unknown', {}), ('computer_observe', {'extra': True}),
                                       ('player_source', {}), ('player_source', {'source_id': 'absent'}),
                                       ('computer_input', {'actions': 'not a list'})]:
                        assert (await client.call_tool(name, args)).is_error

    anyio.run(exercise)
    child = int(pid.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls[0] == dict(event='startup', test_sentinel_inherited=True)
    assert 'harmless-presence-test' not in log.read_text()
    proposed = [call for call in calls[1:] if call['proposal']]
    assert all(call['refusal'] and not call['read'] for call in proposed)
    assert {call['name'] for call in proposed} >= set(tool_specs()) - {'computer_observe', 'player_source'}
    assert len([call for call in calls[1:] if call['read']]) == 4
    assert all(set(call) == {'name', 'arguments', 'proposal', 'refusal', 'read'} for call in calls[1:])


@pytest.mark.parametrize('fault', ['extra', 'duplicate', 'current', 'empty', 'too-many', 'old-schema',
    'id', 'clock', 'hash', 'dimensions', 'not-png', 'truncated', 'missing-image', 'image-symlink',
    'directory-symlink', 'packet-symlink', 'missing-packet', 'json-bound', 'png-bound', 'total-png-bound'])
def test_invalid_or_forged_packet_never_serves(tmp_path, fault):
    path, packet, images = make_packet(tmp_path)
    metadata = packet['sources'][0]
    image = tmp_path / 'sources' / f'{metadata["source_id"]}.png'
    if fault == 'extra':
        packet['extra'] = True
    elif fault == 'duplicate':
        packet['sources'].append(deepcopy(metadata))
    elif fault == 'current':
        packet['current_source_id'] = 'absent'
    elif fault == 'empty':
        packet['sources'] = []
    elif fault == 'too-many':
        packet['sources'] = [metadata] * 31
    elif fault == 'old-schema':
        metadata['schema'] = 'computer-source/0'
    elif fault == 'id':
        metadata['source_id'] = '../escape'
    elif fault == 'clock':
        metadata['presented_ms'] = 0
    elif fault == 'hash':
        metadata['sha256'] = '0' * 64
    elif fault == 'dimensions':
        metadata['width'] = 2
    elif fault in ('not-png', 'truncated'):
        png = b'not a PNG' if fault == 'not-png' else images[0][:-20]
        image.write_bytes(png)
        metadata['sha256'] = hashlib.sha256(png).hexdigest()
    elif fault == 'missing-image':
        image.unlink()
    elif fault == 'image-symlink':
        original = tmp_path / 'outside.png'
        image.rename(original)
        image.symlink_to(original)
    elif fault == 'directory-symlink':
        directory = tmp_path / 'sources'
        directory.rename(tmp_path / 'outside')
        directory.symlink_to(tmp_path / 'outside', target_is_directory=True)
    elif fault == 'png-bound':
        with image.open('r+b') as stream:
            stream.truncate(MAX_PNG_BYTES + 1)
    elif fault == 'total-png-bound':
        # Valid first PNG plus legal trailing bytes consumes all but one byte.
        padded = images[0] + b'\0' * (MAX_PNG_BYTES - len(images[0]) - 1)
        image.write_bytes(padded)
        metadata['sha256'] = hashlib.sha256(padded).hexdigest()
    path.write_text(json.dumps(packet))
    if fault == 'packet-symlink':
        path.rename(tmp_path / 'original.json')
        path.symlink_to(tmp_path / 'original.json')
    elif fault == 'missing-packet':
        path.unlink()
    elif fault == 'json-bound':
        path.write_bytes(b' ' * (MAX_JSON_BYTES + 1))
    with pytest.raises((ValueError, OSError, SyntaxError)):
        load_packet(path)


@pytest.mark.parametrize('encoded', [b'{"sources":[],"sources":[],"current_source_id":"x"}',
                                   b'{"sources":[],"current_source_id":NaN}'])
def test_packet_uses_current_strict_json_decoder(tmp_path, encoded):
    path = tmp_path / 'packet.json'
    path.write_bytes(encoded)
    with pytest.raises(ValueError):
        load_packet(path)


def test_fixture_has_no_live_service_imports():
    script = '''import runpy, sys, json
runpy.run_path(sys.argv[1])
print(json.dumps(sorted(sys.modules)))
'''
    result = subprocess.run([sys.executable, '-c', script, str(FIXTURE)], check=True,
                            capture_output=True, text=True, timeout=15)
    modules = set(json.loads(result.stdout))
    assert not modules & {'harness.player_client', 'harness.application', 'harness.computer.runtime',
                          'harness.computer.channel', 'harness.player.memory', 'harness.player.programs'}
