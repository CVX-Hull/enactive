"""Real SQLite/files for current export/import, with synthetic observations only."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from harness.gameplay.advisory_export import artifact_parts, derive_data, export_current
from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.evidence import _canonical
from harness.gameplay.mission_requests import _source_binding
from harness.gameplay.procedure_library import ProcedureLibrary
from harness.gameplay.procedure_archive import captured_database
from tests import test_procedure_library as archive_fixtures


class AdvisoryExportTests(unittest.TestCase):
    def setUp(self):
        owned = Path(__file__).resolve().parents[1] / '.runtime/advisory-export-tests'
        owned.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=owned)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.fixture = archive_fixtures.SealedProcedureArchiveTests()
        self.fixture.root = self.root
        from tests.test_procedures import procedure
        self.fixture.environment = procedure()['environment']

    def export(self, *pins, **limits):
        return export_current(self.root, list(pins), validator_revision='0' * 40, **limits)

    def library(self, *pins):
        result = ProcedureLibrary(self.root, pins, current_mission_id='current')
        self.addCleanup(result.close)
        return result

    def test_single_current_donor_format_preserves_originals_and_uses_advisory_source_metadata(self):
        directory, identity, record, pin = self.fixture.archive()
        before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
        with self.assertRaises(ContractError):
            self.library(pin)  # Raw current sources are not a live fallback.
        artifact, = self.export(pin)
        self.assertEqual(artifact, self.root.joinpath(*artifact_parts(directory.name, pin)))
        self.assertEqual(before, {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()})
        after_export = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        library = self.library(pin)
        self.assertEqual(library.records(), (record,))
        metadata, image = library.source(directory.name, identity)
        self.assertEqual(metadata['schema'], 'advisory-source/1')
        self.assertEqual(metadata['capture']['original_protocol'], 7)
        self.assertEqual(hashlib.sha256(image).hexdigest(), metadata['reference']['frame_sha256'])
        with self.assertRaises(ContractError):
            _source_binding(metadata)
        self.assertEqual(after_export, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        with self.assertRaises(FileExistsError):
            self.export(pin)
        self.assertEqual(after_export, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_published_projection_is_deterministic_from_pinned_original_blobs(self):
        directory, _, _, pin = self.fixture.archive()
        artifact, = self.export(pin)
        manifest = json.loads((artifact / 'manifest.json').read_bytes())
        with captured_database((directory / 'mission.sqlite3').read_bytes()) as database:
            first = derive_data(database, json.loads((directory / 'evidence/evidence.json').read_bytes()), pin)
            second = derive_data(database, json.loads((directory / 'evidence/evidence.json').read_bytes()), pin)
        self.assertEqual(_canonical(first), _canonical(second))
        self.assertEqual(_canonical(first), _canonical(manifest['data']))

    def test_current_exports_do_not_follow_original_absolute_paths_after_relocation(self):
        _, identity, _, pin = self.fixture.archive()
        self.export(pin)
        relocated = self.root / 'relocated-project'
        (relocated / '.runtime').mkdir(parents=True)
        shutil.copytree(self.root / '.runtime/procedure-library', relocated / '.runtime/procedure-library')
        with ProcedureLibrary(relocated, [pin], current_mission_id='current') as library:
            metadata, _ = library.source(pin['mission_id'], identity)
            self.assertIn(str(self.root), metadata['reference']['frame_path'])
            self.assertEqual(metadata['capture']['original_protocol'], 7)

    def test_invalid_or_over_budget_source_cannot_publish_ready_manifest(self):
        directory, _, _, pin = self.fixture.archive()
        with self.assertRaises(ContractError):
            self.export(pin, max_bytes=1)
        self.assertFalse(self.root.joinpath(*artifact_parts(directory.name, pin)).exists())
        bad = self.fixture.edit_db(directory, "UPDATE requests SET state='running'")
        with self.assertRaises(ContractError):
            self.export(bad)
        self.assertFalse(self.root.joinpath(*artifact_parts(directory.name, bad)).exists())

    def test_derived_field_tamper_and_original_hash_corruption_refuse_independently(self):
        _, _, _, pin = self.fixture.archive()
        artifact, = self.export(pin)
        path = artifact / 'manifest.json'
        before = path.read_bytes()
        value = json.loads(before)
        value['data']['procedures'][0]['record']['goal'] = 'forged derived meaning'
        path.write_bytes(_canonical(value))
        with self.assertRaisesRegex(ContractError, 'projection differs'):
            self.library(pin)
        path.write_bytes(before)
        (artifact / 'mission.sqlite3').write_bytes(b'changed pinned originals')
        with self.assertRaisesRegex(ContractError, 'pinned hash'):
            self.library(pin)

    def test_artifact_images_remain_checked_and_raw_original_changes_cannot_redirect_reads(self):
        directory, identity, _, pin = self.fixture.archive()
        artifact, = self.export(pin)
        library = self.library(pin)
        original = library.source(directory.name, identity)[1]
        (directory / 'evidence/frames' / (identity + '.png')).write_bytes(b'changed raw mission')
        self.assertEqual(library.source(directory.name, identity)[1], original)
        (artifact / 'evidence/frames' / (identity + '.png')).write_bytes(b'changed export')
        with self.assertRaises(ContractError):
            library.source(directory.name, identity)

    def rebind_corrupt_originals(self, artifact, pin, sql, parameters=()):
        """Attacker updates original bytes AND all derived fields/pins in fixture.

        Live semantic guards must still refuse; this avoids merely exercising an
        outer digest or projection mismatch. No production original is modified.
        """
        database_path = artifact / 'mission.sqlite3'
        with sqlite3.connect(database_path) as database:
            database.execute(sql, parameters)
        new = {**pin, 'ledger_sha256': hashlib.sha256(database_path.read_bytes()).hexdigest()}
        manifest_path = artifact / 'manifest.json'
        manifest = json.loads(manifest_path.read_bytes())
        index = json.loads((artifact / 'evidence/evidence.json').read_bytes())
        with captured_database(database_path.read_bytes()) as database:
            data = derive_data(database, index, new)
        manifest.update(source=new, data=data)
        manifest_path.write_bytes(_canonical(manifest))
        target = self.root.joinpath(*artifact_parts(new['mission_id'], new))
        artifact.rename(target)
        return new

    def test_semantic_terminal_allowlists_and_reflection_closure_survive_recomputed_pins(self):
        for number, (sql, parameters) in enumerate((
                ("UPDATE requests SET state=?", ('invented-terminal',)),
                ("INSERT INTO reflection_jobs VALUES (?)", ('claimed',)),
                ("UPDATE metadata SET value=? WHERE key='state'", (canonical({'phase': 'active'}),)))):
            directory, _, _, pin = self.fixture.archive('mission-' + str(number))
            artifact, = self.export(pin)
            changed = self.rebind_corrupt_originals(artifact, pin, sql, parameters)
            with self.subTest(sql=sql), self.assertRaises(ContractError):
                self.library(changed)

    def test_semantic_receipt_guard_survives_independently_recomputed_original_pins(self):
        _, _, _, receipt, _, pin = self.fixture.known_archive()
        artifact, = self.export(pin)
        receipt['transport_disposition'] = 'unknown'
        changed = self.rebind_corrupt_originals(artifact, pin, 'UPDATE primitives SET result=?', (canonical(receipt),))
        with self.assertRaisesRegex(ContractError, 'delivery disposition'):
            self.library(changed)

    def test_duplicate_native_identity_refuses_after_recomputed_original_pins_and_projection(self):
        _, _, _, receipt, _, pin = self.fixture.known_archive()
        artifact, = self.export(pin)
        receipt['logical_action_id'] = 'logical-2'
        changed = self.rebind_corrupt_originals(artifact, pin,
            "INSERT INTO primitives SELECT 'logical-2',request_id,intent,native_id,state,?,effect FROM primitives WHERE id='logical-1'",
            (canonical(receipt),))
        with self.assertRaisesRegex(ContractError, 'reuse an immutable native request identity'):
            self.library(changed)

    def test_all_dependency_pins_and_qualified_lineage_are_still_required(self):
        from tests.test_procedures import successor
        _, _, first, a = self.fixture.archive()
        _, _, child, b = self.fixture.archive('mission-b',
            records=[successor(first, mission_id='mission-b', id='revision-b', support=first['support'])], dependencies=[a])
        self.export(a, b)
        with self.assertRaises(ContractError):
            self.library(b)
        self.assertEqual(len(self.library(b, a).records()), 2)
        self.assertEqual(child['mission_id'], 'mission-b')

    def test_new_current_donor_can_keep_already_exported_parent_closure(self):
        from tests.test_procedures import successor
        _, _, first, a = self.fixture.archive()
        self.export(a)
        _, _, _, b = self.fixture.archive('mission-b',
            records=[successor(first, mission_id='mission-b', id='revision-b', support=first['support'])], dependencies=[a])
        self.export(b, dependencies=[a])
        self.assertEqual(len(self.library(b, a).records()), 2)

    def test_symlink_or_alias_export_files_cannot_bypass_regular_file_guards(self):
        _, _, _, pin = self.fixture.archive()
        artifact, = self.export(pin)
        path = artifact / 'manifest.json'
        saved = self.root / 'saved-manifest.json'
        shutil.move(path, saved)
        path.symlink_to(saved)
        with self.assertRaises(ContractError):
            self.library(pin)
