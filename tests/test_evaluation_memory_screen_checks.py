"""The memory screen's free checks on fixtures built here: a knowledge repository, a two-run lineage and the cut (#590)."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from harness.curator.knowledge import Repository
from tools.memory_screen_checks import (CutModel, StoreError, covered_turns, cut_report, fact_history, main,
    read_lineage, read_versions, replay, simulate, store_report)

SESSION = 'c' * 32
RECORD = '5' * 32
BASE = 4_000_000_000.0


def fact(identity: str, statement: str, version: str, session: str, citations: list[str]) -> dict:
    return dict(schema='curator-fact/1', id=identity, type='resource', statement=statement, scope=dict(game='cdda'),
        citations=citations, published_in=version, session=session)


def lines(*facts: dict) -> bytes:
    return ''.join(json.dumps(item) + '\n' for item in facts).encode()


def knowledge(root: Path, tank_frame: str) -> Path:
    """A repository at v2: v1 holds a recipe, v2 rewrites it and adds the tank. The first session read `run-a`."""
    repository = Repository(root, 'cdda')
    repository.ensure()
    recipe = fact('rod-recipe', 'A rod needs a stick.', 'v1', 'run-a-1', ['x-1'])
    repository.commit({'facts.jsonl': lines(recipe)}, 'Publish v1')
    repository.commit({'facts.jsonl': lines(dict(recipe, statement='A rod needs a stick and a hook.'),
        fact('roof-tank', 'The roof tank holds 18 L of clean water.', 'v2', 'run-a-2', [tank_frame]))}, 'Publish v2')
    for session in ('run-a-1', 'run-a-2'):
        directory = repository.state / 'sessions' / session
        directory.mkdir(parents=True)
        (directory / 'manifest.json').write_text(json.dumps(dict(inputs=dict(trace_sessions=['run-a']))))
    return repository.path


class Trace:
    """One actor's host trace: each request makes one call, one second apart; an input returns a frame and an image."""

    def __init__(self, actor: str, start: float) -> None:
        self.actor, self.wall, self.requests, self.images, self.omitted = actor, start, 0, 0, 0
        self.events = [dict(type='host-start', schema='player-host/4', telemetry_version=4, session=SESSION,
            actor_id=actor, wall_time=self.iso(), monotonic_ms=0)]

    def iso(self) -> str:
        return datetime.fromtimestamp(self.wall, timezone.utc).isoformat()

    def call(self, tool: str, arguments: dict, result: dict, *, write: int = 1000) -> None:
        self.requests += 1
        self.wall += 1
        common = dict(wall_time=self.iso(), monotonic_ms=self.requests * 1000.0, request_id=f'request-{self.requests}')
        usage = dict(input=3, output=20, cacheRead=5000 * self.requests, cacheWrite=write, cost=dict(total=0.01, cacheWrite=0.001))
        self.events += [dict(common, type='context-image-projection', input_images=self.images, omitted_images=self.omitted),
            dict(common, type='request-start', logical_request_id=common['request_id']),
            dict(common, type='response-complete', stop_reason='toolUse', usage_available=True, usage=usage),
            dict(common, type='tool-start', tool_call_id='call', tool=tool, arguments=arguments),
            dict(common, type='tool-result', tool_call_id='call', tool=tool,
                result=dict(content=[dict(type='text', text=json.dumps(result))], isError=False))]

    def press(self) -> str:
        frame = f'{self.actor[:4]}-{self.requests + 1}'
        self.call('computer_input', dict(actions=[dict(type='key', key='e', modifiers=[])]),
            dict(operation_id=f'{len(self.events):032x}', source=dict(source_id=frame)))
        self.images += 1
        return frame

    def write(self, directory: Path) -> None:
        directory.mkdir(parents=True)
        (directory / 'host.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in self.events))


def lineage(root: Path) -> tuple[list[Path], str, str]:
    """`run-a`: a first actor presses twice (the second frame shows the tank), writes a record and hands off; its
    successor presses three times. `run-b`: one actor presses four times; its third frame is where the fact is needed."""
    first, second, third = Trace('a' * 32, BASE), Trace('b' * 32, BASE + 100), Trace('d' * 32, BASE + 200)
    first.press()
    tank = first.press()
    first.call('player_memory_append', dict(record={}), dict(id=RECORD, kind='work'))
    first.call('player_handoff', dict(ids=[], summary='x'), dict(kind='handoff'))
    for _ in range(3):
        second.press()
    frames = [third.press() for _ in range(4)]
    first.write(root / 'run-a' / 'actors' / '001')
    second.write(root / 'run-a' / 'actors' / '002')
    third.write(root / 'run-b' / 'actors' / '001')
    return [root / 'run-a', root / 'run-b'], tank, frames[2]


def test_store_reads_each_version_and_changes_nothing(tmp_path):
    repository = knowledge(tmp_path / 'knowledge', 'aaaa-2')
    before = sorted((str(path), path.stat().st_mtime_ns) for path in repository.rglob('*'))
    versions = read_versions(repository)
    assert [(v['version'], len(v['facts']), v['bytes']) for v in versions] == [('v0', 0, 0),
        ('v1', 1, len(lines(fact('rod-recipe', 'A rod needs a stick.', 'v1', 'run-a-1', ['x-1'])))), ('v2', 2, versions[2]['bytes'])]
    history = fact_history(versions, 'rod-recipe')
    assert (history['version'], history['changed_in'], history['dropped_in']) == ('v1', ['v2'], None)
    assert history['statement'] == 'A rod needs a stick.' and history['latest_statement'].endswith('a hook.')
    assert fact_history(versions, 'cupboard') is None
    report, = store_report([repository], ['tank=tank|roof', 'rations=ration'], [])
    assert [(row['version'], row['covers'], row['added'], row['changed']) for row in report['versions'][1:]] == [
        ('v1', ['run-a'], 1, []), ('v2', ['run-a'], 1, ['rod-recipe'])]
    assert [found['id'] for found in report['found']['tank']] == ['roof-tank'] and report['found']['rations'] == []
    assert before == sorted((str(path), path.stat().st_mtime_ns) for path in repository.rglob('*'))
    (repository / '.git' / 'refs' / 'tags' / 'v3').write_text('0' * 40 + '\n')
    with pytest.raises(StoreError, match='not a loose object'):  # as a packed repository would be
        read_versions(repository)


def test_replay_places_the_need_the_record_and_the_fact(tmp_path):
    runs, tank, need = lineage(tmp_path)
    repository = knowledge(tmp_path / 'knowledge', tank)
    _, actors = read_lineage(runs)
    assert [(a.run, a.name, a.first, a.requests, a.successor) for a in actors] == [('run-a', '001', 1, 4, False),
        ('run-a', '002', 5, 3, True), ('run-b', '001', 8, 4, False)]
    row, = replay(runs, [f'tank:need={need},record=5555,fact=roof-tank'], None, repository, [1, 47])
    assert (row['need']['run'], row['need']['request'], row['need']['lineage_request']) == ('run-b', 3, 10)
    record = row['record']
    assert (record['written']['lineage_request'], record['first_briefing']['lineage_request']) == (3, 5)
    assert (record['briefing_to_needing_actor']['lineage_request'], record['requests_before_need']) == (8, 2)
    assert record['recorded'] is None  # no read or handoff gave it to an actor from the needing one on
    entry = row['fact']
    assert (entry['version'], entry['covers'], entry['first_cited']['lineage_request']) == ('v2', ['run-a'], 2)
    assert entry['at_admission_boundaries']['lineage_request'] == 8 and entry['boundary_before_need']
    assert [(e['lag'], e['lineage_request']) for e in entry['with_handoff_sessions']] == [(1, 6), (47, 7)]
    with pytest.raises(ValueError, match='not returned by any call'):
        replay(runs, ['x:need=nope-1'], None, None, [])


def test_cut_frees_only_covered_turns():
    images = list(range(60))  # every turn carries one image
    model = CutModel()
    plain = simulate(images, model, None)
    assert [plain[i]['prompt'] for i in (0, 1, 39)] == [4500, 5450, 4500 + 39 * 950]
    assert [plain[i]['write'] for i in (0, 1)] == [4500, 950]
    assert [i for i, row in enumerate(plain) if row['image_drop']] == [40]  # the 40th image: a block of 20 goes
    assert plain[40] == dict(prompt=42500 - 20 * 658, freed=None, image_drop=True, write=42500 - 20 * 658 - 3900)
    kept_up = simulate(images, model, 10)
    assert kept_up[40] == dict(prompt=42500 - 24 * 950, freed=24, image_drop=False, write=42500 - 24 * 950 - 3900)
    assert not any(row['image_drop'] for row in kept_up)
    behind = simulate(images, model, 47)
    assert (behind[40]['freed'], behind[40]['image_drop'], behind[40]['prompt']) == (0, True, plain[40]['prompt'])
    assert simulate(images, CutModel(min_free=30), 10)[40]['freed'] == 0  # a cut that would free too little is not made
    assert (covered_turns(45, 10, 'steady'), covered_turns(45, 10, 'sessions'), covered_turns(5, 10, 'sessions')) == (35, 30, 0)


def test_cut_report_and_the_command(tmp_path, capsys):
    runs, tank, need = lineage(tmp_path)
    report = cut_report(runs, CutModel(), [10])
    recorded, plain, lagged = report['rows']
    assert (recorded['row'], recorded['requests'], recorded['cache_write'], recorded['image_drops']) == ('recorded', 11, 11000, 0)
    assert recorded['prompt_max'] == 3 + 5000 * 4 + 1000
    assert (plain['row'], plain['requests'], plain['prompt_max'], plain['cuts']) == ('no cut', 11, 4500 + 3 * 950, 0)
    first_actor = simulate([0, 1, 2, 2], CutModel(), None)  # two frames, then a call that returns no image
    assert [row['prompt'] for row in first_actor] == [4500, 5450, 6400, 6400 + 192]
    assert lagged == dict(plain, row='lag 10')  # nothing reaches a mark in so short a lineage
    repository = knowledge(tmp_path / 'knowledge', tank)
    assert main(['store', str(repository), '--find', 'tank=tank', '--runs', str(tmp_path / 'run-a')]) == 0
    assert 'roof-tank (resource) first in v2 by run-a-2' in capsys.readouterr().out
    assert main(['replay', *map(str, runs), '--loss', f'tank:need={need},fact=roof-tank', '--knowledge', str(repository)]) == 0
    assert 'sessions at admission boundaries only: briefing at run-b/001 request 1 of 4' in capsys.readouterr().out
    assert main(['cut', *map(str, runs), '--lags', '10', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['model']['turn_tokens'] == 950
