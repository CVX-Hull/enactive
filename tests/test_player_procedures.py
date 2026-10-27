"""Semantic procedure authoring over revealed records and actual SDK staging."""
from copy import deepcopy
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_contracts import validate_request
from harness.mission_client import MissionClientError, _envelope
from harness.player_mcp import make_server
from harness.player_tools import PlayerTools
from mcp.client import Client
from tests import test_campaign_procedures as procedure_fixture
from tests.test_player_claims import StagingClient
from tests.test_mission_request_producer import snapshot
from tests.test_mission_contracts import request as memory_request
from tests.test_procedures import procedure
from tests.test_reflection_exchange import proposal


MECHANICAL = ('schema', 'record_type', 'id', 'mission_id', 'procedure_id', 'revision', 'environment')


class ProcedureClient(StagingClient):
    packet = None

    def _json(self, path, *, data=None, **options):
        request = json.loads(data)
        if request['kind'] == 'context':
            self.events.append('context')
            return dict(status='accepted', context=dict(mission_id=request['mission_id'],
                                                        packet=deepcopy(self.packet)))
        response = super()._json(path, data=data, **options)
        if request['kind'] == 'remember' and request['entry_type'] == 'procedure':
            response['operation']['result'] = dict(memory_version=len(self.writes),
                entry=deepcopy(request['entry']), grants_authority=False)
        return response


class PlayerProcedureAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / '.runtime').mkdir()
        self.client = ProcedureClient(self.root)
        self.player = PlayerTools(self.client)
        self.selected = dict(snapshot_id='chosen', mission=snapshot(), source=None, native={})
        self.selected['mission']['configuration'] = dict(procedure_environment=procedure()['environment'])
        self.player.snapshots['chosen'] = deepcopy(self.selected)

    def semantic(self, **changes):
        entry = {k:v for k,v in procedure().items() if k not in MECHANICAL}
        entry.update(changes)
        return entry

    def submit(self, entry=None, identity='remember-procedure'):
        return self.player.call('enactive_remember', dict(snapshot_id='chosen', request_id=identity,
            wait_seconds=0, intent=dict(entry_type='procedure', entry=entry or self.semantic())))

    def reveal(self, records):
        self.client.packet = dict(procedures=deepcopy(records))
        self.player.call('enactive_context', dict(snapshot_id='chosen', intent=dict(handoff=None,
            scope=dict(session='game-test', coordinate_epoch=0), query='test procedure', max_bytes=32768)))

    def advice(self, identities=None):
        self.player.snapshots['chosen']['mission']['reflection'] = dict(proposals=identities or ['proposal-1'])
        self.offered = proposal(mission_id=self.selected['mission']['mission_id'], candidates=[
            procedure(mission_id=self.selected['mission']['mission_id'])])
        self.advice_reads = []
        def read(mission_id, identity):
            self.advice_reads.append((mission_id, identity))
            return dict(status='available', proposal={**deepcopy(self.offered), 'id': identity}, grants_authority=False)
        self.client.reflection_advice = read
        return self.player.call('enactive_advice', dict(snapshot_id='chosen', proposal_index=None))[0]

    def adopt(self, *, snapshot_id='chosen', proposal_index=0, candidate_index=0, identity='adopt'):
        return self.player.call('enactive_remember', dict(snapshot_id=snapshot_id, request_id=identity,
            wait_seconds=0, intent=dict(entry_type='procedure_candidate', proposal_index=proposal_index,
                                      candidate_index=candidate_index)))

    def test_compact_advice_preserves_original_indexes_and_exact_candidate_body(self):
        view = self.advice([f'proposal-{n}' for n in range(6)])
        self.assertEqual([item['proposal_index'] for item in view['proposals']], [2, 3, 4, 5])
        self.assertEqual(view['omitted_proposals'], 2)
        self.assertEqual(len(self.advice_reads), 4)
        candidate = view['proposals'][0]['candidates'][0]
        self.assertEqual(candidate['goal'], self.offered['candidates'][0]['goal'])
        self.assertNotIn('id', candidate)
        self.assertNotIn('support', candidate)
        self.assertNotIn('program', candidate)
        self.assertEqual(self.player.procedures, {})  # Exposure is not adoption.
        self.adopt(proposal_index=2)
        self.assertEqual(self.client.writes[0]['entry'], self.offered['candidates'][0])
        self.assertEqual(self.client.writes[0]['entry_type'], 'procedure')
        record = self.client.writes[0]['entry']
        self.assertEqual(self.player.procedures[(record['mission_id'], record['id'])], record)
        validate_request(self.client.writes[0])

    def test_exact_advice_detail_and_adoption_use_defensive_original_copy(self):
        self.advice()
        view, image = self.player.call('enactive_advice', dict(snapshot_id='chosen', proposal_index=0))
        self.assertIsNone(image)
        self.assertEqual(view['proposals'][0]['proposal']['candidates'], self.offered['candidates'])
        view['proposals'][0]['proposal']['candidates'][0]['reason'] = 'changed return'
        self.offered['candidates'][0]['goal'] = 'changed remote fixture'
        self.adopt()
        self.assertNotEqual(self.client.writes[0]['entry']['goal'], 'changed remote fixture')
        self.assertNotEqual(self.client.writes[0]['entry']['reason'], 'changed return')

    def test_unread_new_snapshot_wrong_indexes_and_eviction_never_retarget(self):
        with self.assertRaisesRegex(ContractError, 'Read this snapshot'):
            self.adopt()
        self.advice()
        self.player.snapshots['newer'] = deepcopy(self.player.snapshots['chosen'])
        for selection in (dict(snapshot_id='newer'), dict(candidate_index=1), dict(proposal_index=1)):
            with self.subTest(selection=selection), self.assertRaises(ContractError):
                self.adopt(**selection)
        with self.assertRaisesRegex(ContractError, 'outside'):
            self.player.call('enactive_advice', dict(snapshot_id='chosen', proposal_index=1))
        self.player._advice.clear()
        with self.assertRaisesRegex(ContractError, 'Read this snapshot'):
            self.adopt()
        self.assertEqual(self.client.writes, [])

    def test_missing_or_wrong_proposal_does_not_make_candidate_selectable(self):
        self.advice()
        self.player._advice.clear()
        self.client.reflection_advice = lambda *args: dict(status='missing', grants_authority=False)
        view, _ = self.player.call('enactive_advice', dict(snapshot_id='chosen', proposal_index=0))
        self.assertEqual(view['proposals'], [dict(proposal_index=0, status='missing')])
        with self.assertRaises(ContractError): self.adopt()
        for changes in (dict(id='other'), dict(mission_id='other')):
            self.client.reflection_advice = lambda *args: dict(status='available', proposal={**self.offered, **changes})
            with self.assertRaisesRegex(ContractError, 'differs'):
                self.player.call('enactive_advice', dict(snapshot_id='chosen', proposal_index=0))
        self.assertEqual(self.client.writes, [])

    def test_old_advice_model_shape_is_rejected_without_compatibility(self):
        with self.assertRaises(ContractError):
            self.player.call('enactive_advice', dict(mission_id='mission-test', proposal_id='proposal-1'))
        self.assertEqual(self.client.events, [])

    def test_new_family_derives_frozen_metadata_without_source_or_status_refresh(self):
        original = self.semantic(program=dict(language='javascript/1', source="function step(v,s){return {status:'yield',state:s,input:null,reason:'fixture'}}"))
        self.submit(original)
        record = self.client.writes[0]['entry']
        self.assertEqual(record['mission_id'], self.selected['mission']['mission_id'])
        self.assertEqual(record['environment'], self.selected['mission']['configuration']['procedure_environment'])
        self.assertEqual(record['revision'], 1)
        self.assertIsNone(record['parent'])
        self.assertNotEqual(record['id'], record['procedure_id'])
        self.assertEqual({k:v for k,v in record.items() if k not in MECHANICAL}, original)
        validate_request(self.client.writes[0])
        # The post-operation presentation attempts status; composition happens
        # before it, and never obtains a replacement context/source.
        self.assertEqual(self.client.events, ['submit', 'status'])

    def test_canonical_metadata_copies_are_rejected_not_an_alternate_authoring_path(self):
        for name in MECHANICAL:
            with self.subTest(name=name), self.assertRaises(ContractError):
                self.submit({**self.semantic(), name:procedure()[name]})
        self.assertEqual(self.client.writes, [])
        self.assertEqual(self.client.events, [])

    def test_explicit_parent_requires_revealed_record_and_derives_family_revision(self):
        parent = procedure()
        selection = dict(mission_id=parent['mission_id'], revision_id=parent['id'])
        with self.assertRaisesRegex(ContractError, 'explicitly retrieve'):
            self.submit(self.semantic(parent=selection))
        self.assertEqual(self.client.writes, [])
        self.reveal([parent])
        self.submit(self.semantic(parent=selection))
        record = self.client.writes[-1]['entry']
        self.assertEqual(record['parent'], selection)
        self.assertEqual(record['procedure_id'], parent['procedure_id'])
        self.assertEqual(record['revision'], parent['revision']+1)
        self.assertNotEqual(record['id'], parent['id'])

    def test_retrieved_historical_head_is_an_exact_parent_for_current_authorship(self):
        from tests.test_procedures import historical, successor
        root = historical()
        head = historical(successor(root, mission_id="older-mission"))
        selection = dict(mission_id=head['mission_id'], revision_id=head['id'])
        with self.assertRaisesRegex(ContractError, 'explicitly retrieve'):
            self.submit(self.semantic(parent=selection))
        self.reveal([head])
        self.submit(self.semantic(parent=selection), identity='current-revision')
        record = self.client.writes[-1]['entry']
        self.assertEqual((record['schema'], record['environment']['native_protocol']), ('procedure/3', 7))
        self.assertEqual((record['procedure_id'], record['revision'], record['parent']),
                         (head['procedure_id'], 3, selection))
        self.assertEqual(self.player.procedures[(head['mission_id'], head['id'])], head)

    def test_missing_or_malformed_admission_environment_submits_nothing(self):
        for environment in (None, {}, {**procedure()['environment'], 'mission_schema':'mission/10'}):
            with self.subTest(environment=environment):
                self.player.snapshots['chosen']['mission']['configuration']['procedure_environment'] = environment
                with self.assertRaises(ContractError): self.submit()
        self.assertEqual(self.client.writes, [])
        self.assertEqual(self.client.events, [])

    def test_original_staging_identity_collects_and_changed_semantics_never_resubmits(self):
        self.submit()
        original = deepcopy(self.client.writes[0])
        restarted = PlayerTools(self.client)
        restarted.snapshots['chosen'] = deepcopy(self.selected)
        self.player = restarted
        self.submit()
        self.assertEqual(self.client.writes, [original])
        self.assertEqual(len(self.client.reads), 1)
        with self.assertRaisesRegex(ValueError, 'staging failed'):
            self.submit(self.semantic(reason='Changed interpretation'))
        self.assertEqual(self.client.writes, [original])

    def test_cache_contains_only_explicitly_revealed_bounded_copies(self):
        records = [procedure(id=f'revision-{n}', procedure_id=f'family-{n}') for n in range(34)]
        for start in range(0, len(records), 16):
            self.reveal(records[start:start+16])
        self.assertEqual(len(self.player.procedures), 32)
        self.assertNotIn(('mission-a', 'revision-0'), self.player.procedures)
        records[-1]['goal'] = 'mutated external data'
        self.assertNotEqual(self.player.procedures[('mission-a','revision-33')]['goal'], records[-1]['goal'])

    def completed(self, record, identity='accepted-procedure'):
        request = memory_request('remember', request_id=identity, mission_id=record['mission_id'],
            entry_type='procedure', entry=deepcopy(record))
        validate_request(request)
        return _envelope(dict(status='accepted', operation=dict(request=request, state='completed',
            result=dict(entry=deepcopy(record), memory_version=1, grants_authority=False))), identity)

    def test_completed_results_are_bounded_qualified_independent_copies(self):
        for n in range(34):
            self.player._finish(self.completed(procedure(id=f'revision-{n}', procedure_id=f'family-{n}')))
        self.assertEqual(len(self.player.procedures), 32)
        self.assertNotIn(('mission-a','revision-0'), self.player.procedures)
        # An explicit repeated result refreshes the existing cache position.
        self.player._finish(self.completed(procedure(id='revision-2', procedure_id='family-2')))
        self.player._finish(self.completed(procedure(id='revision-34', procedure_id='family-34')))
        self.assertIn(('mission-a','revision-2'), self.player.procedures)
        self.assertNotIn(('mission-a','revision-3'), self.player.procedures)
        record = procedure(mission_id='other-mission', id='revision-33')
        envelope = self.completed(record)
        output, _ = self.player._finish(envelope)
        self.assertIn(('mission-a','revision-33'), self.player.procedures)
        output['response']['operation']['result']['entry']['goal'] = 'changed output'
        envelope['response']['operation']['result']['entry']['goal'] = 'changed envelope'
        record['goal'] = 'changed caller'
        self.assertEqual(self.player.procedures[('other-mission','revision-33')]['goal'], procedure()['goal'])
        self.assertEqual(len(self.player.procedures), 32)
        restarted = PlayerTools(self.client)
        self.assertEqual(restarted.procedures, {})
        restarted._finish(self.completed(procedure()))  # An explicit collected receipt can reveal data again.
        self.assertIn(('mission-a',procedure()['id']), restarted.procedures)

    def test_nonfinal_uncertain_rejected_and_nonprocedure_results_never_reveal_a_parent(self):
        base = self.completed(procedure())
        variants = []
        for state in ('accepted','running','blocked','failed','paused'):
            v=deepcopy(base);v['response']['operation']['state']=state;variants.append(v)
        for changes in (dict(transport='uncertain'),dict(reason='Original outcome uncertain'),
                        dict(operation_id='another-operation')):
            variants.append({**deepcopy(base),**changes})
        v=deepcopy(base);v['response']['status']='rejected';variants.append(v)
        v=deepcopy(base);v['response']['operation']['request']['entry_type']='claim';variants.append(v)
        for result in (None,{},dict(entry=None)):
            v=deepcopy(base);v['response']['operation']['result']=result;variants.append(v)
        for v in variants:
            with self.subTest(envelope=v):
                self.player._finish(v)
                self.assertEqual(self.player.procedures, {})
        self.assertEqual(self.client.writes, [])

    def test_invalid_or_mismatched_completed_record_fails_without_revealing_or_rewriting(self):
        base = self.completed(procedure())
        for change in (dict(goal=None),dict(id='other-revision'),dict(mission_id='other-mission'),
                       dict(reason='Another canonical body')):
            v=deepcopy(base);v['response']['operation']['result']['entry'].update(change)
            before=deepcopy(v)
            with self.subTest(change=change),self.assertRaises(ContractError):self.player._finish(v)
            self.assertEqual(v,before)
            self.assertEqual(self.player.procedures,{})
        v=deepcopy(base)
        v['response']['operation']['request']['mission_id']='other-mission'
        with self.assertRaisesRegex(ContractError,'differs'):
            self.player._finish(v)
        self.assertEqual(self.player.procedures,{})
        self.assertEqual(self.client.writes,[])


