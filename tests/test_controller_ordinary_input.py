"""Synthetic ordinary receiver and immutable delivery receipts; no native claim."""
import copy
import hashlib
import time
import unittest
from unittest.mock import patch

from harness.controller import ControlError, validate_state
from tests import test_controller as fixtures
from tests.test_controller import FakeBridge, state, frame_geometry


class OrdinaryControllerTests(unittest.TestCase):
    setUp = fixtures.ControllerTests.setUp
    ready = fixtures.ControllerTests.ready
    expect = fixtures.ControllerTests.expect
    acquire = fixtures.ControllerTests.acquire
    mission_dispatch = fixtures.ControllerTests.mission_dispatch

    def test_native_six_requires_boolean_receiver_and_rejects_five(self):
        validate_state(state())
        for receiver in (None, 1, "true"):
            value = state()
            value['boundary']['input_receiver'] = receiver
            with self.subTest(receiver=receiver), self.assertRaises(ControlError):
                validate_state(value)
        with self.assertRaises(ControlError):
            validate_state(state(protocol=5))

    def test_direct_key_follows_actual_preflight_drift_and_resize(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            lease = self.acquire(operation='interaction')
            expected = self.expect()
            fake.value.update(revision=11, category='UNFAMILIAR', scene=None,
                              frame_geometry=frame_geometry() | {'window_width': 2})
            fake.value['boundary'].update(kind='menu', id='new-menu')
            captured = []
            receipt = self.mission_dispatch(lease, kind='direct',
                value={'type': 'key', 'key': 'ESC', 'modifiers': []},
                **expected, preflight=lambda value, received: captured.append((value, received)))
            self.assertEqual(receipt['result']['status'], 'ready')
            self.assertFalse(receipt['request']['require_exact_frame'])
            self.assertEqual(receipt['request']['revision'], 11)
            self.assertEqual(receipt['request']['boundary_id'], 'new-menu')
            self.assertEqual(receipt['preflight']['observation'], captured[0][0])
            self.assertEqual(receipt['preflight']['informing']['expected_revision'], expected['expected_revision'])
            self.assertIs(self.controller._mission_lease, lease)

    def test_click_resize_refusal_retains_actual_preflight_and_lease(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            lease = self.acquire(operation='interaction')
            click = dict(type='click', button='left', x=0, y=0, geometry=frame_geometry())
            # A revised synthetic geometry, not native resize qualification.
            # Same-revision geometry contradictions remain separate negatives.
            fake.value['revision'] += 1
            fake.value['frame_geometry']['window_width'] = 2
            receipt = self.mission_dispatch(lease, kind='direct', value=click)
            self.assertEqual(receipt['result']['status'], 'rejected')
            self.assertFalse(receipt['published'])
            self.assertIsNone(receipt['request'])
            self.assertIsNone(receipt['processing_error'])
            self.assertEqual(receipt['preflight']['observation']['frame_geometry']['window_width'], 2)
            self.assertEqual(click['geometry']['window_width'], 1)
            self.assertIs(self.controller._mission_lease, lease)
            self.assertFalse(self.controller.pause_requested)

    def test_known_ack_survives_postprocessing_failures(self):
        for fault in ('journal', 'snapshot', 'unlink', 'receipt'):
            with self.subTest(fault=fault), FakeBridge(self.controller) as fake:
                self.ready()
                lease = self.acquire(operation='interaction')
                record, accept = self.controller._record, self.controller._accept
                from pathlib import Path
                unlink = Path.unlink
                failed_unlinks = []
                def fail_record(request, outcome):
                    if (fault == 'journal' and request.get('kind') == 'direct'
                            or fault == 'receipt' and request.get('kind') == 'mission_receipt'):
                        raise OSError('injected storage failure')
                    return record(request, outcome)
                def fail_accept(value, **kwargs):
                    if fault == 'snapshot' and value['status'] == 'ready' and value['revision'] > fake.requests[-1].get('revision', 10**9):
                        raise ControlError('injected snapshot failure')
                    return accept(value, **kwargs)
                def fail_unlink(path, *args, **kwargs):
                    if (fault == 'unlink' and path.parent == self.controller.admissions
                            and any(request['kind'] == 'direct' and path.name == f"{request['id']}.json"
                                    for request in fake.requests)):
                        failed_unlinks.append(path.name)
                        raise OSError('injected unlink failure')
                    return unlink(path, *args, **kwargs)
                with patch.object(self.controller, '_record', fail_record), patch.object(self.controller, '_accept', fail_accept), patch.object(Path, 'unlink', fail_unlink):
                    receipt = self.mission_dispatch(lease, kind='direct', value={'type': 'text', 'text': 'x'})
                self.assertEqual(receipt['result']['status'], 'ready')
                self.assertEqual(receipt['result']['id'], receipt['request']['id'])
                self.assertIsNotNone(receipt['received_monotonic'])
                self.assertIn('injected', receipt['processing_error'])
                self.assertEqual(self.controller.unknown_outcomes, [])
                self.assertTrue(self.controller.pause_requested)
                if fault == 'unlink':
                    self.assertEqual(failed_unlinks, [f"{receipt['request']['id']}.json"])

    def test_historical_ack_keeps_newer_same_revision_actual_current(self):
        self.historical_ack_current(timestamp_delta=1)

    def test_capture_counter_orders_current_and_ack_within_same_millisecond(self):
        self.historical_ack_current(timestamp_delta=0)

    def historical_ack_current(self, *, timestamp_delta):
        ack = state(id='ack-id', revision=5, frame='frame-game-test-10.png')
        self.controller._accept(ack)
        current = copy.deepcopy(ack)
        current.update(id='', frame='frame-game-test-11.png', timestamp_ms=ack['timestamp_ms'] + timestamp_delta)
        fixtures.atomic_json(self.controller.bridge / 'state.json', current)
        self.controller._accept(ack, historical=True)
        snapshot, received = self.controller.observation_snapshot()
        self.assertEqual(snapshot, current)
        # Rereading the old ACK neither rolls back nor renews current's clock.
        fixtures.atomic_json(self.controller.bridge / 'state.json', ack)
        self.controller._accept(ack, historical=True)
        self.assertEqual(self.controller.observation_snapshot(), (current, received))


if __name__ == '__main__':
    unittest.main()
