"""Extract actual native receiver, commit and poll bodies; no SDL/game qualification."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class NativeReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("c++")
        if not compiler:
            raise unittest.SkipTest("C++ compiler unavailable")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        header = (Path(__file__).resolve().parents[1] / "native/cdda_harness.h").read_text()
        def body(start, end, *, last=False):
            begin = native.rindex(start) if last else native.index(start)
            return native[begin:native.index(end, begin)]
        production = [header[header.index('enum class boundary_kind'):header.index('// Marks only the injected')],
                      body('struct input_scope {', 'std::vector<std::pair<size_t, const void *>> receivers;'),
                      body('bool scoped()', 'bool in_game = false;'),
                      body('void fault_pause()', 'void scene('),
                      body('scope::scope( boundary_kind', 'void activity_interruptible('),
                      body('void ordinary_gate(', 'input_event action_event('),
                      body('bool publish( ', 'void publish_control( '),
                      body('bool uuid_id(', '} // namespace').replace('bool poll_control(', 'bool production_poll_control('),
                      body('bool poll( keyboard_mode', '} // namespace cdda_harness')]
        fixture = Path(__file__).with_name('native_receiver_fixture.cpp').read_text()
        source = cls.root / 'receiver.cpp'
        source.write_text(fixture.replace('// PRODUCTION_TYPES', production[0] + production[1]).replace(
            '// PRODUCTION_FUNCTIONS', ''.join(production[2:])))
        cls.binary = cls.root / 'receiver'
        result = subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', str(source),
                                 '-o', str(cls.binary)], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr)

    def test_production_receiver_and_dispatch(self):
        for scenario in ('unfamiliar', 'identity', 'timeouts', 'normal-owner', 'unsupported-owner',
                         'debug', 'activity', 'interrupt', 'outside', 'direct-key-resize',
                         'direct-text-resize', 'direct-click-resize', 'direct-exact-rejected',
                         'translated-key', 'translated-text', 'translated-click', 'translated-click-resize',
                         'semantic-exact', 'semantic-drift', 'comparison-io', 'comparison-symlink',
                         'stale', 'authority', 'pause', 'receiver-exit', 'receiver-changed-at-commit',
                         'expected-refusal', 'wire5', 'hard-fault', 'human-fault', 'postcommit-feed',
                         'postcommit-publish', 'postcommit-unlink', 'control-first', 'control-postcommit-feed',
                         'control-postcommit-publish', 'control-wire5', 'refusal-capture-failure',
                         'refusal-capture-human', 'refusal-storage-failure'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory(dir=self.root) as directory:
                result = subprocess.run([str(self.binary), scenario], cwd=directory,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f'{scenario} passed\n')

    def test_wire_and_live_publication_contract(self):
        native = (Path(__file__).resolve().parents[1] / 'native/cdda_harness.cpp').read_text()
        self.assertIn('out.member( "protocol", 6 );', native)
        self.assertEqual(native.count('integer_member( request, "protocol" ) != 6'), 2)
        self.assertIn(r'\"protocol\":6', native)
        self.assertNotIn('integer_member( request, "protocol" ) != 5', native)
        self.assertIn('out.member( "input_receiver", ordinary_receiver() );', native)
        self.assertNotIn('menus.count( name )', native)
        self.assertNotIn('e.what() ==', native)
        self.assertNotIn('e.what().find', native)