class PlayerProcedureLedgerTests(unittest.TestCase):
    setUp = procedure_fixture.CampaignProcedureTests.setUp
    episode = procedure_fixture.CampaignProcedureTests.episode

    def connection(self, first_response=None):
        root = self.ledger.directory.parent
        (root / '.runtime').mkdir()
        client = StagingClient(root)
        player = PlayerTools(client)
        selected = dict(snapshot_id='chosen', mission=snapshot(epoch=0,
            configuration=dict(procedure_environment=procedure()['environment'])), native={}, source=None)
        player.snapshots['chosen'] = selected
        entry = {k:v for k,v in procedure(support=[self.episode()]).items() if k not in MECHANICAL}
        calls = []
        def receiver(path, *, data=None, **options):
            body = json.loads(data)
            calls.append(body['kind'])
            if body['kind'] == 'result':
                return dict(status='accepted', operation=self.ledger.request(body['operation_id']))
            if body['kind'] == 'context':
                packet = self.memory.context(body['scope'], body['query'], max_bytes=body['max_bytes'],
                    now_monotonic=100, now_timestamp_ms=1_000_000)
                return dict(status='accepted', context=dict(mission_id=self.admission.mission_id, packet=packet))
            self.ledger.begin_request(body, now=1000)
            result = self.memory.apply(body, now=1000)
            self.ledger.complete_request(body['request_id'], 'completed', result, now=1000)
            if calls == ['remember'] and first_response is not None:
                if first_response == 'uncertain':raise MissionClientError('Injected lost first response')
                return dict(status='accepted',operation=dict(request=body,state='running',result=None))
            return dict(status='accepted', operation=dict(request=body, state='completed', result=result))
        client._json = receiver
        return client, player, entry, calls

    def revision_loop(self, first_response=None):
        client, player, entry, calls = self.connection(first_response)
        def remember(content, identity):
            output, _ = player.call('enactive_remember', dict(snapshot_id='chosen', request_id=identity,
                wait_seconds=0, intent=dict(entry_type='procedure', entry=content)))
            return output
        output = remember(entry, 'first-artifact')
        if first_response is not None:
            self.assertEqual(player.procedures,{})
            first = self.ledger.memory_records('procedure')[0]['entry']
            attempt={**entry,'parent':dict(mission_id=first['mission_id'],revision_id=first['id'])}
            with self.assertRaisesRegex(ContractError,'Parent revision unavailable'):
                remember(attempt,'unrevealed-successor')
            self.assertEqual(calls,['remember'])
            # A fresh adapter has no receipt cache; original collection, not
            # another submission or an automatic context read, reveals it.
            player=PlayerTools(client)
            player.snapshots['chosen']=dict(snapshot_id='chosen',mission=snapshot(epoch=0,
                configuration=dict(procedure_environment=procedure()['environment'])),native={},source=None)
            output,_=player.call('enactive_result',dict(mission_id=self.admission.mission_id,
                operation_id='first-artifact',wait_seconds=0))
        first=output['response']['operation']['result']['entry']
        self.assertEqual(player.procedures[(first['mission_id'],first['id'])],first)
        changed = {**entry, 'parent':dict(mission_id=first['mission_id'], revision_id=first['id']),
                   'reason':'Revised scoped interpretation'}
        second = remember(changed, 'revised-artifact')['response']['operation']['result']['entry']
        self.assertEqual(second['procedure_id'], first['procedure_id'])
        self.assertEqual(second['revision'], 2)
        self.assertEqual(second['parent'],changed['parent'])
        self.assertEqual(calls.count('remember'),2)
        self.assertNotIn('context',calls)
        self.assertEqual(calls.count('result'),first_response is not None)
        with self.assertRaisesRegex(ContractError, 'branches|stale'):
            remember(changed, 'incomparable-artifact')
        self.assertEqual(len(self.ledger.memory_records('procedure')), 2)

    def test_semantic_authoring_and_revision_reach_actual_memory_guards(self):
        self.revision_loop()

    def test_pending_first_response_requires_explicit_original_collection(self):
        self.revision_loop('running')

    def test_uncertain_first_response_requires_explicit_original_collection_without_replay(self):
        self.revision_loop('uncertain')

    def test_omitted_unrevealed_parent_requires_explicit_sufficient_context(self):
        _,player,entry,calls=self.connection()
        output,_=player.call('enactive_remember',dict(snapshot_id='chosen',request_id='first',wait_seconds=0,
            intent=dict(entry_type='procedure',entry=entry)))
        first=output['response']['operation']['result']['entry'];player.procedures.clear()
        changed={**entry,'parent':dict(mission_id=first['mission_id'],revision_id=first['id'])}
        for maximum in (1024,32768):
            output,_=player.call('enactive_context',dict(snapshot_id='chosen',intent=dict(handoff=None,
                scope=dict(session='native-session',coordinate_epoch=0),query='water',max_bytes=maximum)))
            if maximum==1024:
                self.assertEqual(output['response']['context']['packet']['procedures'],[])
                self.assertEqual(player.procedures,{})
                with self.assertRaisesRegex(ContractError,'Parent revision unavailable'):
                    player.call('enactive_remember',dict(snapshot_id='chosen',request_id='too-early',wait_seconds=0,
                        intent=dict(entry_type='procedure',entry=changed)))
                self.assertEqual(calls.count('remember'),1)
        player.call('enactive_remember',dict(snapshot_id='chosen',request_id='successor',wait_seconds=0,
            intent=dict(entry_type='procedure',entry=changed)))
        self.assertEqual(len(self.ledger.memory_records('procedure')),2)
        self.assertEqual(calls.count('context'),2)

    def test_official_mcp_preserves_completed_records_and_explicit_successor(self):
        _,player,entry,calls=self.connection()
        async def exercise():
            async with Client(make_server(player)) as client:
                tools=(await client.list_tools()).tools
                expected=list(player.model_specs.values())
                self.assertEqual([t.name for t in tools],[s.name for s in expected])
                for actual,spec in zip(tools,expected):
                    self.assertEqual(actual.input_schema,spec.schema)
                    self.assertEqual(actual.description,spec.description)
                    self.assertEqual(actual.annotations.read_only_hint,spec.read_only)
                async def write(content):
                    result=await client.call_tool('enactive_remember',dict(snapshot_id='chosen',
                        intent=dict(entry_type='procedure',entry=content)))
                    self.assertFalse(result.is_error)
                    return json.loads(result.content[0].text)['response']['operation']['result']['entry']
                first=await write(entry)
                self.assertEqual(player.procedures[(first['mission_id'],first['id'])],first)
                second=await write({**entry,'parent':dict(mission_id=first['mission_id'],revision_id=first['id'])})
                self.assertEqual(second['procedure_id'],first['procedure_id'])
                self.assertEqual(second['revision'],2)
        asyncio.run(exercise())
        self.assertEqual(calls,['remember','remember'])
        self.assertEqual(len(self.ledger.memory_records('procedure')),2)


if __name__ == '__main__':
    unittest.main()
