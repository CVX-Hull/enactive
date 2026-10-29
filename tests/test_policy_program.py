"""Real embedded-runtime component tests, not organic gameplay evidence."""
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

from harness.player.policy_program import PolicyProgram, PolicyProgramError


def policy(expression):
    return f"function step(view, state) {{ return {expression}; }}"


YIELD = "{status:'yield', state, actions:null, reason:'unfamiliar view'}"


class PolicyProgramTests(unittest.TestCase):
    def test_changed_observations_drive_each_decision_and_continuation(self):
        code = """
        let calls = 0;
        function step(view, state) {
          calls++;
          if (view.kind !== 'choices')
            return {status:'yield', state, actions:null, reason:'unfamiliar view'};
          const row = view.rows.find(row => row.label === state.target);
          if (!row) return {status:'yield', state, actions:null, reason:'target absent'};
          return {status:'act', state:{...state, calls}, reason:'visible target',
                  actions:[{type:'click', button:'left', x:row.x, y:row.y}]};
        }
        """
        state = {'target': 'odd unfamiliar item'}
        with PolicyProgram(code) as program:
            for i in range(20):
                rows = [{'label': 'distractor', 'x': 1, 'y': 2},
                        {'label': state['target'], 'x': 100 + i, 'y': 50 + i}]
                if i % 2:
                    rows.reverse()
                view = {'kind': 'choices', 'rows': rows}
                result = program.step(view, state)
                self.assertEqual(result['actions'], [{'type': 'click', 'button': 'left',
                                                     'x': 100 + i, 'y': 50 + i}])
                state = result['state']
                self.assertEqual(state['calls'], i + 1)
            self.assertEqual(program.step({'kind': 'unknown'}, state)['status'], 'yield')
            self.assertEqual(program.step({'kind': 'choices', 'rows': []}, state)['reason'],
                             'target absent')

    def test_ordinary_actions_and_done_are_data(self):
        actions = [{'type': 'key', 'key': 'ENTER', 'modifiers': []},
                  {'type': 'key', 'key': 'x', 'modifiers': ['CTRL', 'SHIFT']},
                  {'type': 'text', 'text': 'a' * 31},
                  {'type': 'click', 'button': 'right', 'x': 16383, 'y': 0}]
        for value in actions:
            with self.subTest(value=value), PolicyProgram(policy(
                    "{status:'act', state, reason:'try', actions:[view.actions]}")) as program:
                self.assertEqual(program.step({'actions': value}, {})['actions'], [value])
        with PolicyProgram(policy("{status:'done', state, reason:'terminated', actions:null}")) as program:
            self.assertEqual(program.step({}, {})['status'], 'done')

    def test_actions_schema_rejects_missing_modifiers_geometry_and_invalid_values(self):
        invalid = [{'type': 'key', 'key': 'x'},
                   {'type': 'key', 'key': 'x', 'modifiers': ['CTRL', 'CTRL']},
                   {'type': 'text', 'text': 'a' * 32},
                   {'type': 'click', 'button': 'left', 'x': 0, 'y': 1, 'geometry': {}},
                   {'type': 'click', 'button': 'left', 'x': -1, 'y': 1},
                   {'type': 'click', 'button': 'left', 'x': True, 'y': 1}]
        for value in invalid:
            with self.subTest(value=value), PolicyProgram(policy(
                    "{status:'act', state, reason:'try', actions:[view.actions]}")) as program:
                self.assert_faulted(program, {'actions': value}, {})

    def assert_faulted(self, program, view=None, state=None, **kwargs):
        with self.assertRaises(PolicyProgramError):
            program.step(view if view is not None else {}, state if state is not None else {},
                         **kwargs)
        with self.assertRaises(PolicyProgramError):
            program.step({}, {})

    def test_compile_errors_and_runaway_compilation(self):
        for source in ('function step(', 'const x = 1;', 'while (true) {}',
                       "throw new Error('compile failure')",
                       'function step(){}; const again=()=>Promise.resolve().then(again); again();'):
            with self.subTest(source=source), self.assertRaises(PolicyProgramError):
                PolicyProgram(source)

    def test_json_numeric_domain_rejects_loss_before_policy_can_choose_actions(self):
        for value in (2**53, 2**53 + 1, -(2**53 + 1), 10**400, float(2**53)):
            with self.subTest(value=str(value)[:24]), PolicyProgram(policy(YIELD)) as program:
                self.assert_faulted(program, state={'n':value})
        with PolicyProgram(policy("{status:'yield',state,actions:null,reason:'finite binary64'}")) as program:
            self.assertEqual(program.step({}, {'n':2**53-1,'fraction':.25})['state'],
                             {'n':2**53-1,'fraction':.25})
        with PolicyProgram(policy("{status:'yield',state:{n:1e100},actions:null,reason:'unsafe integer'}")) as program:
            self.assert_faulted(program)

    def test_huge_timeout_is_a_normal_fault_and_closes_instance(self):
        with PolicyProgram(policy(YIELD)) as program:
            self.assert_faulted(program, timeout_seconds=10**1000)

    def test_exceptions_loops_and_memory_exhaustion_invalidate_program(self):
        bodies = ["throw new Error('step failure')", 'while (true) {}',
                  'const a = []; while (true) { a.push(new Array(100000).fill(1)); }']
        for body in bodies:
            with self.subTest(body=body), PolicyProgram(f'function step() {{ {body} }}') as program:
                self.assert_faulted(program)

    def test_json_validation_before_stringify(self):
        invalid = ['undefined', '() => 1', 'Symbol()', '1n', 'Promise.resolve({})',
                   "{status:'yield', state:{n:NaN}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{n:Infinity}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{n:undefined}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{n:() => 1}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{n:Symbol()}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{n:1n}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{n:new Date()}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{n:[,1]}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{get n(){throw Error('getter ran')}}, actions:null, reason:'bad'}",
                   "{status:'yield', state:{[Symbol()]:1}, actions:null, reason:'bad'}"]
        for expression in invalid:
            with self.subTest(expression=expression), PolicyProgram(policy(expression)) as program:
                self.assert_faulted(program)
        with PolicyProgram("function step(){ const a={}; a.self=a; return a; }") as program:
            self.assert_faulted(program)

    def test_result_schema_and_utf8_bounds(self):
        invalid = ["{status:'success', state:{}, actions:null, reason:'wrong status'}",
                   "{status:'yield', state:{}, actions:null, reason:''}",
                   "{status:'yield', state:{}, actions:null, reason:'x'.repeat(1025)}",
                   "{status:'yield', state:[], actions:null, reason:'wrong state'}",
                   "{status:'yield', state:{}, actions:{type:'text',text:'x'}, reason:'wrong actions'}",
                   "{status:'act', state:{}, actions:null, reason:'missing actions'}",
                   "{status:'yield', state:{}, reason:'missing actions'}",
                   "{status:'yield', state:{}, actions:null, reason:'extra field', extra:1}",
                   "{status:'yield', state:{x:'x'.repeat(16384)}, actions:null, reason:'large state'}",
                   "{status:'yield', state:{x:'界'.repeat(12000)}, actions:null, reason:'large result'}",
                   "{status:'yield', state:{}, actions:null, reason:'\\ud800'}"]
        for expression in invalid:
            with self.subTest(expression=expression), PolicyProgram(policy(expression)) as program:
                self.assert_faulted(program)

    def test_host_actions_and_source_bounds(self):
        for source in (None, 1, ' ' * (32768 + 1), '//界' * 11000, '\ud800'):
            with self.subTest(source_type=type(source)), self.assertRaises(PolicyProgramError):
                PolicyProgram(source)
        for view, state in (([], {}), ({}, []), ({'n': float('nan')}, {}),
                            ({'x': 'x' * 262144}, {}), ({}, {'x': 'x' * 16384}),
                            ({'x': '\ud800'}, {})):
            with self.subTest(view_type=type(view)), PolicyProgram(policy(YIELD)) as program:
                self.assert_faulted(program, view, state)

    def test_step_timeout_argument(self):
        for timeout in (0, -1, .051, float('nan'), float('inf'), True, None):
            with self.subTest(timeout=timeout), PolicyProgram(policy(YIELD)) as program:
                self.assert_faulted(program, timeout_seconds=timeout)
        with PolicyProgram(policy(YIELD)) as program:
            self.assertEqual(program.step({}, {}, timeout_seconds=.04)['status'], 'yield')

    def test_bridge_intrinsics_cannot_be_replaced(self):
        source = """
        JSON.parse = () => ({forged:true});
        JSON.stringify = () => '{"status":"done"}';
        Object.getPrototypeOf = () => null;
        Object.getOwnPropertyDescriptor = () => ({value:1, enumerable:true});
        Reflect.ownKeys = () => [];
        Number.isFinite = () => true;
        Array.isArray = () => false;
        Object.prototype.toJSON = () => 'forged';
        Array.prototype.toJSON = () => 'forged';
        function step(view, state) {
          return {status:'yield', state:{n:view.n, a:[1,2]}, actions:null, reason:'original'};
        }
        """
        with PolicyProgram(source) as program:
            self.assertEqual(program.step({'n': 17}, {})['state'], {'n': 17, 'a': [1, 2]})
        with PolicyProgram("Number.isFinite=()=>true;" + policy(
                "{status:'yield',state:{n:NaN},actions:null,reason:'bad'}")) as program:
            self.assert_faulted(program)

    def test_delayed_schedulers_and_host_capabilities_are_unreachable(self):
        names = ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval',
                 '__timer_manager', '__TimerManager', 'queueMicrotask',
                 'SharedArrayBuffer', 'Worker', 'fetch', 'require', 'process',
                 'read', 'load', 'std', 'os', 'XMLHttpRequest', 'WebSocket']
        source = policy("{status:'yield', state:{types:view.names.map(n => typeof globalThis[n]),"
                        "waitAsync:typeof Atomics.waitAsync}, actions:null, reason:'capabilities'}")
        with PolicyProgram(source) as program:
            result = program.step({'names': names}, {})['state']
            self.assertEqual(result['types'], ['undefined'] * len(names))
            self.assertEqual(result['waitAsync'], 'undefined')

    def test_microtasks_finish_inside_step_and_cannot_escape_its_timeout(self):
        source = """
        let n = 0;
        function step(view, state) {
          if (view.schedule) Promise.resolve().then(() => { n++; });
          return {status:'yield', state:{n}, actions:null, reason:'microtask count'};
        }
        """
        with PolicyProgram(source) as program:
            program.step({'schedule': True}, {})
            before = program.step({}, {})['state']['n']
            time.sleep(.03)
            after = program.step({}, {})['state']['n']
            self.assertEqual(before, 1)
            self.assertEqual(after, before)
        source = """
        function step() {
          const again = () => Promise.resolve().then(again);
          again();
          return {status:'yield', state:{}, actions:null, reason:'runaway microtasks'};
        }
        """
        with PolicyProgram(source) as program:
            self.assert_faulted(program)

    def test_validation_work_is_bounded(self):
        source = """
        function step() {
          const value = new Proxy({}, {ownKeys(){while(true){}}});
          return {status:'yield', state:{value}, actions:null, reason:'validation loop'};
        }
        """
        with PolicyProgram(source) as program:
            self.assert_faulted(program)

    def test_close_is_idempotent_and_context_exit_does_not_reopen(self):
        program = PolicyProgram(policy(YIELD))
        program.close()
        program.close()
        with self.assertRaises(PolicyProgramError):
            program.step({}, {})
        with self.assertRaises(PolicyProgramError):
            with program:
                pass

    def test_success_and_fault_lifetimes_leave_stderr_clean(self):
        script = """
from harness.player.policy_program import PolicyProgram, PolicyProgramError
for code in ["function step(v,s){return {status:'yield',state:s,actions:null,reason:'ok'}}",
             "function step(){while(true){}}", "while(true){}",
             "function step(){const a=[];while(true){a.push(new Array(100000).fill(1))}}"]:
    try:
        with PolicyProgram(code) as p:
            p.step({}, {})
    except PolicyProgramError:
        pass
print('closed')
"""
        result = subprocess.run([sys.executable, '-c', script], capture_output=True,
                                text=True, timeout=15, cwd=Path(__file__).resolve().parents[1],
                                env={**os.environ, 'PYTHONWARNINGS': 'error::ResourceWarning'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'closed')
        self.assertEqual(result.stderr, '')


class BasicActionBoundsTests(unittest.TestCase):
    def test_public_sequence_and_wait_bounds_are_evaluated_before_dispatch(self):
        code = policy("{status:'act', state, actions:view.actions, reason:'proposal'}")
        key = {'type': 'key', 'key': 'x', 'modifiers': []}
        with PolicyProgram(code) as p:
            self.assertEqual(p.step({'actions': [key] * 32}, {})['actions'], [key] * 32)
        for actions in ([], [key] * 33, [{'type': 'wait', 'seconds': 2}] * 8,
                        [{'type': 'wait', 'seconds': True}], [{'type': 'wait', 'seconds': 2.01}],
                        [{'type': 'click', 'button': 'left', 'x': 1.5, 'y': 0}]):
            with self.subTest(actions=actions), PolicyProgram(code) as p:
                with self.assertRaises(PolicyProgramError):
                    p.step({'actions': actions}, {})
        with PolicyProgram(code) as p:
            self.assertEqual(p.step({'actions': [{'type': 'wait', 'seconds': 2}]}, {})['status'], 'act')


if __name__ == '__main__':
    unittest.main()
