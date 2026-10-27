"""Represented UI source contract: real JS/writer, synthetic transfer only.

No native usefulness, learned authorship, pixels or player cadence is established.
"""
from contextlib import contextmanager
import copy
from dataclasses import replace
import unittest

from harness.gameplay.mission_contracts import LearningPolicy
from tests import test_mission_runtime as runtime_fixture
from tests.test_procedures import procedure


CODE = """function step(view, state) {
 const key = (key, next) => ({status:'act', state:{...state,...next},
   input:{type:'key',key,modifiers:[]}, reason:'synthetic transfer fixture'});
 if (state.activated)
   return {status:'done',state,input:null,reason:'inspect actual transfer effect'};
 if (!state.opened) return key('i', {opened:true});
 const ui = view.ui;
 if (!ui || ui.purpose !== 'uilist' || ui.title !== 'Fixture transfer')
   return {status:'yield',state,input:null,reason:'required represented UI unavailable'};
 const matches = ui.rows.filter(row => row.text === 'Transfer sample');
 const selected = ui.rows.findIndex(row => row.id === ui.selected);
 if (matches.length !== 1 || !matches[0].enabled || selected < 0)
   return {status:'yield',state,input:null,reason:'target absent, disabled or ambiguous'};
 const target = ui.rows.findIndex(row => row.id === matches[0].id);
 if (target === selected) {
   if (state.objective === 'highlight')
     return {status:'done',state,input:null,reason:'highlight reached; invocation not requested'};
   return key('ENTER', {opened:true,activated:true});
 }
 return key(target > selected ? 'DOWN' : 'UP', state);
}"""


