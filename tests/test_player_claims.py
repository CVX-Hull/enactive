"""Semantic adapter and real SDK staging with synthetic evidence, never native play."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest

from harness.gameplay.campaign_memory import CampaignMemory
from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.mission_contracts import validate_request
from harness.gameplay.mission_ledger import MissionLedger
from harness.mission_client import MissionClient, MissionClientError
from harness.player_tools import PlayerTools
from tests import test_campaign_memory as memory_fixture
from tests.test_mission_contracts import admission, claim, request
from tests.test_mission_request_producer import bundle, lifecycle, phase, skill, snapshot


class StagingClient(MissionClient):
    """Use the actual SDK stage/submit fence, with no network or game runtime."""
    def __init__(self, root):
        super().__init__(root)
        self.writes = []
        self.reads = []
        self.events = []

    def _json(self, path, *, data=None, **options):
        import json
        body = json.loads(data)
        if body['kind'] == 'result':
            self.reads.append(body)
            return dict(status='accepted', operation=None)
        self.writes.append(body)
        self.events.append('submit')
        return dict(status='accepted', operation=dict(request=body, state='completed', result=dict(status='ok')))

    def status(self):
        self.events.append('status')
        raise MissionClientError('No current synthetic status; binding must use the cache')

    def source(self, *args):
        raise AssertionError('Composition cannot fetch a replacement source')


class PlayerClaimTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / '.runtime').mkdir()
        self.client = StagingClient(self.root)
        self.player = PlayerTools(self.client)
        self.source = bundle(7)
        self.ref = self.source['reference']
        self.scope = dict(mission_id='mission-test', session=self.ref['session'], coordinate_epoch=4)
        self.selected = dict(snapshot_id='chosen', mission=snapshot(coordinate_scope=self.scope),
                             source=self.source, native={})
        self.player.snapshots['chosen'] = deepcopy(self.selected)
        self.player.sources[('mission-test', self.ref['observation_id'])] = deepcopy(self.source)

    def entry(self, **changes):
        value = dict(key=dict(property='supply', subject='water', unit='charges', coverage_id='page-1'),
            value=dict(quantity=18, state=None), text='Visible water count', coverage='menu page',
            status='last_seen', grounding=dict(kind='source', source_id=None, coordinate_epoch=None),
            supports=[dict(primary=True, sources=[], claims=[])])
        value.update(changes)
        return value

    def arguments(self, entry=None, identity='remember', **intent):
        return dict(snapshot_id='chosen', request_id=identity, wait_seconds=0,
            intent=dict(entry_type='claim', entry=self.entry() if entry is None else entry, **intent))

    def submit(self, entry=None, identity='remember', kind='remember', **intent):
        self.player.call('enactive_' + kind, self.arguments(entry, identity, **intent))
        return self.client.writes[-1]

    def test_expands_exact_native_order_scope_and_explicit_support_groups(self):
        alternate = bundle(3)
        additional = alternate['reference']['observation_id']
        self.player.sources[('mission-test', additional)] = alternate
        entry = self.entry(supports=[dict(primary=True, sources=[additional], claims=['premise']),
                                     dict(primary=False, sources=[additional], claims=[])])
        before = deepcopy(entry)
        lower = int(time.time() * 1000)
        result = self.submit(entry)
        upper = int(time.time() * 1000)
        expected = claim(id='claim-' + hashlib.sha256(b'remember').hexdigest(),
            key=entry['key'], value=entry['value'], text=entry['text'], coverage=entry['coverage'],
            scope=self.scope, observed_time=dict(revision=self.ref['revision'], turn=self.ref['turn']),
            received_time=result['entry']['received_time'], sources=[self.ref['observation_id'], additional],
            supports=[dict(sources=[self.ref['observation_id'], additional], claims=['premise']),
                      dict(sources=[additional], claims=[])])
        self.assertEqual(result, validate_request(request('remember', request_id='remember', epoch=3,
            entry_type='claim', entry=expected)))
        self.assertLessEqual(lower, expected['received_time'])
        self.assertLessEqual(expected['received_time'], upper)
        self.assertNotEqual(expected['received_time'], self.ref['timestamp_ms'])
        self.assertEqual(entry, before)

    def test_identity_keys_derive_reserved_constants(self):
        for subject, coverage in (('world', 'visible-world-menu'), ('character', 'visible-character-screen')):
            entry = self.entry(key=dict(property='identity', subject=subject), value=dict(quantity=None, state='Visible name'))
            result = self.submit(entry, identity=subject)['entry']
            self.assertEqual(result['key'], dict(property='identity', subject=subject, unit='name', coverage_id=coverage))
            self.assertEqual(result['kind'], 'interpretation')

    def test_unobserved_unknown_and_claim_only_premises_are_source_free(self):
        self.player.snapshots['chosen']['source'] = None
        self.player.sources.clear()
        for index, supports in enumerate(([], [dict(primary=False, sources=[], claims=['premise'])])):
            entry = self.entry(grounding=dict(kind='unobserved', session='unseen-session', coordinate_epoch=9),
                value=dict(quantity=None, state=None), status='unknown', supports=supports)
            result = self.submit(entry, identity='unknown-' + str(index))['entry']
            self.assertEqual(result['scope'], dict(mission_id='mission-test', session='unseen-session', coordinate_epoch=9))
            self.assertEqual(result['observed_time'], dict(revision=None, turn=None))
            self.assertEqual(result['sources'], [])
            self.assertEqual(result['supports'], [dict(sources=[], claims=['premise'])] if supports else [])

    def test_primary_false_does_not_infer_image_support(self):
        result = self.submit(self.entry(supports=[dict(primary=False, sources=[], claims=['premise'])]))['entry']
        self.assertEqual(result['sources'], [self.ref['observation_id']])
        self.assertEqual(result['supports'], [dict(sources=[], claims=['premise'])])

    def test_unobserved_image_citations_and_unread_additional_sources_refuse(self):
        for group in (dict(primary=True, sources=[], claims=[]), dict(primary=False, sources=['unread'], claims=[])):
            with self.subTest(group=group), self.assertRaises(ContractError):
                self.submit(self.entry(grounding=dict(kind='unobserved', session='unseen', coordinate_epoch=1), supports=[group]))
        with self.assertRaisesRegex(ContractError, 'Read the selected'):
            self.submit(self.entry(supports=[dict(primary=False, sources=['unread'], claims=[])]))
        self.assertEqual(self.client.writes, [])

    def test_correction_uses_explicit_retired_ids_for_supersedes(self):
        result = self.submit(identity='correction', kind='correct', retired_ids=['old-one', 'old-two'], reason='Evidence changed')
        self.assertEqual(result['kind'], 'correct')
        self.assertEqual(result['entry']['supersedes'], result['retired_ids'])
        self.assertEqual(self.submit(identity='separate')['entry']['supersedes'], [])

    def test_duplicate_across_instances_reuses_original_host_time_and_only_collects(self):
        first = self.submit()
        saved = self.client.staged_request('mission-test', 'remember')
        self.assertEqual(saved, first)
        time.sleep(.01)
        self.assertGreater(int(time.time() * 1000), saved['entry']['received_time'])
        self.client = StagingClient(self.root)
        self.player = PlayerTools(self.client)
        self.player.snapshots['chosen'] = deepcopy(self.selected)
        self.player.call('enactive_remember', self.arguments())
        self.assertEqual(self.client.writes, [])
        self.assertEqual(len(self.client.reads), 1)
        self.assertEqual(self.client.staged_request('mission-test', 'remember'), saved)
        with self.assertRaisesRegex(MissionClientError, 'staging failed'):
            self.submit(self.entry(text='Changed semantics'))
        self.assertEqual(len(self.client.reads), 1)
        self.assertEqual(self.client.writes, [])

    def stage_path(self, identity='remember'):
        digest = hashlib.sha256(('mission-test\0' + identity).encode()).hexdigest()
        folder = self.root / '.runtime' / 'mission-requests'
        folder.mkdir(exist_ok=True, mode=0o700)
        return folder / ('mc-' + digest + '.json')

    def test_partial_corrupt_unsafe_and_wrong_kind_stages_fail_closed(self):
        path = self.stage_path()
        for payload, mode in ((b'', 0o600), (b'{', 0o600), (canonical(request()).encode(), 0o600),
                              (canonical(request()).encode(), 0o644)):
            with self.subTest(payload=payload, mode=mode):
                path.write_bytes(payload)
                path.chmod(mode)
                with self.assertRaises((ContractError, MissionClientError)):
                    self.submit()
                self.assertEqual(self.client.writes, [])
                self.assertEqual(self.client.reads, [])
        path.unlink()
        path.symlink_to(self.root / 'missing')
        with self.assertRaises(MissionClientError):
            self.submit()
        self.assertEqual(self.client.writes, [])

    def test_existing_other_kind_cannot_reuse_claim_identity(self):
        other = request('observe', request_id='remember')
        self.client.submit(other, wait_seconds=0)
        with self.assertRaisesRegex(ContractError, 'identity'):
            self.submit()
        self.assertEqual(len(self.client.writes), 1)
        self.assertEqual(self.client.reads, [])

    def test_epoch_auto_requires_matching_published_scope_and_explicit_provisional_is_preserved(self):
        for scope in (None, {**self.scope, 'session': 'other'}, {**self.scope, 'mission_id': 'other'}):
            self.player.snapshots['chosen']['mission']['coordinate_scope'] = scope
            with self.subTest(scope=scope), self.assertRaisesRegex(ContractError, 'coordinate_epoch'):
                self.submit()
        self.assertEqual(self.client.writes, [])
        provisional = 12
        self.player.snapshots['chosen']['mission']['provisional_scope'] = {**self.scope, 'coordinate_epoch': provisional}
        result = self.submit(self.entry(grounding=dict(kind='source', source_id=None, coordinate_epoch=provisional)))
        self.assertEqual(result['entry']['scope']['coordinate_epoch'], provisional)
        menu = bundle(9, kind='menu')
        self.player.snapshots['chosen']['source'] = menu
        result = self.submit(self.entry(grounding=dict(kind='source', source_id=None, coordinate_epoch=provisional)), identity='pre-adoption')
        self.assertEqual(result['entry']['observed_time'], dict(revision=9, turn=None))

    def test_explicit_source_uses_its_native_order_and_requires_source_read(self):
        alternate = bundle(2)
        identity = alternate['reference']['observation_id']
        entry = self.entry(grounding=dict(kind='source', source_id=identity, coordinate_epoch=8))
        with self.assertRaises(ContractError):
            self.submit(entry)
        self.player.sources[('mission-test', identity)] = alternate
        result = self.submit(entry)['entry']
        self.assertEqual(result['observed_time'], dict(revision=2, turn=alternate['reference']['turn']))
        self.assertEqual(result['scope']['coordinate_epoch'], 8)
        self.assertEqual(result['sources'], [identity])

    def test_staged_request_absence_identity_and_secure_file_contract(self):
        self.assertIsNone(self.client.staged_request('mission-test', 'absent'))
        path = self.stage_path('absent')
        self.assertIsNone(self.client.staged_request('mission-test', 'absent'))
        path.write_bytes(canonical(request(request_id='absent')).encode())
        path.chmod(0o600)
        self.assertEqual(self.client.staged_request('mission-test', 'absent')['request_id'], 'absent')
        link = self.root / 'hard-link'
        os.link(path, link)
        with self.assertRaises(MissionClientError):
            self.client.staged_request('mission-test', 'absent')
        link.unlink()
        path.write_bytes(b'x' * 65537)
        with self.assertRaises(MissionClientError):
            self.client.staged_request('mission-test', 'absent')
        path.unlink()
        path.mkdir()
        with self.assertRaises(MissionClientError):
            self.client.staged_request('mission-test', 'absent')
        path.rmdir()
        path.parent.rmdir()
        path.parent.symlink_to(self.root / 'missing-folder')
        with self.assertRaises(MissionClientError):
            self.client.staged_request('mission-test', 'absent')
        path.parent.unlink()
        (self.root / '.runtime').rmdir()
        with self.assertRaises(MissionClientError):
            self.client.staged_request('mission-test', 'absent')

    def test_source_claim_with_empty_group_rejects_instead_of_inventing_support(self):
        with self.assertRaisesRegex(ContractError, 'Empty support group'):
            self.submit(self.entry(supports=[dict(primary=False, sources=[], claims=[])]))
        self.assertEqual(self.client.writes, [])

    def test_other_memory_variant_is_unchanged_and_cannot_reuse_claim_identity(self):
        work = dict(schema='campaign-memory/5', record_type='Work', predecessor_work_id=None, id='work-1',
            intent='Inspect water', scope=self.scope, stage='inspection', progress=None,
            available=[], committed=[], predicted_output=[], observed_output=[], unresolved_effects=[],
            sources=[], next_verification='Read the inventory', status='interrupted')
        arguments = self.arguments()
        arguments['intent'] = dict(entry_type='work', entry=work)
        self.player.call('enactive_remember', arguments)
        self.assertEqual(self.client.writes[-1]['entry'], work)
        with self.assertRaisesRegex(ContractError, 'identity'):
            self.submit()
        self.assertEqual(len(self.client.writes), 1)
        self.assertEqual(self.client.reads, [])

    def test_old_canonical_shape_and_missing_snapshot_are_rejected(self):
        with self.assertRaises(ContractError):
            self.submit(claim())
        self.player.snapshots.clear()
        with self.assertRaisesRegex(ContractError, 'Snapshot handle unavailable'):
            self.submit()
        self.assertEqual(self.client.writes, [])

    def input_arguments(self, *, operation=None, source_id=None, scope='new_root'):
        intent = skill() if operation is None else lifecycle(operation)
        intent.pop('kind')
        return dict(snapshot_id='chosen', request_id='input', wait_seconds=0, source_id=source_id,
            supporting_source_ids=[], scope=scope, limits=dict(primitives=8, wall_seconds=45, game_seconds=600), intent=intent)

    def test_null_skill_and_nonlaunch_bind_exact_cached_source_after_source_eviction(self):
        self.player.sources.clear()
        for operation in (None, 'save'):
            args = self.input_arguments(operation=operation)
            args['request_id'] = 'skill' if operation is None else operation
            self.player.call('enactive_skill' if operation is None else 'enactive_lifecycle', args)
            result = self.client.writes[-1]
            self.assertEqual(result['sources'], [self.ref['observation_id']])
            self.assertEqual(result['expected_revision'], self.ref['revision'])
            self.assertEqual(result['expected_boundary_id'], self.source['observation']['boundary']['id'])
        self.assertEqual(self.client.reads, [])
        self.assertEqual(self.client.events, ['submit', 'status', 'submit', 'status'])

    def test_missing_snapshot_source_explains_explicit_diagnostic_selection_without_io(self):
        # Observe can retain diagnostic evidence without publishing current_source.
        # An unrelated already-read image cannot become an implicit replacement.
        chosen = self.player.snapshots['chosen']
        chosen['source'] = None
        chosen['mission']['current_source'] = None
        chosen['mission']['phase'] = 'paused'
        chosen['mission']['lifecycle_phase'] = phase(self.source, operation='load', stage='awaiting_transition')
        before = deepcopy(chosen)
        with self.assertRaisesRegex(ContractError, 'enactive_source.*explicitly select'):
            self.player.call('enactive_lifecycle', self.input_arguments(operation='load', scope='lifecycle'))
        self.assertEqual(self.player.snapshots['chosen'], before)
        self.assertEqual(self.client.writes, [])
        self.assertEqual(self.client.reads, [])
        self.assertEqual(self.client.events, [])

    def test_launch_null_remains_source_free_even_with_old_cached_source(self):
        self.player.call('enactive_lifecycle', self.input_arguments(operation='launch'))
        result = self.client.writes[-1]
        self.assertEqual(result['sources'], [])
        self.assertIsNone(result['expected_session'])
        self.assertIsNone(result['expected_revision'])

    def test_explicit_alternate_source_preserved_with_older_admission(self):
        self.player.snapshots['chosen']['mission'].update(phase='admitted', native_process=dict(last_sample=None))
        self.player.snapshots['chosen']['source'] = None
        alternate = bundle(2, kind='menu')
        identity = alternate['reference']['observation_id']
        self.player.sources[('mission-test', identity)] = alternate
        self.player.call('enactive_lifecycle', self.input_arguments(operation='load', source_id=identity))
        self.assertEqual(self.client.writes[-1]['sources'], [identity])

    def test_phase_checkpoint_mismatch_missing_source_and_snapshot_eviction_refuse(self):
        self.player.snapshots['chosen']['mission']['prompt_phase'] = phase(bundle(4))
        with self.assertRaisesRegex(ContractError, 'checkpoint'):
            self.player.call('enactive_skill', self.input_arguments(scope='prompt'))
        self.player.snapshots['chosen']['source'] = None
        with self.assertRaises(ContractError):
            self.player.call('enactive_skill', self.input_arguments())
        self.player.snapshots.clear()
        with self.assertRaisesRegex(ContractError, 'Snapshot handle unavailable'):
            self.player.call('enactive_skill', self.input_arguments(source_id=self.ref['observation_id']))
        self.assertEqual(self.client.writes, [])


class PlayerClaimLedgerTests(unittest.TestCase):
    """Actual canonical source/SQLite memory application; still synthetic evidence."""
    setUp = memory_fixture.CampaignMemoryTests.setUp
    source = memory_fixture.CampaignMemoryTests.source
    context = memory_fixture.CampaignMemoryTests.context

    def test_adapter_correction_retires_actual_ledger_claim_and_preserves_backend_guards(self):
        self.ledger.close()
        self.ledger = MissionLedger(self.root / 'claim-ledger', admission=admission(), now=time.time())
        self.memory = CampaignMemory(self.ledger, self.store)
        reference = self.source()
        (self.root / '.runtime').mkdir()
        client = StagingClient(self.root)
        player = PlayerTools(client)
        source = dict(reference=reference.to_dict(), observation=self.store.observation(reference))
        scope = dict(mission_id='mission-test', session=reference.session, coordinate_epoch=0)
        player.snapshots['chosen'] = dict(mission=snapshot(epoch=0, coordinate_scope=scope), source=source)
        entry = PlayerClaimTests.entry(self)
        intent = dict(entry_type='claim', entry=entry)
        def apply(path, *, data=None, **options):
            import json
            body = json.loads(data)
            self.ledger.begin_request(body, now=time.time())
            result = self.memory.apply(body, now=time.time())
            return dict(status='accepted', operation=dict(request=body, state='completed', result=result))
        client._json = apply
        args = dict(snapshot_id='chosen', request_id='remember', wait_seconds=0, intent=intent)
        original, _ = player.call('enactive_remember', args)
        original_id = original['response']['operation']['result']['entry']['id']
        replacement = deepcopy(entry)
        replacement.update(value=dict(quantity=None, state=None), status='unknown', text='Water count unreadable')
        args.update(request_id='correction', intent=dict(entry_type='claim', entry=replacement,
            retired_ids=[original_id], reason='Visible count is unverified'))
        corrected, _ = player.call('enactive_correct', args)
        result = corrected['response']['operation']['result']
        self.assertEqual(result['entry']['supersedes'], [original_id])
        packet = self.context()
        self.assertEqual([row['id'] for row in packet['claims']], [result['entry']['id']])
        self.assertEqual(packet['claims'][0]['status'], 'unknown')
        unsupported = deepcopy(entry)
        unsupported['supports'] = []
        args.update(request_id='unsupported', intent=dict(entry_type='claim', entry=unsupported))
        with self.assertRaisesRegex(ContractError, 'explicit support'):
            player.call('enactive_remember', args)
        self.assertEqual(len(self.ledger.memory_records('claim')), 2)


if __name__ == '__main__':
    unittest.main()
