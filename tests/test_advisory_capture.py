"""Current advisory provenance stays distinct from current input observations."""
from copy import deepcopy
import hashlib
import json
import unittest

from harness.gameplay.advisory_capture import (
    capture_projection, source_envelope, validate_capture, validate_captured_mapping, validate_source,
)
from harness.gameplay.contracts import ContractError, EvidenceRef, canonical
from harness.gameplay.evidence import _identity, _validate_observation
from harness.gameplay.mission_requests import _source_binding
from harness.gameplay.native_receipts import validate_ordinary_mapping
from tests.test_gameplay_evidence import observation, png
from tests.test_mission_ledger import intent, known_receipt


def historical_source():
    original = observation()
    original['protocol'] = 6
    original.update(category='UILIST', scene=None, ui={
        'purpose': 'UILIST', 'title': 'Original menu',
        'rows': [{'id': 'row-1', 'text': 'knife', 'enabled': True, 'hotkey': 'a'}],
        'selected': 'row-1', 'filter': None, 'count': None, 'coverage': 'rendered_rows_only'})
    original['boundary']['kind'] = 'menu'
    sid = _identity(original)
    ref = EvidenceRef(sid, original['session'], original['revision'], original['timestamp_ms'],
        100.0, None, '/original/project/evidence/' + sid + '.png', hashlib.sha256(png()).hexdigest(), 'menu')
    origin = dict(ledger_sha256='a' * 64, index_sha256='b' * 64, native_protocol=6,
                  store_version=5, program_view='program-view/1')
    return original, source_envelope('old-mission', origin, ref.to_dict(), original)


def historical_receipt(proposed=None):
    value = known_receipt(proposed=proposed)
    request = json.loads(value['native_request_json'])
    request['protocol'] = 6
    value['native_request_json'] = canonical(request)
    value['native_ack']['protocol'] = 6
    return value


class AdvisoryCaptureTests(unittest.TestCase):
    def test_historical_ui_is_preserved_without_marker_invention_or_input_binding(self):
        original, source = historical_source()
        self.assertEqual(source['capture']['original_ui'], original['ui'])
        self.assertNotIn('rendered_marker', source['capture']['original_ui']['rows'][0])
        self.assertNotIn('observation', source)
        self.assertFalse(source['grants_authority'])
        self.assertEqual(validate_source(source, mission_id='old-mission',
            source_id=source['reference']['observation_id']), source)
        source['capture']['original_ui']['title'] = 'changed copy'
        self.assertEqual(original['ui']['title'], 'Original menu')
        for value in (original, source):
            with self.subTest(value=value), self.assertRaises(ContractError):
                _validate_observation(value)
        for value in (source, {'reference': source['reference'], 'observation': original}):
            with self.subTest(value=value), self.assertRaises(ContractError):
                _source_binding(value)

    def test_semantic_capture_corruption_and_cross_mission_reference_refuse(self):
        _, source = historical_source()
        changes = [lambda s: s.update(mission_id='foreign'),
            lambda s: s.update(grants_authority=True),
            lambda s: s['origin'].update(store_version=6),
            lambda s: s['reference'].update(revision=99),
            lambda s: s['capture'].update(original_protocol=6.0),
            lambda s: s['capture'].update(original_protocol=5),
            lambda s: s['capture'].update(frame_ok=False),
            lambda s: s['capture'].update(frame='frame-foreign-2.png'),
            lambda s: s['capture']['boundary'].update(kind='unsupported', input_receiver=True),
            lambda s: s.update(extra=True)]
        for change in changes:
            invalid = deepcopy(source)
            change(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(ContractError):
                validate_source(invalid, mission_id='old-mission')
        current = observation()
        current['scene']['neighbors'][0]['dx'] = 9
        with self.assertRaises(ContractError):
            capture_projection(current)
        with self.assertRaises(ContractError):
            validate_capture(observation())

    def validate(self, value, proposed=None, disposition='returned'):
        return validate_captured_mapping(proposed or intent(), value, logical_id='logical-1',
            native_id='native-uuid-1', disposition=disposition, protocol=6)

    def test_captured_delivery_uses_shared_correlations_and_stays_ineligible_as_native_wire(self):
        for kind, value in (('action', 'RIGHT'), ('key', 'ESC'),
                            ('direct', dict(type='text', text='é')), ('resume', None)):
            proposed = intent(kind=kind, value=value)
            receipt = historical_receipt(proposed)
            projected = self.validate(receipt, proposed)
            self.assertEqual(projected['ack']['original_protocol'], 6)
            self.assertNotIn('protocol', projected['ack'])
            with self.assertRaises(ContractError):
                validate_ordinary_mapping(proposed, receipt, logical_id='logical-1',
                                          native_id='native-uuid-1', disposition='returned')

    def test_semantic_receipt_corruption_refuses_even_without_any_outer_hash_comparison(self):
        changes = [lambda r: r.update(logical_action_id='wrong'), lambda r: r.update(published=False),
            lambda r: r.update(value='LEFT'), lambda r: r.update(source_before='wrong'),
            lambda r: r.update(transport_disposition='unknown'), lambda r: r.pop('processing_error'),
            lambda r: r.update(received_monotonic=True), lambda r: r.update(received_monotonic=float('inf')),
            lambda r: r['native_ack'].update(protocol=7), lambda r: r['native_ack'].update(id='wrong'),
            lambda r: r['native_ack'].update(status='rejected'), lambda r: r['native_ack'].update(revision=30),
            lambda r: r['native_ack'].update(session='foreign'), lambda r: r.update(source_after='unrelated'),
            lambda r: r.update(source_after=None, evidence_loss=None)]
        for change in changes:
            receipt = historical_receipt()
            change(receipt)
            with self.subTest(receipt=receipt), self.assertRaises(ContractError):
                self.validate(receipt)
        for change in (dict(id='wrong'), dict(session='foreign'), dict(revision=29),
                       dict(action='LEFT'), dict(protocol=7), dict(require_exact_frame=None)):
            receipt = historical_receipt()
            request = json.loads(receipt['native_request_json'])
            receipt['native_request_json'] = canonical(request | change)
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.validate(receipt)

    def test_unknown_ack_and_known_delivery_effects_stay_separate(self):
        self.assertIsNone(self.validate({'native_ack': None}, disposition='unknown'))
        for disposition in ('unknown', 'not_dispatched'):
            with self.assertRaises(ContractError):
                self.validate(historical_receipt(), disposition=disposition)
        receipt = historical_receipt()
        receipt.update(source_after=None, evidence_loss='original image retention failure')
        self.validate(receipt)