class ProgramUIExecutionTests(unittest.TestCase):
    @contextmanager
    def fixture(self, *, fault=None, reorder=True):
        f = runtime_fixture.MissionRuntimeTests(methodName='runTest')
        f.setUp()
        try:
            f.a = replace(f.a, learning=LearningPolicy(procedure()['environment'],
                reflector_id='reflector-a'), allowed_skills=(*f.a.allowed_skills, 'direct', 'program'))
            f.start()
            normal = copy.deepcopy(f.bridge.value['scene'])
            effects = dict(available=1, carried=0, activated=[], keys=[])
            entry = procedure(mission_id=f.a.mission_id, procedure_id='fixture-transfer',
                goal='Transfer one synthetic sample', program={'language':'javascript/1', 'source':CODE},
                support=[dict(mission_id=f.a.mission_id, request_ids=['start-1'],
                    source_ids=[f.runtime._current.observation_id], interpretation='Synthetic source contract only')])
            remember = f.request('remember', entry_type='procedure', entry=entry)
            self.assertEqual(f.runtime.command(remember)['status'], 'accepted')
            self.assertEqual(f.settled(remember['request_id'])['state'], 'completed')

            def transfer(bridge, request):
                if request['kind'] != 'direct':
                    return True
                key = request['input']['key']
                effects['keys'].append(key)
                if key == 'i':
                    rows = [dict(id=identity, text=label, enabled=True, hotkey=None, rendered_marker=None)
                        for identity, label in [('a', 'Inspect sample'), ('b', 'Leave sample'),
                                                ('target', 'Transfer sample')]]
                    ui = dict(purpose='uilist', title='Fixture transfer', rows=rows,
                        selected='a', filter=None, count=None, coverage='rendered_rows_only')
                    if fault == 'missing-ui':
                        ui = None
                    elif fault == 'missing-target':
                        rows.pop()
                    elif fault == 'disabled':
                        rows[-1]['enabled'] = False
                    elif fault == 'ambiguous':
                        rows[1]['text'] = 'Transfer sample'
                    bridge.value.update(scene=None, ui=ui, category='UILIST',
                        actions=['UILIST.UP', 'UILIST.DOWN', 'CONFIRM', 'UILIST.QUIT'])
                    bridge.value['boundary'].update(kind='menu', id='fixture-transfer')
                elif key in ('DOWN', 'UP'):
                    ui = bridge.value['ui']
                    index = next(n for n, row in enumerate(ui['rows']) if row['id'] == ui['selected'])
                    ui['selected'] = ui['rows'][index + (1 if key == 'DOWN' else -1)]['id']
                    if reorder and len(effects['keys']) == 2:
                        ui['rows'] = [ui['rows'][2], ui['rows'][1], ui['rows'][0]]
                elif key in ('ENTER', 'ESC'):
                    if key == 'ENTER':
                        chosen = bridge.value['ui']['selected']
                        effects['activated'].append(chosen)
                        if chosen == 'target':
                            effects['available'] -= 1
                            effects['carried'] += 1
                    scene = copy.deepcopy(normal)
                    scene['turn'] += 1
                    bridge.value.update(scene=scene, ui=None, category='DEFAULTMODE', actions=['INVENTORY'])
                    bridge.value['boundary'].update(kind='normal_play', id='fixture-return')
                return True

            f.bridge.behavior = transfer
            yield f, entry, effects
        finally:
            f.doCleanups()

    def invoke(self, f, entry, *, primitives=8, objective='invoke'):
        intent = ('Highlight the target without invoking it' if objective == 'highlight'
                  else 'Invoke the target, then stop for independent effect inspection')
        request = f.control('program', dict(state=dict(objective=objective), intent=intent,
            expected=intent, interrupt_allowed=False), request_id='program-ui',
            limits=dict(primitives=primitives, wall_seconds=120, game_seconds=1200),
            procedure=dict(mission_id=entry['mission_id'], revision_id=entry['id'],
                use_id='ui-use', applicability='Represented synthetic transfer list'))
        frozen = copy.deepcopy(request)
        self.assertIsNone(request['phase_id'])
        self.assertIsNone(f.runtime._prompt_phase)
        self.assertEqual(f.runtime.command(request)['status'], 'accepted')
        result = f.settled(request['request_id'])
        self.assertEqual(f.runtime._ledger.request(request['request_id'])['request'], frozen)
        self.assertEqual(request, frozen)
        return result

    def test_highlight_and_invoke_objectives_have_distinct_effect_oracles(self):
        # These are explicit fictional UI objectives, not model or native evidence.
        def reached(objective, effects, ui):
            if objective == 'highlight':
                return (ui is not None and ui['selected'] == 'target'
                        and effects['activated'] == [] and effects['carried'] == 0)
            return (effects['activated'] == ['target'] and effects['carried'] == 1
                    and effects['available'] == 0)

        for objective in ('highlight', 'invoke'):
            with self.subTest(objective=objective), self.fixture() as (f, entry, effects):
                result = self.invoke(f, entry, objective=objective)
                self.assertEqual(result['result']['program']['status'], 'done')
                self.assertFalse(result['result']['program']['task_success_verified'])
                ui = f.bridge.value['ui']
                self.assertTrue(reached(objective, effects, ui))
                opposite = 'invoke' if objective == 'highlight' else 'highlight'
                self.assertFalse(reached(opposite, effects, ui))
                self.assertEqual('ENTER' in effects['keys'], objective == 'invoke')

    def assert_trace(self, f, entry, result, keys):
        self.assertEqual(result['state'], 'partial', result)
        self.assertFalse(result['result']['program']['task_success_verified'])
        self.assertEqual(result['result']['procedure_use']['revision_id'], entry['id'])
        self.assertEqual(result['result']['procedure_use']['root_request_id'], 'program-ui')
        self.assertFalse(result['result']['procedure_use']['inherited'])
        rows = f.runtime._ledger.primitive_records()
        self.assertEqual([row['intent']['value']['key'] for row in rows], keys)
        self.assertEqual({row['request_id'] for row in rows}, {'program-ui'})
        self.assertTrue(all(row['state'] == 'returned' for row in rows))
        self.assertIsNotNone(rows[0]['intent']['input_observation'])
        self.assertTrue(all(row['intent']['input_observation'] is None for row in rows[1:]))
        trace = result['result']['program']['trace']
        self.assertEqual(trace['omitted_events'], 0)
        deliveries = [event for event in trace['events'] if event['kind'] == 'delivery']
        evaluations = [event for event in trace['events'] if event['kind'] == 'evaluation']
        self.assertEqual([event['input']['key'] for event in deliveries], keys)
        self.assertEqual([event['logical_id'] for event in deliveries], [row['logical_id'] for row in rows])
        self.assertEqual([event['before_source_id'] for event in deliveries],
                         [row['intent']['source_before'] for row in rows])
        for n, event in enumerate(deliveries):
            self.assertEqual(event['transport_disposition'], 'returned')
            self.assertEqual(event['after_source_id'], rows[n]['result']['source_after'])
            self.assertEqual(evaluations[n]['source_id'], event['before_source_id'])
            if n + 1 < len(evaluations):
                self.assertEqual(evaluations[n + 1]['source_id'], event['after_source_id'])
        self.assertEqual(len({event['source_id'] for event in evaluations}), len(evaluations))
        self.assertEqual(f.runtime.status()['spent_inputs'], len(keys))
        self.assertEqual(f.runtime.status()['phase'], 'active')

    def test_current_label_selection_survives_row_reorder_in_one_program_request(self):
        for reorder, keys in ((False, ['i', 'DOWN', 'DOWN', 'ENTER']),
                              (True, ['i', 'DOWN', 'UP', 'ENTER'])):
            with self.subTest(reorder=reorder), self.fixture(reorder=reorder) as (f, entry, effects):
                result = self.invoke(f, entry)
                self.assertEqual(effects['keys'], keys)
                self.assertEqual(effects['activated'], ['target'])
                self.assertEqual((effects['available'], effects['carried']), (0, 1))
                self.assertEqual(result['result']['program']['status'], 'done')
                self.assertEqual(result['result']['program']['evaluations'], 5)
                self.assert_trace(f, entry, result, keys)
                references = {ref.observation_id: ref for ref in f.runtime._store.historical_references}
                evaluations = [event for event in result['result']['program']['trace']['events']
                               if event['kind'] == 'evaluation']
                menus = [f.runtime._store.observation(references[event['source_id']])['ui']
                         for event in evaluations[1:4]]
                self.assertEqual([menu['selected'] for menu in menus], ['a', 'b', 'target'])
                self.assertEqual([[row['id'] for row in menu['rows']].index('target') for menu in menus],
                                 [2, 0, 0] if reorder else [2, 2, 2])
                self.assertEqual(f.bridge.value['scene']['position'], [0, 0, 0])
                self.assertEqual(f.runtime.status()['metrics']['game_seconds'], 1)
                self.assertIsNone(f.runtime._prompt_phase)

    def test_changed_required_ui_yields_then_ordinary_fallback_keeps_root_budget(self):
        for fault in ('missing-ui', 'missing-target', 'disabled', 'ambiguous'):
            with self.subTest(fault=fault), self.fixture(fault=fault) as (f, entry, effects):
                result = self.invoke(f, entry, primitives=2)
                self.assertEqual(result['result']['program']['status'], 'yield')
                self.assertEqual(effects['activated'], [])
                self.assertEqual((effects['available'], effects['carried']), (1, 0))
                self.assert_trace(f, entry, result, ['i'])
                self.assertEqual(result['result']['phase']['origin_request_id'], 'program-ui')
                self.assertEqual(f.runtime.status()['prompt_phase']['origin_request_id'], 'program-ui')
                root = f.runtime._ledger.request('program-ui')
                fallback = f.control('direct', dict(input=dict(type='key', key='ESC', modifiers=[]),
                    intent='Deliberate fixture cancellation', expected='Inspect return', interrupt_allowed=False),
                    phase_id='program-ui', request_id='ui-fallback')
                self.assertEqual(f.runtime.command(fallback)['status'], 'accepted')
                returned = f.settled('ui-fallback')
                self.assertEqual(returned['state'], 'partial', returned)
                lineage = returned['result']['procedure_use']
                self.assertEqual(lineage['root_request_id'], 'program-ui')
                self.assertEqual(lineage['revision_id'], entry['id'])
                self.assertTrue(lineage['inherited'])
                self.assertEqual(f.runtime.status()['spent_inputs'], 2)
                self.assertEqual(effects['keys'], ['i', 'ESC'])
                self.assertEqual(effects['activated'], [])
                self.assertEqual(f.runtime._ledger.request('program-ui'), root)
                self.assertIsNone(f.runtime._prompt_phase)

    def test_original_cumulative_cap_stops_before_activation_and_blocks_replenishment(self):
        with self.fixture() as (f, entry, effects):
            result = self.invoke(f, entry, primitives=3)
            self.assertIn('limit exhausted', result['result']['reason'])
            self.assert_trace(f, entry, result, ['i', 'DOWN', 'UP'])
            self.assertEqual(f.bridge.value['ui']['selected'], 'target')
            self.assertEqual((effects['available'], effects['carried']), (1, 0))
            root = f.runtime._ledger.request('program-ui')
            child = f.control('direct', dict(input=dict(type='key', key='ENTER', modifiers=[]),
                intent='Fixture activation beyond root cap', expected='Must refuse', interrupt_allowed=False),
                phase_id='program-ui', request_id='over-budget')
            self.assertEqual(f.runtime.command(child)['status'], 'accepted')
            refused = f.settled('over-budget')
            self.assertEqual(refused['state'], 'blocked', refused)
            self.assertIn('Original local macro allowance exhausted', refused['result']['reason'])
            self.assertEqual(effects['keys'], ['i', 'DOWN', 'UP'])
            self.assertEqual(effects['activated'], [])
            self.assertEqual(f.runtime.status()['spent_inputs'], 3)
            self.assertEqual(f.runtime._ledger.request('program-ui'), root)
            self.assertEqual(f.runtime.status()['phase'], 'active')
