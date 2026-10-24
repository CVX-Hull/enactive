"""Real JS + mission writer + synthetic transport; not organic/native evidence."""
from dataclasses import replace
import copy
import threading
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.mission_contracts import LearningPolicy, validate_request
from harness.gameplay.program_input import program_view
from tests import test_mission_runtime as runtime_fixture
from tests.test_procedures import procedure, successor


CODE = """function step(view, state) {
 if (!view.scene) return {status:'yield',state,input:null,reason:'visible scene unavailable'};
 if (view.scene.visible_creatures.some(c=>c.hostile))
   return {status:'yield',state,input:null,reason:'changed visible threat'};
 if (view.scene.position[0] >= state.target)
   return {status:'done',state,input:null,reason:'program stopping condition; inspect actual outcome'};
 return {status:'act',state,input:{type:'key',key:'RIGHT',modifiers:[]},reason:'test fixture direction'};
}"""


class ProgramExecutionTests(unittest.TestCase):
    def setUp(self):
        self.f = runtime_fixture.MissionRuntimeTests(methodName='runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.a = replace(self.f.a, learning=LearningPolicy(procedure()['environment'], reflector_id='reflector-a'),
                           allowed_skills=(*self.f.a.allowed_skills, 'direct', 'program'))
        self.f.start()
        self.support = self.f.runtime._current.observation_id
        self.entry = procedure(mission_id=self.f.a.mission_id,
            program={'language':'javascript/1', 'source':CODE},
            support=[{'mission_id':self.f.a.mission_id, 'request_ids':['start-1'],
                'source_ids':[self.support], 'interpretation':'Synthetic fixture only'}])
        self.remember(self.entry)
        self.deliveries = 0
        def move(bridge, request):
            if request['kind'] == 'direct':
                self.deliveries += 1
                if request['input']['type'] == 'key':
                    bridge.value['scene']['position'][0] += 1
                bridge.value['scene']['turn'] += 1
            return True
        self.f.bridge.behavior = move

    def remember(self, entry):
        request = self.f.request('remember', request_id='remember-' + entry['id'],
                                 entry_type='procedure', entry=entry)
        self.assertEqual(self.f.runtime.command(request)['status'], 'accepted')
        result = self.f.settled(request['request_id'])
        self.assertEqual(result['state'], 'completed', result)

    def invoke(self, target=2, *, revision=None, **changes):
        selection = dict(mission_id=self.entry['mission_id'], revision_id=revision or self.entry['id'],
                         use_id='use-' + changes.get('request_id', 'program-1'), applicability='Synthetic visible fixture')
        request = self.f.control('program', dict(state={'target':target}, intent='Synthetic movement fixture',
            expected='Inspect actual position', interrupt_allowed=False), procedure=selection,
            request_id='program-1')
        request.update(changes)
        response = self.f.runtime.command(request)
        self.assertEqual(response['status'], 'accepted', response)
        return self.f.settled(request['request_id'])

    def test_multiple_inputs_one_request_current_feedback_and_pinned_lineage(self):
        result = self.invoke()
        self.assertEqual(result['state'], 'partial', result)
        self.assertEqual(result['result']['program']['status'], 'done')
        self.assertFalse(result['result']['program']['task_success_verified'])
        self.assertEqual(self.deliveries, 2)
        rows = self.f.runtime._ledger.primitive_records()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['request_id'] for r in rows}, {'program-1'})
        self.assertNotEqual(rows[0]['intent']['source_before'], rows[1]['intent']['source_before'])
        self.assertIsNotNone(rows[0]['intent']['input_observation'])
        self.assertIsNone(rows[1]['intent']['input_observation'])
        self.assertEqual(result['result']['procedure_use']['revision_id'], self.entry['id'])
        events = result['result']['program']['trace']['events']
        self.assertEqual([e['input']['key'] for e in events if e['kind'] == 'delivery'], ['RIGHT', 'RIGHT'])
        self.assertEqual([e['transport_disposition'] for e in events if e['kind'] == 'delivery'], ['returned', 'returned'])
        self.assertEqual(result['result']['program']['trace']['omitted_events'], 0)
        self.assertEqual(self.f.runtime.status()['phase'], 'active')

    def test_original_input_limit_stops_without_new_request_or_allowance(self):
        result = self.invoke(10, limits=dict(primitives=2, wall_seconds=10, game_seconds=20))
        self.assertEqual(self.deliveries, 2)
        self.assertIn('limit exhausted', result['result']['reason'])
        self.assertEqual(self.f.runtime.status()['phase'], 'active')
        self.assertEqual({r['request_id'] for r in self.f.runtime._ledger.primitive_records()}, {'program-1'})

    def test_adviser_gets_actual_generated_inputs_and_delivery_without_player_narration(self):
        self.invoke()
        self.f.runtime._registered_reflection._urgent = True
        jobs = self.f.wait(lambda: self.f.runtime._ledger.reflection_records()[0])
        trajectory = [row for job in jobs for row in job['job']['trajectory']
                      if row['request']['request_id'] == 'program-1']
        self.assertEqual(len(trajectory), 1)
        trace = trajectory[0]['result']['program']['trace']
        self.assertEqual(trace['omitted_events'], 0)
        evaluations = [e for e in trace['events'] if e['kind'] == 'evaluation']
        deliveries = [e for e in trace['events'] if e['kind'] == 'delivery']
        self.assertEqual(len(evaluations), 3)
        self.assertEqual(len(deliveries), 2)
        self.assertTrue(all(e['transport_disposition'] == 'returned' for e in deliveries))
        self.assertEqual([e['input']['key'] for e in deliveries], ['RIGHT', 'RIGHT'])
        self.assertTrue(all(e['source_id'] for e in evaluations))
        self.assertTrue(all('state' in e for e in evaluations))

    def test_visible_counterexample_yields_then_revision_supersedes_selection(self):
        original = self.f.bridge.behavior
        def changed(bridge, request):
            out = original(bridge, request)
            if request['kind'] == 'direct':
                bridge.value['scene']['visible_creatures'] = [{'name':'visible fixture creature','hostile':True}]
            return out
        self.f.bridge.behavior = changed
        result = self.invoke(10)
        self.assertEqual(self.deliveries, 1)
        self.assertEqual(result['result']['program']['status'], 'yield')
        newer = successor(self.entry, support=self.entry['support'], program={'language':'javascript/1','source':CODE},
            counterexamples=[{'mission_id':self.f.a.mission_id, 'request_ids':['program-1'],
                'source_ids':result['result']['source_ids'][-1:], 'interpretation':'Changed visible threat in fixture'}])
        self.remember(newer)
        refused = self.invoke(10, request_id='stale-program')
        self.assertEqual(refused['state'], 'blocked')
        self.assertEqual(self.deliveries, 1)
        self.assertEqual(self.f.runtime.status()['phase'], 'active')

    def test_program_fault_is_zero_input_and_preserves_ordinary_fallback(self):
        newer = successor(self.entry, support=self.entry['support'], program={'language':'javascript/1', 'source':'function step(){while(true){}}'})
        self.remember(newer)
        result = self.invoke(revision=newer['id'])
        self.assertEqual(result['state'], 'blocked', result)
        self.assertEqual(result['result']['program']['status'], 'error')
        self.assertEqual(self.deliveries, 0)
        self.assertEqual(self.f.runtime.status()['phase'], 'active')
        ordinary = self.f.control('direct', dict(input=dict(type='key', key='RIGHT', modifiers=[]),
            intent='Synthetic ordinary fallback', expected='Inspect fixture', interrupt_allowed=False), request_id='fallback')
        self.assertEqual(self.f.runtime.command(ordinary)['status'], 'accepted')
        self.assertEqual(self.f.settled('fallback')['state'], 'partial')
        self.assertEqual(self.deliveries, 1)

    def test_advisory_procedure_is_not_silently_executable(self):
        newer = successor(self.entry, support=self.entry['support'], program=None)
        self.remember(newer)
        result = self.invoke(revision=newer['id'])
        self.assertEqual(result['state'], 'blocked')
        self.assertIn('no executable program', result['result']['reason'])
        self.assertEqual(self.deliveries, 0)
        self.assertEqual(self.f.runtime.status()['phase'], 'active')

    def test_unknown_delivery_ends_program_and_collection_does_not_replay(self):
        original = self.f.bridge.behavior
        def lose_return(bridge, request):
            original(bridge, request)
            return request['kind'] != 'direct'
        self.f.bridge.behavior = lose_return
        result = self.invoke(10)
        self.assertEqual(result['state'], 'unknown', result)
        self.assertEqual(self.deliveries, 1)
        self.assertEqual(result['result']['program']['evaluations'], 1)
        self.assertEqual(self.f.result('program-1'), result)
        self.assertEqual(self.deliveries, 1)
        rows = self.f.runtime._ledger.primitive_records()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['state'], 'unknown')

    def test_cancellation_keeps_returned_program_delivery_for_reflection(self):
        dispatch = self.f.runtime._dispatch
        def cancel_after_dispatch(work, *args, **kwargs):
            actual = dispatch(work, *args, **kwargs)
            work.cancelled.set()
            return actual
        with patch.object(self.f.runtime, '_dispatch', side_effect=cancel_after_dispatch):
            result = self.invoke(10)
        self.assertEqual(result['state'], 'paused', result)
        self.assertEqual(self.deliveries, 1)
        delivery = [e for e in result['result']['program']['trace']['events'] if e['kind'] == 'delivery']
        self.assertEqual(len(delivery), 1)
        self.assertEqual(delivery[0]['transport_disposition'], 'returned')
        self.f.runtime._registered_reflection._urgent = True
        jobs = self.f.wait(lambda: self.f.runtime._ledger.reflection_records()[0])
        row = next(row for job in jobs for row in job['job']['trajectory']
                   if row['request']['request_id'] == 'program-1')
        self.assertEqual(row['result']['program']['trace'], result['result']['program']['trace'])

    def test_text_expands_and_click_uses_the_current_geometry(self):
        code = """function step(view,state) {
          if (!state.typed) return {status:'act',state:{typed:true},input:{type:'text',text:'ab'},reason:'fixture text'};
          if (!state.clicked) return {status:'act',state:{typed:true,clicked:true},input:{type:'click',button:'left',x:0,y:0},reason:'fixture click'};
          return {status:'done',state,input:null,reason:'fixture stopping'};
        }"""
        newer = successor(self.entry, support=self.entry['support'],
            program={'language':'javascript/1', 'source':code})
        self.remember(newer)
        result = self.invoke(revision=newer['id'])
        self.assertEqual(result['result']['program']['status'], 'done', result)
        values = [row['intent']['value'] for row in self.f.runtime._ledger.primitive_records()]
        self.assertEqual(values[:2], [{'type':'text','text':'a'}, {'type':'text','text':'b'}])
        self.assertEqual(values[2]['geometry'], self.f.bridge.value['frame_geometry'])
        self.assertEqual(self.deliveries, 3)

    def test_program_view_has_no_authority_files_or_hidden_image_claim(self):
        observed = self.f.runtime._store.observation(self.f.runtime._current)
        view = program_view(observed)
        self.assertEqual(view['scene'], observed['scene'])
        self.assertEqual(set(view['boundary']), {'kind', 'input_receiver'})
        self.assertFalse({'frame', 'session', 'timestamp_ms', 'revision', 'frame_sha256'} & view.keys())
        self.assertLess(len(canonical(view).encode()), 256*1024)
        self.assertTrue(view['omissions'])

    def test_program_yield_preserves_menu_root_and_cumulative_child_budget(self):
        original = self.f.bridge.behavior
        def menu(bridge, request):
            original(bridge, request)
            if request['kind'] == 'direct':
                bridge.value.update(scene=None, ui=None, category='UNFAMILIAR_FIXTURE', actions=['QUIT'])
                bridge.value['boundary'].update(kind='menu', id='fixture-menu')
            return True
        self.f.bridge.behavior = menu
        result = self.invoke(10)
        self.assertEqual(result['result']['program']['status'], 'yield')
        self.assertEqual(result['result']['phase']['origin_request_id'], 'program-1')
        self.assertEqual(self.f.runtime.status()['prompt_phase']['origin_request_id'], 'program-1')
        direct = self.f.control('direct', dict(input=dict(type='key',key='ESC',modifiers=[]),
            intent='Fixture fallback', expected='Observe fixture', interrupt_allowed=False),
            phase_id='program-1', request_id='menu-fallback')
        self.assertEqual(self.f.runtime.command(direct)['status'], 'accepted')
        settled = self.f.settled('menu-fallback')
        self.assertEqual(settled['result']['procedure_use']['root_request_id'], 'program-1')
        self.assertEqual(settled['result']['procedure_use']['revision_id'], self.entry['id'])

    def test_program_requires_current_contract_explicit_root_and_selection(self):
        request = self.f.control('program', dict(state={}, intent='fixture', expected='fixture',
            interrupt_allowed=False))
        with self.assertRaises(ContractError): validate_request(request)
        for old in ('mission/10', 'mission/9'):
            with self.assertRaises(ContractError): validate_request({**request, 'schema':old})

    def test_program_activity_local_overshoot_keeps_original_cost_and_authority(self):
        self.program_activity_return("game_seconds")

    def test_program_activity_late_observe_keeps_original_cost_and_authority(self):
        self.program_activity_return("wall_seconds")

    def program_activity_return(self, limit):
        normal = copy.deepcopy(self.f.bridge.value['scene'])
        finish = False
        def activity(bridge, request):
            if request['kind'] == 'direct':
                bridge.value.update(scene=None, ui=None, actions=[])
                bridge.value['boundary'].update(kind='activity_poll', input_receiver=False,
                    id='fixture-activity', recovery_operations=['request_interrupt'])
            elif request['kind'] == 'observe' and finish:
                bridge.value['revision'] += 1
                scene = copy.deepcopy(normal)
                scene['turn'] += 301 if limit == 'game_seconds' else 20
                bridge.value.update(scene=scene, actions=['sleep'])
                bridge.value['boundary'].update(kind='normal_play', input_receiver=True,
                    id='fixture-return', recovery_operations=[])
            return True
        self.f.bridge.behavior = activity
        opened = self.invoke(10, limits=dict(primitives=8,
            wall_seconds=1 if limit == 'wall_seconds' else 120, game_seconds=300))
        self.assertEqual(opened['result']['phase']['stage'], 'activity_poll')
        root = self.f.runtime._ledger.request('program-1')
        lease = self.f.runtime._lease
        deliveries = copy.deepcopy(self.f.bridge.delivered)
        if limit == 'wall_seconds':
            threading.Event().wait(max(0, root['deadline'] - self.f.runtime._wall() + .03))
        finish = True
        self.f.runtime.command(self.f.request('observe', request_id='program-activity-return'))
        returned = self.f.settled('program-activity-return')
        self.assertEqual(returned['state'], 'completed', returned)
        self.assertEqual(returned['result']['macro_exhausted'], limit, returned)
        self.assertIs(self.f.runtime._lease, lease)
        self.assertEqual(self.f.runtime.status()['metrics']['game_seconds'], 301 if limit == 'game_seconds' else 20)
        self.assertEqual(self.f.runtime.status()['spent_inputs'], 1)
        self.assertEqual(self.f.runtime._ledger.request('program-1'), root)
        self.assertIsNone(self.f.runtime._prompt_phase)
        self.assertEqual(self.f.bridge.delivered, deliveries)


if __name__ == '__main__':
    unittest.main()
