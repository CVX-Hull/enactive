"""Real file/MCP boundary fixtures for #181; no native or gameplay claims."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid

from mcp import Client

from experiments.computer_control.client import ComputerClient, OperationExpired, atomic
from experiments.computer_control.mcp import make_server
from experiments.computer_control.protocol import (ControlError, MAX_FRAME_BYTES, read_json,
    receipt, state, validate_input)
from experiments.computer_control.run import prepared_launch
from experiments.computer_control import run as custodian
from harness.prepared_app import wrapper_source
from tests.test_gameplay_evidence import png


class ComputerControlTests(unittest.TestCase):
    def setUp(self):
        owned = tempfile.TemporaryDirectory()
        self.addCleanup(owned.cleanup)
        self.run = Path(owned.name)
        self.bridge = self.run / 'bridge'
        self.bridge.mkdir(mode=0o700)
        (self.bridge / 'receipts').mkdir()
        (self.run / 'operations').mkdir()
        self.session = uuid.uuid4().hex
        self.config = dict(schema='computer-run/1', session=self.session, pid=321,
            deadline_monotonic=time.monotonic() + 60, max_inputs=32, max_requests=32,
            max_frames=32, max_bytes=1024**3)
        atomic(self.run / 'control.json', self.config)
        self.frame = dict(name='frame-1.png', capture_id=1, presented_ms=1000, width=640,
            height=400, window_width=640, window_height=400, viewport=[0, 0, 640, 400])
        (self.bridge / 'frame-1.png').write_bytes(png(b'owned fixture pixels'))
        self.target = dict(schema='computer-target/1', session=self.session, pid=321, window_id=1,
            paused=False, takeover_generation=0, latest_frame=self.frame, error='')
        atomic(self.bridge / 'state.json', self.target)
        self.calls = []
        self.mode = 'delivered'
        self.stop_native = threading.Event()
        self.native = threading.Thread(target=self.producer, daemon=True)
        self.native.start()
        self.addCleanup(lambda: (self.stop_native.set(), self.native.join(2)))
        self.client = ComputerClient(self.run)
        self.addCleanup(self.client.close)

    def producer(self):
        while not self.stop_native.wait(.002):
            path = self.bridge / 'request.json'
            if not path.exists():
                continue
            claimed = self.bridge / 'claimed.json'
            try:
                path.rename(claimed)
            except FileNotFoundError:
                continue
            request = read_json(claimed)
            self.calls.append(request)
            mode = self.mode if request['kind'] == 'input' else 'delivered'
            if mode == 'lost':
                continue
            value = dict(schema='computer-receipt/1', id=request['id'], session=request['session'],
                disposition='delivered' if mode == 'handoff_delay' else mode, emitted_events=0 if request['kind'] == 'observe' or mode == 'rejected' else 1,
                reason='Synthetic file producer; no application effect assertion',
                frame=self.frame if request['kind'] == 'observe' else None)
            atomic(self.bridge / 'receipts' / (request['id'] + '.json'), value)
            if mode == 'handoff_delay':
                time.sleep(.05)
            claimed.unlink()

    def key(self):
        return dict(type='key', key='a', modifiers=[])

    def test_unknown_screen_needs_only_mechanical_target_and_input(self):
        value, image = self.client.execute([self.key(), dict(type='text', text='hé✓')])
        self.assertEqual(value['status'], 'completed', value)
        self.assertTrue(image.startswith(b'\x89PNG'))
        self.assertEqual([c['kind'] for c in self.calls], ['input', 'input', 'observe'])
        self.assertNotIn('scene', value['target'])
        self.assertNotIn('category', value['target'])
        self.assertEqual(self.client.inputs, 2)
        original_count = len(self.calls)
        collected, exact_image = self.client.result(value['operation_id'])
        self.assertEqual(collected, value)
        self.assertEqual(exact_image, image)
        self.assertEqual(len(self.calls), original_count)

    def test_validate_entire_sequence_before_first_publication(self):
        with self.assertRaises(ControlError):
            self.client.execute([self.key(), dict(type='navigate', target='shelter')])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.inputs, 0)

    def test_pointer_requires_returned_capture_and_original_geometry(self):
        action = dict(type='click', x=200, y=180, button='left')
        with self.assertRaises(ControlError):
            self.client.execute([action], capture_id=1)
        value, _ = self.client.execute(observe=True)
        original = deepcopy(value['capture'])
        value, _ = self.client.execute([action], capture_id=1)
        self.assertEqual(value['status'], 'completed')
        published = next(c for c in self.calls if c['kind'] == 'input')['input']
        self.assertEqual(published['geometry'], {k: original[k] for k in ('width', 'height', 'window_width', 'window_height', 'viewport')})
        self.assertEqual(action, dict(type='click', x=200, y=180, button='left'))

    def test_partial_delivery_stops_sequence_and_permanently_fences_input(self):
        self.mode = 'partial'
        value, _ = self.client.execute([self.key(), self.key()])
        self.assertEqual(value['status'], 'unknown', value)
        self.assertEqual(len([c for c in self.calls if c['kind'] == 'input']), 1)
        self.assertTrue((self.bridge / 'pause').exists())
        with self.assertRaises(ControlError):
            self.client.execute([self.key()])
        self.client.result(value['operation_id'])
        self.assertEqual(len([c for c in self.calls if c['kind'] == 'input']), 1)

    def test_missing_ack_is_local_unknown_not_fabricated_native_receipt_or_zero_effect(self):
        self.mode = 'lost'
        value = self.client._send('input', self.key(), time.monotonic() + .05)
        self.assertEqual(value['schema'], 'computer-transport/1')
        self.assertEqual(value['disposition'], 'unknown')
        self.assertIsNone(value['emitted_events'])
        self.assertTrue((self.bridge / 'pause').exists())
        with self.assertRaises(ControlError):
            self.client.execute([self.key()])

    def test_known_rejection_does_not_destroy_healthy_control(self):
        self.mode = 'rejected'
        value, _ = self.client.execute([self.key()])
        self.assertEqual(value['status'], 'refused')
        self.assertFalse((self.bridge / 'pause').exists())
        self.mode = 'delivered'
        value, _ = self.client.execute([self.key()])
        self.assertEqual(value['status'], 'completed')

    def test_original_capacity_and_clock_do_not_reset_on_new_decision(self):
        self.client.config['max_inputs'] = 1
        self.client.execute([self.key()])
        with self.assertRaisesRegex(ControlError, 'remaining original input'):
            self.client.execute([self.key()])
        self.client.deadline = time.monotonic() - 1
        with self.assertRaisesRegex(ControlError, 'Original deadline'):
            self.client.execute(observe=True)
        self.assertEqual(len([c for c in self.calls if c['kind'] == 'input']), 1)

    def test_capture_reserves_bytes_before_native_publication(self):
        self.client.config['max_bytes'] = MAX_FRAME_BYTES - 1
        with self.assertRaisesRegex(ControlError, 'capture reservation'):
            self.client._send('observe', None, time.monotonic() + 1)
        self.assertEqual(self.calls, [])

    def test_retained_capture_corruption_stops_without_more_input(self):
        self.client.execute(observe=True)
        (self.bridge / 'frame-1.png').write_bytes(png(b'changed immutable pixels'))
        with self.assertRaisesRegex(ControlError, 'Immutable capture'):
            self.client._frame(self.frame)
        self.assertTrue((self.bridge / 'pause').exists())
        with self.assertRaises(ControlError):
            self.client.execute([self.key()])

    def test_terminal_ack_waits_for_native_handoff_without_false_unknown(self):
        self.mode = 'handoff_delay'
        result, _ = self.client.execute([self.key(), self.key()])
        self.assertEqual(result['status'], 'completed', result)
        self.assertFalse((self.bridge / 'pause').exists())

    def test_waits_that_cannot_finish_are_not_reported_complete(self):
        with self.assertRaisesRegex(ControlError, 'Sequence waits'):
            self.client.execute([dict(type='wait', seconds=2)] * 32)
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(OperationExpired, 'does not fit'):
            self.client._wait(2, time.monotonic() + .01)
        self.assertFalse((self.bridge / 'pause').exists())

    def test_target_integrity_failure_cannot_rearm_after_a_new_read(self):
        atomic(self.bridge / 'state.json', self.target | dict(session='wrong-target'))
        with self.assertRaises(ControlError):
            self.client.execute([self.key()])
        self.assertTrue((self.bridge / 'pause').exists())
        atomic(self.bridge / 'state.json', self.target)
        with self.assertRaises(ControlError):
            self.client.execute([self.key()])
        self.assertEqual(self.calls, [])

    def test_restart_cannot_recover_authority_or_renew_counters(self):
        with self.assertRaises((FileExistsError, BlockingIOError)):
            ComputerClient(self.run)
        self.client.close()
        with self.assertRaises(FileExistsError):
            ComputerClient(self.run)

    def test_protocol_rejects_game_semantics_extra_fields_bad_receipts_and_duplicate_json(self):
        for value in (self.target | dict(category='INVENTORY'), self.target | dict(session='different')):
            with self.assertRaises(ControlError):
                state(value, session=self.session, pid=321)
        bad = dict(schema='computer-receipt/1', id='x', session=self.session, disposition='rejected',
                   emitted_events=1, reason='wrong', frame=None)
        with self.assertRaises(ControlError):
            receipt(bad, identity='x', session=self.session)
        (self.run / 'bad.json').write_text('{"id":1,"id":2}')
        with self.assertRaises(ControlError):
            read_json(self.run / 'bad.json')
        for value in (dict(type='text', text='x'*32), self.key() | dict(menu='x'),
                      dict(type='text', text='\n'), dict(type='key', key='F99', modifiers=[])):
            with self.assertRaises(ControlError):
                validate_input(value)

    def test_derived_launch_preserves_prepared_paths_without_old_bridge(self):
        source = prepared_launch()
        self.assertIn('unset CDDA_HARNESS_DIR', source)
        self.assertNotIn('export CDDA_HARNESS_DIR=', source)
        self.assertIn('SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN=1', source)
        baseline = wrapper_source(Path(__file__).resolve().parents[1])
        self.assertEqual([x for x in baseline.splitlines() if not x.startswith('export CDDA_HARNESS_DIR=')],
                         [x for x in source.splitlines() if x != 'unset CDDA_HARNESS_DIR'
                          and not x.startswith('export DYLD_INSERT_LIBRARIES=')])

    def test_mcp_cancellation_latches_pause_before_native_collection_is_abandoned(self):
        self.mode = 'lost'
        async def exercise():
            async with Client(make_server(self.client)) as client:
                call = asyncio.create_task(client.call_tool('computer_input', {'actions': [self.key()]}))
                end = time.monotonic() + 2
                while not self.calls and time.monotonic() < end:
                    await asyncio.sleep(.005)
                self.assertTrue(self.calls)
                call.cancel()
                try:
                    await call
                except asyncio.CancelledError:
                    pass
                end = time.monotonic() + 2
                while not (self.bridge / 'pause').exists() and time.monotonic() < end:
                    await asyncio.sleep(.005)
                self.assertTrue((self.bridge / 'pause').exists())
                self.assertEqual(len(self.calls), 1)
        asyncio.run(exercise())

    def test_pause_and_receipt_storage_failures_do_not_skip_owned_cleanup(self):
        case = self.run / 'cleanup-case'
        case.mkdir()
        (case / 'prompt.txt').write_text('fixture')
        (self.run / '.runtime/bridge').mkdir(parents=True)
        profile = dict(library={'path': '/fixture/library'}, session=self.session, source_commit='fixture',
                       wall_seconds=60, host_seconds=20, port=9876, node='/fixture/node', effort='medium',
                       limits={k: self.config[k] for k in ('max_inputs', 'max_requests', 'max_frames', 'max_bytes')})
        class Child:
            def __init__(self, pid, code):
                self.pid, self.returncode, self.signals = pid, code, []
            def poll(self): return self.returncode
            def send_signal(self, sig): self.signals.append(sig)
            def wait(self, timeout): self.returncode = 0; return 0
        game, host = Child(111, None), Child(222, 0)
        def launch(*args, **kwargs):
            if not (case / 'bridge/state.json').exists():
                atomic(case / 'bridge/state.json', self.target | dict(pid=111))
                return game
            return host
        original_touch, original_atomic = Path.touch, custodian.atomic
        def fail_pause(path, *args, **kwargs):
            if path == case / 'bridge/pause': raise OSError('injected Pause storage failure')
            return original_touch(path, *args, **kwargs)
        def fail_receipt(path, value):
            if path == case / 'receipt.json': raise OSError('injected receipt storage failure')
            return original_atomic(path, value)
        with patch.object(custodian, 'ROOT', self.run), patch.object(custodian, 'preflight',
                return_value=(profile, {'model': {'id': 'fixture'}})), patch.object(custodian.subprocess,
                'Popen', side_effect=launch), patch.object(custodian, 'serve', return_value=(None, None)), \
                patch.object(Path, 'touch', fail_pause), patch.object(custodian, 'atomic', fail_receipt), \
                patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fixture-only'}):
            result = custodian.run_proof(case)
        self.assertEqual(result['pause_error'], 'OSError')
        self.assertEqual(result['receipt_error'], 'OSError')
        self.assertTrue(result['native_absence_verified'])
        self.assertTrue(result['deciding_host_quiescent'])
        self.assertTrue(result['input_authority_revoked'])
        self.assertEqual(game.returncode, 0)
        self.assertEqual(len(game.signals), 1)

    def test_correctable_local_mcp_argument_refusal_preserves_basic_control(self):
        async def exercise():
            async with Client(make_server(self.client)) as client:
                refused = await client.call_tool('computer_input', {'actions': [dict(type='key', key='F99', modifiers=[])]})
                self.assertTrue(refused.is_error)
                self.assertFalse((self.bridge / 'pause').exists())
                corrected = await client.call_tool('computer_input', {'actions': [self.key()]})
                self.assertFalse(corrected.is_error)
                self.assertEqual(json.loads(corrected.content[0].text)['status'], 'completed')
        asyncio.run(exercise())

    def test_actual_mcp_tools_return_one_json_and_typed_pixels(self):
        async def exercise():
            async with Client(make_server(self.client)) as client:
                tools = await client.list_tools()
                names = {x.name for x in tools.tools}
                self.assertEqual(names, {'computer_observe', 'computer_input', 'computer_result', 'computer_stop'})
                result = await client.call_tool('computer_observe', {})
                self.assertFalse(result.is_error)
                self.assertIsNone(result.structured_content)
                self.assertEqual([c.type for c in result.content], ['text', 'image'])
                value = json.loads(result.content[0].text)
                self.assertEqual(value['capture']['capture_id'], 1)
        asyncio.run(exercise())
