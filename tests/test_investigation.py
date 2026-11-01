"""Closed-case export fixtures; no native or browser qualification."""
import base64
import contextlib
import hashlib
import html as html_parser
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from harness.computer.protocol import ControlError
from tools.evaluate import main
from tools.investigation import export_selection, html_document, png_check, validate_bundle, write_export


class InvestigationTests(unittest.TestCase):
    def test_multiframe_png_cannot_bypass_single_image_pixel_budget(self):
        stream = io.BytesIO()
        Image.new('RGBA', (1, 1), 'red').save(stream, format='PNG', save_all=True,
            append_images=[Image.new('RGBA', (1, 1), 'blue')], duration=10, loop=0)
        png = stream.getvalue()
        with self.assertRaises(ControlError):
            png_check(png, 1, 1, hashlib.sha256(png).hexdigest())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = self.root / 'case'
        self.case.mkdir()
        self.session = 'a' * 32
        self.source_id = self.session + '-1'
        self.actor = 'actor-original'
        self.receipt = dict(schema='campaign-receipt/2', session=self.session, source_commit='abc123',
            deciding_hosts_quiescent=True, native_absence_verified=True, input_authority_revoked=True,
            driver=dict(schema='player-driver/3', actors=[dict(index=1, actor_id=self.actor)],
                attempts_charged=1, host_seconds_used=2, configured_estimate_usd=.1, missing_usage_attempts=0),
            accounting=dict(consumed_conservative_reservation_usd=.2), outcome='failed')
        self.put_receipt()
        pixels = io.BytesIO()
        Image.new('RGB', (2, 3), 'blue').save(pixels, format='PNG')
        self.png = pixels.getvalue()
        self.metadata = dict(schema='computer-source/1', session=self.session, source_id=self.source_id,
            capture_id=1, sha256=hashlib.sha256(self.png).hexdigest(), media_type='image/png',
            presented_ms=1000, received_wall=1.1, width=2, height=3, window_width=2,
            window_height=3, viewport=[0, 0, 2, 3])
        (self.case / 'sources').mkdir()
        (self.case / 'sources' / (self.source_id + '.png')).write_bytes(self.png)
        with sqlite3.connect(self.case / 'session.sqlite3') as db:
            db.executescript('''PRAGMA user_version=2;
                CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE sources(id TEXT PRIMARY KEY,metadata TEXT NOT NULL,bytes INTEGER NOT NULL);
                CREATE TABLE operations(id TEXT PRIMARY KEY,actor TEXT,kind TEXT,created_wall REAL,
                    deadline REAL,input_json TEXT,final_json TEXT);
                CREATE TABLE native_intents(id TEXT PRIMARY KEY,operation TEXT,receipt TEXT,source TEXT,timing TEXT);
                CREATE TABLE collections(native_id TEXT PRIMARY KEY,receipt TEXT,source TEXT);''')
            db.executemany('INSERT INTO metadata VALUES(?,?)', [('schema', json.dumps('computer-session/2')),
                ('session', json.dumps(self.session))])
            db.execute('INSERT INTO sources VALUES(?,?,?)', (self.source_id, json.dumps(self.metadata), len(self.png)))
            final = dict(schema='computer-operation/1', operation_id='op1', actor_id=self.actor,
                session=self.session, kind='observe', status='completed', reason='PRIVATE_REASON')
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)',
                ('op1', self.actor, 'observe', 1, 10, 'PRIVATE_ARGS', json.dumps(final)))
            receipt = dict(schema='computer-receipt/2', id='native1', session=self.session,
                disposition='delivered', emitted_events=0, reason='PRIVATE_REASON', frame=None)
            db.execute('INSERT INTO native_intents VALUES(?,?,?,?,?)', ('native1', 'op1', json.dumps(receipt),
                self.source_id, json.dumps(dict(intent_wall=1, intent_monotonic=5,
                    receipt_received_wall=1.1, receipt_received_monotonic=5.1))))
        self.events = [dict(type='host-start', schema='player-host/3', telemetry_version=2,
            monotonic_ms=0, wall_time='1970-01-01T00:00:01Z', model='fixture', provider='fixture',
            provider_routing=dict(only=['selected'], order=['selected'], allow_fallbacks=False,
                token='PRIVATE_TOKEN'), prompt='PRIVATE_PROMPT'),
            dict(type='request-start', request_id='r1', monotonic_ms=10, wall_time='1970-01-01T00:00:01.010Z', payload_bytes=500),
            dict(type='request-fetch-start', request_id='r1', monotonic_ms=12),
            dict(type='response-complete', request_id='r1', monotonic_ms=30,
                wall_time='1970-01-01T00:00:01.030Z', stop_reason='toolUse', usage_available=True,
                usage=dict(input=10, output=20, reasoning=8), response_progress=dict(first_content_delta_ms=22), reasoning='PRIVATE_REASONING'),
            dict(type='assistant-text', request_id='r1', monotonic_ms=31, text='😀' * 4005, omitted_bytes=17),
            dict(type='tool-start', request_id='r1', tool_call_id='t1', monotonic_ms=32, tool='player_program_run', args='PRIVATE_ARGS'),
            dict(type='tool-result', request_id='r1', tool_call_id='t1', monotonic_ms=52,
                result=dict(content=[dict(type='text', text=json.dumps(dict(schema='player-program-run/1',
                    program_id='version1', run_id='issuance1', status='yield', elapsed_seconds=.02,
                    final_state=dict(secret='PRIVATE_STATE'), operations=[dict(operation_id='op1',
                        actor_id=self.actor, session=self.session, source_id=self.source_id)], steps=[])))])),
            dict(type='settled', monotonic_ms=60, ok=True)]
        self.write_trace()
        self.selection = self.root / 'selection.json'
        self.selected = dict(schema='investigation-selection/1', cases=[dict(id='case-A', title='Failed case',
            directory='case', source_ids=[self.source_id])])
        self.put_selection()

    def put_receipt(self):
        (self.case / 'receipt.json').write_text(json.dumps(self.receipt))

    def put_selection(self):
        self.selection.write_text(json.dumps(self.selected))

    def write_trace(self):
        actor = self.case / 'actors' / '001'
        actor.mkdir(parents=True, exist_ok=True)
        (actor / 'host.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in self.events))

    def test_original_relationships_measured_durations_privacy_and_omissions(self):
        before = (self.case / 'session.sqlite3').read_bytes()
        bundle = export_selection(self.selection)
        self.assertIs(validate_bundle(bundle), bundle)
        case = bundle['cases'][0]
        encoded = json.dumps(bundle)
        for private in ('PRIVATE_', str(self.root), 'final_state', 'reasoning_format'):
            self.assertNotIn(private, encoded)
        request = next(e for e in case['events'] if e['kind'] == 'request')
        self.assertEqual((request['elapsed_ms'], request['start_wall_ms'], request['end_wall_ms']), (20, 1010, 1030))
        self.assertEqual(request['metrics']['first_content_ms'], 10)
        self.assertEqual(request['metrics']['reasoning_tokens'], 8)
        statement = next(e for e in case['events'] if e['kind'] == 'statement')
        self.assertEqual((len(statement['text']), statement['text_omitted_chars'], statement['original_omitted_bytes']), (4000, 5, 17))
        program = next(e for e in case['events'] if e['kind'] == 'program')
        operation = next(e for e in case['events'] if e['kind'] == 'operation')
        native = next(e for e in case['events'] if e['kind'] == 'native')
        self.assertEqual(program['run_id'], 'issuance1')
        self.assertEqual(program['program_id'], 'version1')
        self.assertIn(operation['id'], program['links'])
        self.assertEqual(native['native_id'], 'native1')
        self.assertEqual(native['operation_id'], 'op1')
        self.assertAlmostEqual(native['elapsed_ms'], 100)
        self.assertEqual(request['actor_id'], self.actor)
        self.assertIn('actors/001', request['id'])
        self.assertEqual(case['configuration'][0]['provider_only'], ['selected'])
        self.assertEqual(base64.b64decode(case['sources'][0]['png_base64']), self.png)
        self.assertEqual((self.case / 'session.sqlite3').read_bytes(), before)

    def test_closed_receipt_and_exact_selection_version_required(self):
        for field in ('deciding_hosts_quiescent', 'native_absence_verified', 'input_authority_revoked'):
            with self.subTest(field=field):
                self.receipt[field] = False
                self.put_receipt()
                with self.assertRaises(ControlError):
                    export_selection(self.selection)
                self.receipt[field] = True
        self.put_receipt()
        for change in (dict(schema='investigation-selection/0'), dict(raw_args={}), dict(cases=[])):
            self.selection.write_text(json.dumps({**self.selected, **change}))
            with self.assertRaises(ControlError):
                export_selection(self.selection)

    def test_png_corruption_geometry_missing_and_unknown_selection_are_explicit(self):
        png = self.case / 'sources' / (self.source_id + '.png')
        for data in (b'corrupt', self.png[:-8], b''):
            png.write_bytes(data)
            row = export_selection(self.selection)['cases'][0]['sources'][0]
            self.assertIsNone(row['png_base64'])
            self.assertTrue(row['unavailable_reason'])
        png.unlink()
        self.assertTrue(export_selection(self.selection)['cases'][0]['sources'][0]['unavailable_reason'])
        self.selected['cases'][0]['source_ids'] = [self.session + '-99']
        self.put_selection()
        row = export_selection(self.selection)['cases'][0]['sources'][0]
        self.assertIsNone(row['capture_id'])
        self.assertTrue(row['unavailable_reason'])

    def test_invalid_actor_clock_never_becomes_zero_or_shared_span(self):
        self.events[3]['monotonic_ms'] = 9
        self.write_trace()
        case = export_selection(self.selection)['cases'][0]
        request = next(e for e in case['events'] if e['kind'] == 'request')
        self.assertIsNone(request['elapsed_ms'])
        self.assertIsNone(request['start_wall_ms'])
        self.assertGreater(case['coverage']['invalid_clocks'], 0)

    def test_missing_original_endpoints_remain_censored_and_pending(self):
        self.events = [e for e in self.events if e['type'] not in ('response-complete', 'tool-result')]
        self.write_trace()
        rows = export_selection(self.selection)['cases'][0]['events']
        request = next(e for e in rows if e['kind'] == 'request')
        tool = next(e for e in rows if e['kind'] == 'tool')
        self.assertEqual((request['disposition'], tool['disposition']), ('censored', 'pending'))
        self.assertIsNone(request['elapsed_ms'])
        self.assertIsNone(tool['elapsed_ms'])
        self.assertIsNone(request['end_wall_ms'])
        self.assertIsNone(tool['end_wall_ms'])

    def test_strict_bundle_bounds_fields_and_nested_types(self):
        for mutate in (lambda b: b.update(schema='observer-investigation/2'),
                lambda b: b.update(path='/private'),
                lambda b: b['cases'][0]['events'][0].update(raw_args={}),
                lambda b: b['cases'][0]['events'][0]['metrics'].update(payload_bytes=-1),
                lambda b: b['cases'][0]['configuration'][0].update(model={}),
                lambda b: b['cases'][0]['configuration'][0].update(provider_only=['x'] * 33),
                lambda b: b['cases'][0]['events'][0].update(links=[{}]),
                lambda b: b['cases'][0]['sources'][0].update(width=99999)):
            bundle = export_selection(self.selection)
            mutate(bundle)
            with self.assertRaises(ControlError):
                validate_bundle(bundle)

    def test_exact_observer_join_and_invalid_clock_retained_without_span(self):
        observer = self.root / 'observer.json'
        row = dict(session=self.session, source_id=self.source_id, capture_id=1, presented_ms=1000,
            observed_at_wall_ms=1110, decode_finished_wall_ms=1120, dom_replaced_wall_ms=1130,
            outcome='displayed', error=None)
        data = dict(schema='observer-timing/4', retention_limit=2000, omitted_rows=3,
            clock='shared wall assumption', scope='DOM only', rows=[row])
        self.selected['cases'][0]['observer_exports'] = ['observer.json']
        self.put_selection()
        observer.write_text(json.dumps(data))
        case = export_selection(self.selection)['cases'][0]
        observed = next(e for e in case['events'] if e['kind'] == 'observer')
        self.assertEqual((observed['source_id'], observed['elapsed_ms']), (self.source_id, 130))
        self.assertTrue(any('3 omitted rows' in n for n in case['coverage']['notes']))
        row['dom_replaced_wall_ms'] = 990
        observer.write_text(json.dumps(data))
        observed = next(e for e in export_selection(self.selection)['cases'][0]['events'] if e['kind'] == 'observer')
        self.assertIsNone(observed['elapsed_ms'])
        self.assertIsNone(observed['start_wall_ms'])
        self.assertEqual(observed['disposition'], 'invalid_cross_clock_interval')
        data['schema'] = 'observer-timing/3'
        observer.write_text(json.dumps(data))
        with self.assertRaises(ControlError):
            export_selection(self.selection)

    def test_program_version_does_not_merge_distinct_runs_or_original_collection(self):
        projection = json.loads(self.events[6]['result']['content'][0]['text'])
        self.events.insert(-1, dict(type='tool-start', request_id='r1', tool_call_id='t2', monotonic_ms=53))
        self.events.insert(-1, dict(type='tool-result', request_id='r1', tool_call_id='t2', monotonic_ms=54,
            result=dict(content=[dict(type='text', text=json.dumps(dict(schema='player-service-result/1',
                value=projection, progress=dict(args='PRIVATE_ARGS'))))])))
        second = {**projection, 'run_id': 'issuance2'}
        self.events.insert(-1, dict(type='tool-start', request_id='r1', tool_call_id='t3', monotonic_ms=55))
        self.events.insert(-1, dict(type='tool-result', request_id='r1', tool_call_id='t3', monotonic_ms=56,
            result=dict(content=[dict(type='text', text=json.dumps(second))])))
        self.write_trace()
        rows = export_selection(self.selection)['cases'][0]['events']
        programs = [e for e in rows if e['kind'] == 'program']
        self.assertEqual([e['run_id'] for e in programs], ['issuance1', 'issuance2'])
        self.assertEqual({e['program_id'] for e in programs}, {'version1'})

    def test_png_budgets_digest_and_recorded_geometry_never_substitute(self):
        with patch('tools.investigation.MAX_RGBA_BYTES', 1):
            source = export_selection(self.selection)['cases'][0]['sources'][0]
        self.assertIsNone(source['png_base64'])
        self.assertIn('budget', source['unavailable_reason'])
        for changes in (dict(sha256='0' * 64), dict(width=3, window_width=3, viewport=[0, 0, 3, 3])):
            with sqlite3.connect(self.case / 'session.sqlite3') as db:
                db.execute('UPDATE sources SET metadata=?', (json.dumps({**self.metadata, **changes}),))
            source = export_selection(self.selection)['cases'][0]['sources'][0]
            self.assertIsNone(source['png_base64'])
            self.assertTrue(source['unavailable_reason'])

    def test_successor_collection_keeps_original_program_owner_and_children(self):
        projection = json.loads(self.events[6]['result']['content'][0]['text'])
        self.receipt['driver']['actors'][0]['actor_id'] = 'actor-successor'
        self.put_receipt()
        self.events[5]['tool'] = 'player_result'
        self.events[6]['result']['content'][0]['text'] = json.dumps(dict(
            schema='player-service-result/1', actor_id=self.actor, value=projection))
        self.write_trace()
        rows = export_selection(self.selection)['cases'][0]['events']
        program = next(e for e in rows if e['kind'] == 'program')
        tool = next(e for e in rows if e['kind'] == 'tool')
        self.assertEqual(program['actor_id'], self.actor)
        self.assertIn('operation:op1', program['links'])
        self.assertEqual(tool['actor_id'], 'actor-successor')

    def test_explicit_source_retrieval_keeps_original_image_link(self):
        self.events[5]['tool'] = 'player_source'
        self.events[6]['result']['content'][0]['text'] = json.dumps(dict(
            schema='player-source-read/1', source=self.metadata))
        self.write_trace()
        tool = next(e for e in export_selection(self.selection)['cases'][0]['events'] if e['kind'] == 'tool')
        self.assertEqual(tool['source_id'], self.source_id)
        self.assertIn('source:' + self.source_id, tool['links'])

    def test_program_authoring_id_is_available_without_code_or_service_as_computer_link(self):
        self.events[5]['tool'] = 'player_result'
        self.events[6]['result']['content'][0]['text'] = json.dumps(dict(
            schema='player-service-result/1', operation_id='authoring-request', value=dict(
                schema='player-program/1', id='version1', code='PRIVATE_CODE', actor_id=self.actor)))
        self.write_trace()
        tool = next(e for e in export_selection(self.selection)['cases'][0]['events'] if e['kind'] == 'tool')
        self.assertEqual(tool['program_id'], 'version1')
        self.assertIsNone(tool['operation_id'])
        self.assertNotIn('operation:authoring-request', tool['links'])
        self.assertNotIn('PRIVATE_CODE', json.dumps(tool))

    def test_duplicate_case_source_and_unknown_assessment_fields_reject(self):
        for change in (dict(source_ids=[self.source_id] * 2),
                dict(assessments=[dict(label='Review', text='claim', attribution='reviewer', reference='docs/report.md',
                    evidence_ids=['operation:op1'], raw_reasoning='PRIVATE_REASONING')])):
            self.selected['cases'][0].update(change)
            self.put_selection()
            with self.assertRaises(ControlError):
                export_selection(self.selection)
            self.selected['cases'][0].pop('assessments', None)
            self.selected['cases'][0]['source_ids'] = [self.source_id]
        self.selected['cases'] *= 2
        self.put_selection()
        with self.assertRaises(ControlError):
            export_selection(self.selection)

    def test_failed_html_generation_or_partial_publication_leaves_no_outputs(self):
        output, reader = self.root / 'bundle.json', self.root / 'reader.html'
        with patch('tools.investigation.html_document', side_effect=OSError('missing owned assets')):
            with self.assertRaises(OSError):
                write_export(self.selection, output, reader)
        self.assertFalse(output.exists())
        self.assertFalse(reader.exists())
        real_link = __import__('os').link
        def fail_second(source, destination):
            if Path(destination) == reader:
                raise OSError('injected publication failure')
            return real_link(source, destination)
        with patch('tools.investigation.html_document', return_value='fixture reader'), patch('tools.investigation.os.link', side_effect=fail_second):
            with self.assertRaises(ControlError):
                write_export(self.selection, output, reader)
        self.assertFalse(output.exists())
        self.assertFalse(reader.exists())
        self.assertEqual(list(self.root.glob('.investigation-*')), [])

    def test_bounded_complete_rows_and_total_encoded_limit(self):
        with patch('tools.investigation.MAX_EVENTS', 2):
            case = export_selection(self.selection)['cases'][0]
        self.assertEqual(case['coverage']['event_retained'], 2)
        self.assertGreater(case['coverage']['event_omitted'], 0)
        self.assertTrue(any('omitted' in n for n in case['coverage']['notes']))
        with patch('tools.investigation.MAX_BUNDLE_BYTES', 10), self.assertRaises(ControlError):
            export_selection(self.selection)

    def test_hostile_html_uses_same_assets_inert_data_and_no_network(self):
        bundle = export_selection(self.selection)
        bundle['cases'][0]['title'] = '</script><script>alert("owned")</script>\u2028'
        assets = self.root / 'web'
        assets.mkdir()
        for name, text in [('investigation.js', 'window.EnactiveInvestigation={mount(){return {}}};'),
                ('investigation-worker.js', '/*same worker*/'), ('investigation.css', '/*same CSS*/')]:
            (assets / name).write_text(text)
        with patch('tools.investigation.ROOT', self.root):
            html = html_document(bundle)
        self.assertNotIn('</script><script>alert', html)
        self.assertIn("connect-src 'none'", html_parser.unescape(html))
        self.assertIn('worker-src blob:', html)
        self.assertNotIn('Pause', html)
        self.assertIn('EnactiveInvestigation.mount', html)
        self.assertIn('same worker', html)

    def test_cli_requires_output_and_outputs_never_overwrite(self):
        output = self.root / 'bundle.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['investigation-export', str(self.selection), '--output', str(output)]), 0)
        self.assertEqual(json.loads(output.read_text())['schema'], 'observer-investigation/1')
        with self.assertRaises(ControlError):
            write_export(self.selection, output)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['investigation-export', str(self.selection)])
