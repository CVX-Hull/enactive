"""The memory screen's free checks on fixtures built here: a knowledge repository, a two-run lineage and the cut (#590)."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from harness.curator.knowledge import Repository
from tools.memory_screen_checks import (CutModel, ScheduleError, StoreError, check_schedule, covered_turns, cut_report,
    fact_history, main, read_lineage, read_versions, recorded_deliveries_for_run, render_replay, replay, schedule_coverage,
    schedule_from_runner, simulate, store_report, summarise, turn_starts)

SESSION = 'c' * 32
RECORD = '5' * 32
BASE = 4_000_000_000.0


def fact(identity: str, text: str, version: str, session: str, citations: list[str]) -> dict:
    return dict(schema='curator-fact/5', record='fact', id=identity, claim_kind='mechanic', text=text, scope=dict(game='cdda'), evidence_basis='observed', tags=['resource'],
        citations=citations, published_in=version, session=session)


def lines(*facts: dict) -> bytes:
    return ''.join(json.dumps(item) + '\n' for item in facts).encode()


def knowledge(root: Path, tank_frame: str) -> Path:
    """A repository at v2: v1 holds a recipe, v2 rewrites it and adds the tank. The first session read `run-a`."""
    repository = Repository(root, 'cdda')
    repository.ensure()
    recipe = fact('rod-recipe', 'A rod needs a stick.', 'v1', 'run-a-1', ['x-1'])
    repository.commit({'facts.jsonl': lines(recipe)}, 'Publish v1\n\nsession: run-a-1')
    repository.commit({'facts.jsonl': lines(dict(recipe, text='A rod needs a stick and a hook.'),
        fact('roof-tank', 'The roof tank holds 18 L of clean water.', 'v2', 'run-a-2', [tank_frame]))}, 'Publish v2\n\nsession: run-a-2')
    for session in ('run-a-1', 'run-a-2'):
        directory = repository.state / 'sessions' / session
        directory.mkdir(parents=True)
        (directory / 'manifest.json').write_text(json.dumps(dict(inputs=dict(trace_sessions=['run-a']))))
    return repository.path


class Trace:
    """One actor's host trace: each request makes one call, one second apart; an input returns a frame and an image."""

    def __init__(self, actor: str, start: float) -> None:
        self.actor, self.wall, self.requests, self.images, self.omitted = actor, start, 0, 0, 0
        self.events = [dict(type='host-start', schema='player-host/11', telemetry_version=11, session=SESSION,
            actor_id=actor, wall_time=self.iso(), monotonic_ms=0)]

    def iso(self) -> str:
        return datetime.fromtimestamp(self.wall, timezone.utc).isoformat()

    def call(self, tool: str, arguments: dict, result: dict, *, write: int = 1000) -> None:
        self.requests += 1
        self.wall += 1
        common = dict(wall_time=self.iso(), monotonic_ms=self.requests * 1000.0, request_id=f'request-{self.requests}')
        usage = dict(input=3, output=20, cacheRead=5000 * self.requests, cacheWrite=write, cost=dict(total=0.01, cacheWrite=0.001))
        self.events += [dict(common, type='context-image-projection', input_images=self.images, omitted_images=self.omitted),
            dict(common, type='request-start', logical_request_id=common['request_id']),
            dict(common, type='response-complete', stop_reason='toolUse', usage_available=True, usage=usage),
            dict(common, type='tool-start', tool_call_id='call', tool=tool, arguments=arguments),
            dict(common, type='tool-result', tool_call_id='call', tool=tool,
                result=dict(content=[dict(type='text', text=json.dumps(result))], isError=False))]

    def press(self) -> str:
        frame = f'{self.actor[:4]}-{self.requests + 1}'
        self.call('computer_input', dict(actions=[dict(type='key', key='e', modifiers=[])]),
            dict(operation_id=f'{len(self.events):032x}', source=dict(source_id=frame)))
        self.images += 1
        return frame

    def operate(self, *operations: str | None, collect: tuple[str, ...] = (), retry: float | None = None,
                failed: bool = False) -> None:
        """One request whose calls create `operations`, one `computer_input` call each, each returning an image (None:
        a result that names no operation), then collect the results of the operations in `collect` with
        `computer_result`. With `retry`, a first attempt starts that many seconds before the attempt that makes the
        calls. With `failed`, every result is an error."""
        self.requests += 1
        self.wall += 1
        logical = f'request-{self.requests}'
        common = dict(wall_time=self.iso(), monotonic_ms=self.requests * 1000.0, request_id=logical)
        usage = dict(input=3, output=20, cacheRead=5000 * self.requests, cacheWrite=1000, cost=dict(total=0.01, cacheWrite=0.001))
        if retry is not None:
            first = datetime.fromtimestamp(self.wall - retry, timezone.utc).isoformat()
            self.events.append(dict(common, wall_time=first, type='request-start', request_id=f'{logical}-first',
                logical_request_id=logical))
        self.events += [dict(common, type='context-image-projection', input_images=self.images, omitted_images=0),
            dict(common, type='request-start', logical_request_id=logical),
            dict(common, type='response-complete', stop_reason='toolUse', usage_available=True, usage=usage)]
        calls = [('computer_input', operation) for operation in operations] + [('computer_result', o) for o in collect]
        for number, (tool, operation) in enumerate(calls):
            self.events += [dict(common, type='tool-start', tool_call_id=f'call-{number}', tool=tool,
                    arguments=dict(actions=[dict(type='key', key='e', modifiers=[])]) if tool == 'computer_input'
                    else dict(operation_id=operation)),
                dict(common, type='tool-result', tool_call_id=f'call-{number}', tool=tool,
                    result=dict(content=[dict(type='text', text=json.dumps({} if operation is None else
                        dict(operation_id=operation)))], isError=failed))]
        self.images += len(operations)

    def write(self, directory: Path) -> None:
        directory.mkdir(parents=True)
        (directory / 'host.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in self.events))

    def deliver(self, kind: str, receiving: str | None, text: str, *, event_type: str = 'knowledge-delivery',
                **fields) -> None:
        self.events.append(dict(type=event_type, kind=kind, receiving_player_request_id=receiving, text=text, **fields))


def lineage(root: Path) -> tuple[list[Path], str, str]:
    """`run-a`: a first actor presses twice (the second frame shows the tank), writes a record and hands off; its
    successor presses three times. `run-b`: one actor presses four times; its third frame is where the fact is needed."""
    first, second, third = Trace('a' * 32, BASE), Trace('b' * 32, BASE + 100), Trace('d' * 32, BASE + 200)
    first.press()
    tank = first.press()
    first.call('player_memory_append', dict(record={}), dict(id=RECORD, kind='work'))
    first.call('player_handoff', dict(ids=[], summary='x'), dict(kind='handoff'))
    for _ in range(3):
        second.press()
    frames = [third.press() for _ in range(4)]
    first.write(root / 'run-a' / 'actors' / '001')
    second.write(root / 'run-a' / 'actors' / '002')
    third.write(root / 'run-b' / 'actors' / '001')
    return [root / 'run-a', root / 'run-b'], tank, frames[2]


def test_store_reads_each_version_and_changes_nothing(tmp_path):
    repository = knowledge(tmp_path / 'knowledge', 'aaaa-2')
    before = sorted((str(path), path.stat().st_mtime_ns) for path in repository.rglob('*'))
    versions = read_versions(repository)
    assert [(v['version'], len(v['facts']), v['bytes']) for v in versions] == [('v0', 0, 0),
        ('v1', 1, len(lines(fact('rod-recipe', 'A rod needs a stick.', 'v1', 'run-a-1', ['x-1'])))), ('v2', 2, versions[2]['bytes'])]
    history = fact_history(versions, 'rod-recipe')
    assert (history['version'], history['changed_in'], history['dropped_in']) == ('v1', ['v2'], None)
    assert history['text'] == 'A rod needs a stick.' and history['latest_text'].endswith('a hook.')
    assert fact_history(versions, 'cupboard') is None
    report, = store_report([repository], ['tank=tank|roof', 'rations=ration'], [])
    assert [(row['version'], row['covers'], row['added'], row['changed']) for row in report['versions'][1:]] == [
        ('v1', ['run-a'], 1, []), ('v2', ['run-a'], 1, ['rod-recipe'])]
    assert [found['id'] for found in report['found']['tank']] == ['roof-tank'] and report['found']['rations'] == []
    assert before == sorted((str(path), path.stat().st_mtime_ns) for path in repository.rglob('*'))
    (repository / '.git' / 'refs' / 'tags' / 'v3').write_text('0' * 40 + '\n')
    with pytest.raises(StoreError, match='not a loose object'):  # as a packed repository would be
        read_versions(repository)


def test_replay_places_the_need_the_record_and_the_fact(tmp_path):
    runs, tank, need = lineage(tmp_path)
    repository = knowledge(tmp_path / 'knowledge', tank)
    _, actors = read_lineage(runs)
    assert [(a.run, a.name, a.first, a.requests, a.successor) for a in actors] == [('run-a', '001', 1, 4, False),
        ('run-a', '002', 5, 3, True), ('run-b', '001', 8, 4, False)]
    row, = replay(runs, [f'tank:need={need},record=5555,fact=roof-tank'], None, repository, [1, 47])
    assert (row['need']['run'], row['need']['request'], row['need']['lineage_request']) == ('run-b', 3, 10)
    record = row['record']
    assert (record['written']['lineage_request'], record['first_briefing']['lineage_request']) == (3, 5)
    assert (record['briefing_to_needing_actor']['lineage_request'], record['requests_before_need']) == (8, 2)
    assert record['recorded'] is None  # no read or handoff gave it to an actor from the needing one on
    entry = row['fact']
    assert entry['estimate'] == 'publication timing only'
    assert entry['estimate'] in render_replay([row])
    assert (entry['version'], entry['covers'], entry['first_cited']['lineage_request']) == ('v2', ['run-a'], 2)
    assert entry['at_admission_boundaries']['lineage_request'] == 8 and entry['boundary_before_need']
    assert [(e['lag'], e['lineage_request']) for e in entry['with_handoff_sessions']] == [(1, 6), (47, 7)]
    with pytest.raises(ValueError, match='not returned by any call'):
        replay(runs, ['x:need=nope-1'], None, None, [])


def test_cut_frees_only_covered_turns():
    images = list(range(60))  # every turn carries one image
    model = CutModel()
    plain = simulate(images, model, None)
    assert [plain[i]['prompt'] for i in (0, 1, 39)] == [4500, 5450, 4500 + 39 * 950]
    assert [plain[i]['write'] for i in (0, 1)] == [4500, 950]
    assert [i for i, row in enumerate(plain) if row['image_drop']] == [40]  # the 40th image: a block of 20 goes
    assert plain[40] == dict(prompt=42500 - 20 * 658, freed=None, image_drop=True, rewrite=True,
        write=42500 - 20 * 658 - 3900)
    kept_up = simulate(images, model, 10)
    assert kept_up[40] == dict(prompt=42500 - 24 * 950, freed=24, image_drop=False, rewrite=True,
        write=42500 - 24 * 950 - 3900)
    assert not any(row['image_drop'] for row in kept_up)
    behind = simulate(images, model, 47)
    assert (behind[40]['freed'], behind[40]['image_drop'], behind[40]['prompt']) == (0, True, plain[40]['prompt'])
    assert simulate(images, CutModel(min_free=30), 10)[40]['freed'] == 0  # a cut that would free too little is not made
    waiting = summarise('x', [simulate(list(range(80)), CutModel(high_mark=30000, image_peak=99), 60)], 1.0)
    # over the mark from request 28: nothing is covered until turn 61, then every request frees the one turn newly covered
    assert (waiting['cuts_held_back'], waiting['requests_held_back'], waiting['cuts'], waiting['cuts_under_ten_turns']) == (1, 34, 19, 19)
    assert waiting['rewritten'] == sum(row['write'] for row in simulate(list(range(80)), CutModel(high_mark=30000, image_peak=99), 60)
        if row['rewrite'])
    assert (covered_turns(45, 10, 'steady'), covered_turns(45, 10, 'sessions'), covered_turns(5, 10, 'sessions')) == (35, 30, 0)


def test_cut_report_and_the_command(tmp_path, capsys):
    runs, tank, need = lineage(tmp_path)
    report = cut_report(runs, CutModel(), [10])
    recorded, plain, lagged = report['rows']
    assert (recorded['row'], recorded['requests'], recorded['cache_write'], recorded['image_drops']) == ('recorded', 11, 11000, 0)
    assert recorded['prompt_max'] == 3 + 5000 * 4 + 1000
    assert (plain['row'], plain['requests'], plain['prompt_max'], plain['cuts']) == ('no cut', 11, 4500 + 3 * 950, 0)
    first_actor = simulate([0, 1, 2, 2], CutModel(), None)  # two frames, then a call that returns no image
    assert [row['prompt'] for row in first_actor] == [4500, 5450, 6400, 6400 + 192]
    assert lagged == dict(plain, row='lag 10')  # nothing reaches a mark in so short a lineage
    repository = knowledge(tmp_path / 'knowledge', tank)
    assert main(['store', str(repository), '--find', 'tank=tank', '--runs', str(tmp_path / 'run-a')]) == 0
    assert 'roof-tank (mechanic) first in v2 by run-a-2' in capsys.readouterr().out
    assert main(['replay', *map(str, runs), '--loss', f'tank:need={need},fact=roof-tank', '--knowledge', str(repository)]) == 0
    assert 'sessions at admission boundaries only: briefing at run-b/001 request 1 of 4' in capsys.readouterr().out
    assert main(['cut', *map(str, runs), '--lags', '10', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['model']['turn_tokens'] == 950


# R-REGRESSION: fixtures check the cut's token thresholds and delivery accounting without running the game.
def test_cut_marks_count_tokens_above_the_briefing():
    images = list(range(57))
    model = CutModel(head_tokens=5000, turn_tokens=1000, high_mark=60000, low_mark=20000, image_peak=99)
    plain = simulate(images, model, 1)
    briefed = simulate(images, model, 1, briefing_tokens=10000)
    static = replace(model, briefing_tokens=10000)
    assert simulate(images, static, 1) == briefed
    assert simulate(images, static, 1, briefing_tokens=0) == plain
    assert all(row['freed'] is None for row in briefed[:56])
    assert (plain[55]['prompt'], briefed[55]['prompt']) == (60000, 70000)
    assert (plain[56]['freed'], briefed[56]['freed']) == (41, 41)
    assert (plain[56]['prompt'], briefed[56]['prompt']) == (20000, 30000)


def test_first_request_delivery_adds_to_initial_prompt_and_cache_write():
    model = CutModel()
    rows = simulate([0, 1], model, None, delivery_tokens=[17, 0])
    assert [(row['prompt'], row['write']) for row in rows] == [(4517, 4517), (5467, 950)]
    with pytest.raises(ValueError, match='one entry per request'):
        simulate([0, 1], model, None, delivery_tokens=[17])


def test_recorded_briefings_start_fresh_at_handoff(tmp_path):
    run = tmp_path / 'run'
    first, successor = Trace('a' * 32, BASE), Trace('b' * 32, BASE + 100)
    first.deliver('briefing', 'request-1', 'x' * 120, version='v0')
    first.call('player_handoff', dict(summary='Continue the task.'), dict(kind='handoff'))
    first.write(run / 'actors' / '001')
    successor.deliver('briefing', 'request-1', 'é' * 16000, version='v3')
    successor.operate('successor-op')
    successor.write(run / 'actors' / '002')

    report = cut_report([run], CutModel(), [10], recorded_deliveries=True)
    assert report['deliveries'] == dict(bytes_per_token=4, briefing_tokens_by_actor={'001': 30, '002': 8000},
        update_count=0, update_tokens=0, reminder_count=0, reminder_tokens=0, unmatched_deliveries=0)
    _, plain, lagged = report['rows']
    assert (plain['prompt_p50'], plain['prompt_max'], plain['cache_write']) == (4530, 12500, 17030)
    assert lagged == dict(plain, row='lag 10')


def test_deliveries_use_the_player_turn_of_a_retried_attempt(tmp_path):
    trace = Trace('a' * 32, BASE)
    trace.operate('first')
    trace.deliver('update', 'request-2', 'abcde', outcome='delivered')
    trace.events.append(dict(type='request-start', request_id='request-2', logical_request_id='request-2'))
    trace.events.append(dict(type='request-start', request_id='request-3', logical_request_id='request-2'))
    trace.deliver('reminder', 'request-4', 'abc')
    trace.events.append(dict(type='request-start', request_id='request-4', logical_request_id='request-4'))
    run_dir = tmp_path / 'run'
    trace.write(run_dir / 'actors' / '001')
    run, = read_lineage([run_dir])[0]
    briefing, extras, counts = recorded_deliveries_for_run(run)[trace.actor]
    assert (briefing, extras) == (0, [0, 2, 1])
    assert counts == dict(update_count=1, update_tokens=2, reminder_count=1, reminder_tokens=1, unmatched_deliveries=0)


def test_recorded_deliveries_are_written_at_the_receiving_request_and_cut_with_it(tmp_path, capsys):
    trace = Trace('a' * 32, BASE)
    trace.deliver('briefing', 'request-1', 'x' * 120, version='v0')
    trace.operate('op-1')
    trace.deliver('update', 'request-2', 'é' * 201, outcome='delivered', previous_version='v0', version='v1')
    trace.operate('op-2')
    trace.deliver('update', 'request-3', 'x' * 4000, outcome='refused')
    trace.operate('op-3')
    trace.deliver('update', 'request-4', 'x' * 4000, outcome='delivered', event_type='knowledge-undelivered')
    trace.operate('op-4')
    trace.deliver('reminder', 'request-5', 'r' * 801, version='v1')
    trace.operate('op-5')
    trace.operate('op-6')
    trace.deliver('update', 'request-7', 'x' * 4000, outcome='delivered')
    trace.events.append(dict(type='request-start', request_id='recall-1', request_role='recall'))
    trace.deliver('reminder', 'recall-1', 'x' * 4000)
    run_dir = tmp_path / 'run'
    trace.write(run_dir / 'actors' / '001')
    run, = read_lineage([run_dir])[0]
    briefing, extras, counts = recorded_deliveries_for_run(run)[trace.actor]
    assert (briefing, extras) == (30, [0, 101, 0, 0, 201, 0])
    assert counts == dict(update_count=1, update_tokens=101, reminder_count=1, reminder_tokens=201, unmatched_deliveries=2)

    model = CutModel(coverage='schedule', high_mark=9500, low_mark=6400)
    coverage = schedule(change(BASE + 5.5, '001', 4, 'op-4'))
    limits, = covered(run_dir, *coverage['changes'])[0].values()
    assert limits == [0, 0, 0, 0, 0, 4]
    rows = simulate(list(range(6)), model, None, limits, briefing_tokens=briefing, delivery_tokens=extras)
    assert [(row['prompt'], row['write']) for row in rows] == [
        (4530, 4530), (5581, 1051), (6531, 950), (7481, 950), (8632, 1151), (5480, 1580)]
    assert [row['freed'] for row in rows] == [None, None, None, None, None, 4]

    path = tmp_path / 'schedule.json'
    path.write_text(json.dumps(coverage))
    args = ['cut', str(run_dir), '--coverage', 'schedule', '--schedule', str(path), '--high-mark', '9500',
            '--low-mark', '6400', '--recorded-deliveries']
    assert main([*args, '--json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == cut_report([run_dir], model, [], coverage, recorded_deliveries=True)
    assert report['deliveries'] == dict(bytes_per_token=4, briefing_tokens_by_actor={'001': 30}, **counts)
    baseline = cut_report([run_dir], model, [], coverage)
    assert 'deliveries' not in baseline and baseline['rows'][0] == report['rows'][0]
    _, plain, cut = report['rows']
    assert (plain['prompt_max'], plain['cache_write']) == (9582, 9582)
    assert (cut['prompt_max'], cut['cache_write'], cut['cuts'], cut['rewritten']) == (8632, 10212, 1, 1580)
    assert baseline['rows'][2]['cuts'] == 0
    assert main(args) == 0
    output = capsys.readouterr().out
    assert 'recorded deliveries (4 bytes per token) | updates 1 (101 tokens) | reminders 1 (201 tokens)' in output
    assert '2 without a matching player request' in output
    assert 'briefing tokens by actor: 001 = 30' in output


def test_recorded_deliveries_refuse_a_nonzero_static_briefing(tmp_path, capsys):
    run = admission(tmp_path, [['op-1']])
    conflict = '--recorded-deliveries requires --briefing-tokens to be zero'
    with pytest.raises(ScheduleError, match=conflict):
        cut_report([run], CutModel(briefing_tokens=5000), [10], recorded_deliveries=True)
    with pytest.raises(SystemExit) as error:
        main(['cut', str(run), '--recorded-deliveries', '--briefing-tokens', '5000'])
    assert error.value.code == 2
    result = capsys.readouterr()
    assert not result.out and conflict in result.err
    assert main(['cut', str(run), '--recorded-deliveries', '--briefing-tokens', '0']) == 0


def article(identity='article', title='A subject', **extra):
    return dict(schema='curator-fact/5', record='article', id=f'{identity}@v3', slug=identity, title=title, lead='A hypothesis.',
                body=[dict(text='A claim.', facts=['roof-tank'])], links=[], published_in='v3', session='groom', **extra)


def test_store_reports_fact_and_article_totals_current_counts_and_bytes_per_version(tmp_path, capsys):
    path = knowledge(tmp_path/'knowledge', 'aaaa-2')
    repo = Repository(path.parent, path.name)
    old = repo.facts()
    groomed = [dict(old[0], retired=dict(reason='contradicted')), old[1], article()]
    repo.commit({'facts.jsonl': lines(*groomed)}, 'grooming\n\nsession: groom')
    versions = read_versions(path)
    assert len(versions[-1]['facts']) == 2 and len(versions[-1]['articles']) == 1
    assert fact_history(versions, 'article') is None
    report, = store_report([path], ['found=18 L', 'article=A subject'], [])
    assert [(r['facts'], r['articles'], r['current_facts'], r['current_articles'], r['bytes'])
            for r in report['versions']] == [(0, 0, 0, 0, 0),
                (1, 0, 1, 0, versions[1]['bytes']), (2, 0, 2, 0, versions[2]['bytes']),
                (2, 1, 1, 1, len(lines(*groomed)))]
    assert report['versions'][-1]['session'] == 'groom'  # article-only publication has a session
    assert report['found']['found'][0]['text'] == 'The roof tank holds 18 L of clean water.'
    assert report['found']['article'] == []
    assert main(['store', str(path), '--find', 'found=18 L']) == 0
    text = capsys.readouterr().out
    assert '2 facts (1 current), 1 articles (1 current)' in text and '18 L of clean water.' in text
    assert main(['store', str(path), '--json']) == 0
    assert json.loads(capsys.readouterr().out)[0]['versions'][-1]['articles'] == 1


@pytest.mark.parametrize('schema', ['curator-fact/1', 'curator-fact/2', 'curator-fact/3', 'curator-fact/4', None])
@pytest.mark.parametrize('command', ['store', 'replay'])
def test_memory_readers_refuse_other_record_schemas(tmp_path, schema, command):
    runs, tank, need = lineage(tmp_path)
    repo = Repository(tmp_path/'knowledge', 'cdda')
    repo.ensure()
    invalid = dict(fact('f', 'x', 'v1', 's', [tank]), schema=schema)
    repo.commit({'facts.jsonl': lines(invalid)}, 'unsupported record')
    with pytest.raises(StoreError, match='unsupported record schema; expected curator-fact/5'):
        if command == 'store':
            store_report([repo.path], [], [])
        else:
            replay(runs, [f'x:need={need},fact=f'], None, repo.path, [])


@pytest.mark.parametrize('schema', ['curator-knowledge/1', 'curator-knowledge/2', 'curator-knowledge/3', None])
def test_memory_reader_refuses_other_repository_layouts(tmp_path, schema):
    repo = Repository(tmp_path/'knowledge', 'cdda')
    repo.ensure()
    repo.commit({'knowledge.json': json.dumps(dict(schema=schema, game='cdda')).encode()}, 'unsupported layout')
    with pytest.raises(StoreError, match='expected curator-knowledge/4; start a new repository'):
        read_versions(repo.path)


def test_replay_uses_fact_text_and_does_not_treat_an_article_as_a_fact(tmp_path):
    runs, tank, need = lineage(tmp_path)
    path = knowledge(tmp_path/'knowledge', tank)
    repo = Repository(path.parent, path.name)
    repo.commit({'facts.jsonl': lines(*repo.facts(), article())}, 'article')
    row, = replay(runs, [f'x:need={need},fact=roof-tank'], None, path, [])
    assert row['fact']['text'] == 'The roof tank holds 18 L of clean water.'
    with pytest.raises(ValueError, match='fact article is in no version'):
        replay(runs, [f'x:need={need},fact=article'], None, path, [])


@pytest.mark.parametrize('record', [None, 'type', ''])
def test_memory_reader_refuses_unknown_record_discriminators(tmp_path, record):
    repo = Repository(tmp_path/'knowledge', 'cdda')
    repo.ensure()
    repo.commit({'facts.jsonl': lines(dict(article(), record=record))}, 'unknown discriminator')
    with pytest.raises(StoreError, match='unsupported record kind; expected fact or article'):
        read_versions(repo.path)


@pytest.mark.parametrize('metadata', [None, b'{', b'\xff'], ids=['missing', 'invalid-json', 'invalid-encoding'])
def test_memory_reader_refuses_missing_or_unparseable_knowledge_metadata(tmp_path, metadata):
    repo = Repository(tmp_path/'knowledge', 'cdda')
    repo.ensure()
    if metadata is None:
        (repo.path/'knowledge.json').unlink()
        files = {}
    else:
        files = {'knowledge.json': metadata}
    repo.commit(files, 'invalid metadata fixture')
    with pytest.raises(StoreError, match='unsupported knowledge schema:.*start a new repository'):
        read_versions(repo.path)


@pytest.mark.parametrize('operation', ['retag-only', 'retire-only'])
def test_store_uses_the_commit_session_when_a_version_adds_no_record(tmp_path, operation):
    path = knowledge(tmp_path/'knowledge', 'frame')
    repo = Repository(path.parent, path.name)
    records = repo.records()
    if operation == 'retag-only':
        records[0].update(tags=['storage'], retagged=[dict(version='v3', **{'from': ['resource'], 'to': ['storage']})])
    else:
        records[0]['retired'] = dict(reason='contradicted', session=operation, published_in='v3')
    repo.commit({'facts.jsonl': lines(*records)}, f'Publish v3: {operation}\n\nsession: {operation}\nsubmission: fixture')
    manifest = repo.state/'sessions'/operation/'manifest.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(dict(inputs=dict(trace_sessions=['run-b']))))
    versions = read_versions(path)
    assert len(versions[-1]['facts']) == len(versions[-2]['facts']) == 2
    assert not any(r.get('published_in') == 'v3' for r in versions[-1]['facts'])
    assert versions[-1]['session'] == operation
    report, = store_report([path], [], [])
    assert report['versions'][-1]['session'] == operation
    assert report['versions'][-1]['covers'] == ['run-b']


# --- a recorded coverage schedule (R-REGRESSION: the replay that reads the paid live curator run's lag result) ------

MARKED = dict(high_mark=30000, image_peak=99)  # cuts fall due from request 28 of a long actor


def admission(root: Path, *actors: list[list[str]], gap: float = 100) -> Path:
    """A run whose actors (`001`, `002`, ...) start `gap` seconds apart; each request is the operations its calls create."""
    run = root / 'run'
    for position, requests in enumerate(actors):
        trace = Trace(chr(ord('a') + position) * 32, BASE + position * gap)
        for operations in requests:
            trace.operate(*operations)
        trace.write(run / 'actors' / f'{position + 1:03d}')
    return run


def change(wall: float, actor: str | None = None, step: int = 0, operation: str = '', restore: bool = False) -> dict:
    return dict(wall=wall, end=None if actor is None else dict(actor=actor, step=step, operation=operation), restore=restore)


def schedule(*changes: dict) -> dict:
    return dict(schema='curator-coverage-schedule/1', changes=list(changes))


def covered(path: Path, *changes: dict) -> tuple[dict[str, list[int]], int]:
    run, = read_lineage([path])[0]
    by_actor, left_out = schedule_coverage(run, check_schedule(schedule(*changes), run.directories), turn_starts(run))
    return {run.directories[run.facts.actors.index(actor)]: limits for actor, limits in by_actor.items()}, left_out


@pytest.mark.parametrize('lag', [10, 25])
def test_a_schedule_equal_to_a_steady_coverage_reproduces_the_steady_rows(tmp_path, capsys, lag):
    run = admission(tmp_path, [[f'op-{n}'] for n in range(1, 81)])
    # turn n is covered from the request that starts after request n + lag began, as steady coverage covers t - lag
    path = tmp_path / 'schedule.json'
    path.write_text(json.dumps(schedule(change(BASE), *(change(BASE + n + lag + 0.5, '001', n, f'op-{n}')
        for n in range(1, 81)))))
    steady = cut_report([run], CutModel(**MARKED), [lag])
    assert steady['rows'][2]['cuts'] > 0
    assert main(['cut', str(run), '--coverage', 'schedule', '--schedule', str(path), '--high-mark', '30000',
                 '--image-peak', '99', '--json']) == 0
    replayed = json.loads(capsys.readouterr().out)
    assert [row['row'] for row in replayed['rows']] == ['recorded', 'no cut', 'schedule']
    assert replayed['rows'] == [*steady['rows'][:2], dict(steady['rows'][2], row='schedule')]
    assert replayed['schedule'] == dict(read=81, applied=81, left_out=0)
    lineage, _ = read_lineage([run])
    images = [lineage[0].facts.images[(r.actor, r.key)] for r in lineage[0].facts.requests]
    limits, = covered(run, *json.loads(path.read_text())['changes'])[0].values()
    assert simulate(images, CutModel(**MARKED, coverage='schedule'), None, limits) == simulate(images, CutModel(**MARKED), lag)
    assert main(['cut', str(run), '--coverage', 'schedule', '--schedule', str(path)]) == 0
    assert 'schedule: 81 changes read, 81 applied, 0 left out' in capsys.readouterr().out


def test_a_schedule_that_stops_advancing_holds_the_cut_back(tmp_path):
    run = admission(tmp_path, [[f'op-{n}'] for n in range(1, 81)])
    stalled = schedule(change(BASE), *(change(BASE + n + 10.5, '001', n, f'op-{n}') for n in range(1, 21)))
    row = cut_report([run], CutModel(**MARKED, coverage='schedule'), [], stalled)['rows'][2]
    assert cut_report([run], CutModel(**MARKED), [10])['rows'][2]['requests_held_back'] == 0
    assert row['cuts'] > 0 and row['requests_held_back'] > 0 and row['cuts_held_back'] >= 1
    lineage, _ = read_lineage([run])
    images = [lineage[0].facts.images[(r.actor, r.key)] for r in lineage[0].facts.requests]
    limits, = covered(run, *stalled['changes'])[0].values()
    assert limits[-1] == 20
    rows = simulate(images, CutModel(**MARKED, coverage='schedule'), None, limits)
    assert rows[-1]['freed'] == 0 and rows[-1]['prompt'] > MARKED['high_mark']


def test_a_prefix_covers_a_turn_only_whole_and_applies_after_its_time(tmp_path):
    run = admission(tmp_path, [['a1'], ['b1', 'b2'], ['c1'], ['d1']])  # requests start at BASE + 1 .. BASE + 4
    assert covered(run, change(BASE + 3.5, '001', 2, 'b1')) == ({'001': [0, 0, 0, 1]}, 0)
    assert covered(run, change(BASE + 3.5, '001', 3, 'b2')) == ({'001': [0, 0, 0, 2]}, 0)
    # a change at exactly a request's start applies from the next request; a restore moves the prefix back
    assert covered(run, change(BASE + 2, '001', 1, 'a1'), change(BASE + 3.5, '001', 4, 'c1'),
                   change(BASE + 3.75, '001', 1, 'a1', restore=True)) == ({'001': [0, 0, 1, 1]}, 0)


def test_a_request_with_no_start_time_takes_the_coverage_before_it(tmp_path):
    run = admission(tmp_path, [['a1'], ['b1'], ['c1'], ['d1']])
    host = run / 'actors' / '001' / 'host.jsonl'
    events = [json.loads(line) for line in host.read_text().splitlines()]
    for event in events:
        if event['type'] == 'request-start' and event['request_id'] == 'request-3':
            del event['wall_time']
    host.write_text(''.join(json.dumps(event) + '\n' for event in events))
    assert covered(run, change(BASE + 1.5, '001', 1, 'a1'), change(BASE + 2.5, '001', 2, 'b1')) == (
        {'001': [0, 1, 1, 2]}, 0)


def test_actors_before_the_prefix_are_covered_and_actors_after_it_are_not(tmp_path):
    run = admission(tmp_path, *([[f'{actor}-{n}'] for n in range(1, 4)] for actor in ('x', 'y', 'z')))
    assert covered(run, change(BASE + 0.5, '002', 2, 'y-2')) == ({'001': [3, 3, 3], '002': [2, 2, 2], '003': [0, 0, 0]}, 0)
    assert covered(run, change(BASE + 0.5)) == ({'001': [0, 0, 0], '002': [0, 0, 0], '003': [0, 0, 0]}, 0)


def test_an_operation_no_result_places_is_left_out_and_counted(tmp_path):
    run = admission(tmp_path, [['a1'], ['b1'], ['c1'], ['d1']])
    changes = (change(BASE + 0.5, '001', 1, 'a1'), change(BASE + 1.5, '001', 2, 'unknown'),
               change(BASE + 2.5, '001', 3, 'not-in-any-result'))
    assert covered(run, *changes) == ({'001': [1, 1, 1, 1]}, 2)
    report = cut_report([run], CutModel(coverage='schedule'), [], schedule(*changes))
    assert report['schedule'] == dict(read=3, applied=1, left_out=2)


@pytest.mark.parametrize('value, refusal', [
    (dict(schema='curator-coverage-schedule/2', changes=[]), 'unsupported coverage schedule schema'),
    (dict(changes=[]), 'unsupported coverage schedule schema'),
    (dict(schema='curator-coverage-schedule/1'), 'no list of changes'),
    (schedule({k: v for k, v in change(BASE).items() if k != 'wall'}), 'change 1: wall is missing'),
    (schedule(change('soon')), 'change 1: wall is missing or not a number'),
    (schedule(change(True)), 'change 1: wall is missing or not a number'),
    (schedule({k: v for k, v in change(BASE).items() if k != 'restore'}), 'change 1: restore is missing'),
    (schedule(change(BASE, restore='no')), 'change 1: restore is missing'),
    (schedule({k: v for k, v in change(BASE).items() if k != 'end'}), 'change 1: end is missing'),
    (schedule(change(BASE, '001', '2', 'a1')), 'change 1: end is missing or not null'),
    (schedule(dict(change(BASE), end=dict(actor='001', step=2))), 'change 1: end is missing or not null'),
    (schedule(change(BASE), change(BASE - 1)), 'change 2: its time is earlier'),
    (schedule(change(BASE, '001', 2, 'b1'), change(BASE + 1, '001', 1, 'a1')), 'change 2: the covered prefix moves backwards'),
    (schedule(change(BASE, '002', 1, 'x'), change(BASE + 1, '001', 9, 'y')), 'change 2: the covered prefix moves backwards'),
    (schedule(change(BASE, '001', 1, 'a1'), change(BASE + 1)), 'change 2: the covered prefix moves backwards'),
    (schedule(change(BASE, '003', 1, 'a1')), 'change 1: actor 003 is not an actor of the run'),
    (schedule(change(BASE, '001', 0, 'a1')), 'change 1: step 0 is below one'),
])
def test_a_malformed_or_out_of_order_schedule_is_refused(value, refusal):
    with pytest.raises(ScheduleError, match=refusal):
        check_schedule(value, ['001', '002'])


def test_a_backward_prefix_with_a_restore_is_accepted_and_a_schedule_is_given_over_one_run(tmp_path):
    changes = [change(BASE, '002', 1, 'x'), change(BASE, '001', 1, 'a1', restore=True), change(BASE + 1)]
    assert check_schedule(schedule(*changes[:2]), ['001', '002']) == changes[:2]
    with pytest.raises(ScheduleError, match='change 3: the covered prefix moves backwards'):
        check_schedule(schedule(*changes), ['001', '002'])
    runs, _, _ = lineage(tmp_path)
    with pytest.raises(ScheduleError, match='exactly one run; 2 were given'):
        cut_report(runs, CutModel(coverage='schedule'), [], schedule())
    with pytest.raises(ScheduleError, match='only with it'):
        cut_report(runs[:1], CutModel(), [], schedule())
    with pytest.raises(ScheduleError, match='only with it'):
        cut_report(runs[:1], CutModel(coverage='schedule'), [])


def runner_files(run: Path, polls: list[dict], status: dict, tail: str = '') -> Path:
    directory = run / 'curator-runner'
    directory.mkdir()
    (directory / 'polls.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in polls) + tail)
    (directory / 'status.json').write_text(json.dumps(status, indent=1))
    return directory


def poll(wall: float, end: dict | None, restore: dict | None = None, outcome: str = 'read') -> dict:
    return dict(schema='curator-runner-poll/1', began_wall=wall - 0.5, ended_wall=wall, outcome=outcome,
        coverage=dict(covered_prefix=dict(end=end, restore=restore), lag='unknown', backlog=0, as_of='unknown'))


def test_the_schedule_command_writes_the_runner_record_as_a_schedule(tmp_path):
    run = admission(tmp_path, [['a1'], ['b1', 'b2'], ['c1']])
    b2 = dict(actor='001', step=3, operation='b2', ordinal=3)
    restore = dict(version='v4', restored='v2', counted_through='v2')
    status = dict(schema='curator-runner-status/1', state='ended', updated_wall=BASE + 5, lag='unknown',
        covered_prefix=dict(end=dict(actor='001', step=1, operation='a1', ordinal=1), restore=restore))
    directory = runner_files(run, [poll(BASE + 1, None), poll(BASE + 2, None), poll(BASE + 3, b2),
        poll(BASE + 4, b2, outcome='failed')], status, tail='{"schema": "curator-runner-poll/1", "ended')
    before = (directory / 'polls.jsonl').read_bytes()
    # the restore first shown by the status file is timed by the last poll, which did not show it
    expected = schedule(change(BASE + 1), change(BASE + 3, '001', 3, 'b2'), change(BASE + 4, '001', 1, 'a1', restore=True))
    assert schedule_from_runner(run) == expected
    output = tmp_path / 'schedule.json'
    assert main(['schedule', str(run), '--output', str(output)]) == 0
    assert json.loads(output.read_text()) == expected
    assert (directory / 'polls.jsonl').read_bytes() == before  # the half-written row is not read and not cut off


@pytest.mark.parametrize('polls, refusal', [
    ([dict(poll(BASE, None), schema='curator-runner-poll/2')], 'polls.jsonl row 1: unsupported schema'),
    ([{k: v for k, v in poll(BASE, None).items() if k != 'coverage'}], 'polls.jsonl row 1: no ended_wall and covered prefix'),
    ([poll(BASE, None), {k: v for k, v in poll(BASE, None).items() if k != 'ended_wall'}], 'row 2: no ended_wall'),
    ([poll(BASE + 1, None), poll(BASE, dict(actor='001', step=1, operation='a1', ordinal=1))], 'change 2: its time is earlier'),
    ([poll(BASE + 1, None), dict(poll(BASE + 2, None), ended_wall='later')], 'row 2: ended_wall is not a number'),
])
def test_the_schedule_command_refuses_runner_files_it_cannot_read(tmp_path, polls, refusal):
    run = admission(tmp_path, [['a1']])
    runner_files(run, polls, dict(schema='curator-runner-status/1', updated_wall=BASE + 9,
        covered_prefix=dict(end=None, restore=None)))
    with pytest.raises(ScheduleError, match=refusal):
        schedule_from_runner(run)


def single(root: Path, *requests: tuple[tuple, dict]) -> Path:
    """A run of one actor `001`; each request is the arguments and options of `Trace.operate`."""
    trace = Trace('a' * 32, BASE)
    for operations, options in requests:
        trace.operate(*operations, **options)
    trace.write(root / 'run' / 'actors' / '001')
    return root / 'run'


def test_collecting_an_earlier_operation_does_not_make_a_partial_turn_whole(tmp_path):
    run = single(tmp_path, (('a1',), {}), (('A', 'B'), dict(collect=('A',))), (('c1',), {}))
    assert covered(run, change(BASE + 2.5, '001', 2, 'A')) == ({'001': [0, 0, 1]}, 0)
    assert covered(run, change(BASE + 2.5, '001', 3, 'B')) == ({'001': [0, 0, 2]}, 0)


def test_only_a_creating_call_that_did_not_fail_places_an_operation(tmp_path):
    # request 1's input names no operation and request 2 only collects one; request 3's input failed
    run = single(tmp_path, ((None,), {}), ((), dict(collect=('lost',))), (('broken',), dict(failed=True)), (('d1',), {}))
    assert covered(run, change(BASE + 0.5), change(BASE + 2.5, '001', 1, 'lost'),
                   change(BASE + 3.5, '001', 2, 'broken')) == ({'001': [0, 0, 0, 0]}, 2)


def test_a_retried_request_takes_its_coverage_at_its_first_attempt(tmp_path):
    run = single(tmp_path, (('a1',), {}), (('b1',), dict(retry=0.5)), (('c1',), {}))
    lineage_run, = read_lineage([run])[0]
    assert [wall for _, wall in turn_starts(lineage_run)['a' * 32]] == [BASE + 1, BASE + 1.5, BASE + 3]
    assert covered(run, change(BASE + 1.75, '001', 1, 'a1')) == ({'001': [0, 0, 1]}, 0)
    host = run / 'actors' / '001' / 'host.jsonl'
    written = host.read_text()
    for attempt, expected in (('request-2', [0, 0, 1]), ('request-2-first', [0, 1, 1])):
        # an attempt with no start time leaves the request timed by its other attempt
        events = [json.loads(line) for line in written.splitlines()]
        for event in events:
            if event['type'] == 'request-start' and event['request_id'] == attempt:
                del event['wall_time']
        host.write_text(''.join(json.dumps(event) + '\n' for event in events))
        assert covered(run, change(BASE + 1.75, '001', 1, 'a1')) == ({'001': expected}, 0)


def test_a_restore_applies_at_its_time_and_one_left_out_covers_nothing(tmp_path):
    run = admission(tmp_path, [['a1'], ['b1'], ['c1'], ['d1']])
    assert covered(run, change(BASE + 0.5, '001', 2, 'b1'), change(BASE + 3, '001', 1, 'a1', restore=True)) == (
        {'001': [2, 2, 1, 1]}, 0)
    assert covered(run, change(BASE + 0.5, '001', 2, 'b1'), change(BASE + 2.5, '001', 1, 'unknown', restore=True)) == (
        {'001': [2, 2, 0, 0]}, 1)
    assert covered(run, change(BASE + 0.5, '001', 2, 'b1'), change(BASE + 2.5, '001', 1, 'nowhere', restore=True),
                   change(BASE + 3.5, '001', 3, 'c1')) == ({'001': [2, 2, 0, 3]}, 1)


def test_operations_placed_in_reverse_order_are_refused_without_a_restore(tmp_path):
    run = admission(tmp_path, [['a1'], ['A', 'B'], ['c1']])
    with pytest.raises(ScheduleError, match='change 2: its operation is placed before the change before it'):
        covered(run, change(BASE + 0.5, '001', 2, 'B'), change(BASE + 0.75, '001', 2, 'A'))
    assert covered(run, change(BASE + 0.5, '001', 2, 'B'), change(BASE + 0.75, '001', 2, 'A', restore=True)) == (
        {'001': [1, 1, 1]}, 0)


def test_the_schedule_command_times_a_restore_by_the_row_before_it(tmp_path):
    run = admission(tmp_path, [['a1'], ['b1'], ['c1']])
    a1, b1, c1 = (dict(actor='001', step=n, operation=o, ordinal=n) for n, o in ((1, 'a1'), (2, 'b1'), (3, 'c1')))
    restore = dict(version='v4', restored='v2', counted_through='v2')
    status = dict(schema='curator-runner-status/1', updated_wall=BASE + 9, covered_prefix=dict(end=c1, restore=restore))
    runner_files(run, [poll(BASE + 1, None), poll(BASE + 2, b1), poll(BASE + 3, b1), poll(BASE + 4, a1, restore),
        poll(BASE + 5, a1, restore)], status)
    assert schedule_from_runner(run)['changes'] == [change(BASE + 1), change(BASE + 2, '001', 2, 'b1'),
        change(BASE + 3, '001', 1, 'a1', restore=True), change(BASE + 9, '001', 3, 'c1', restore=True)]
    first = tmp_path / 'first'
    runner_files(admission(first, [['a1']]), [poll(BASE + 1, a1, restore)], dict(status, covered_prefix=dict(
        end=a1, restore=restore)))
    assert schedule_from_runner(first / 'run')['changes'] == [change(BASE + 1, '001', 1, 'a1', restore=True)]


def test_the_schedule_command_refuses_an_unreadable_status_file_and_an_output_inside_the_run(tmp_path):
    run = admission(tmp_path, [['a1']])
    directory = runner_files(run, [poll(BASE + 1, None)], dict(schema='curator-runner-status/1', updated_wall=BASE + 2,
        covered_prefix=dict(end=None, restore=None)))
    before = {path: path.read_bytes() for path in directory.iterdir()}
    for inside in (directory / 'polls.jsonl', run / 'schedule.json', tmp_path / 'run' / '.' / 'actors' / 'x.json'):
        with pytest.raises(ScheduleError, match='not written inside the run'):
            main(['schedule', str(run), '--output', str(inside)])
    assert {path: path.read_bytes() for path in directory.iterdir()} == before and not (run / 'schedule.json').exists()
    (directory / 'status.json').write_text('{"schema": ')
    with pytest.raises(ScheduleError, match='status.json: unreadable'):
        schedule_from_runner(run)


def test_recorded_deliveries_uses_only_the_initial_starting_briefing_when_cuts_emit_replacement_briefings(tmp_path):
    trace = Trace('a' * 32, BASE)
    trace.deliver('briefing', 'request-1', 'a' * 180, version='v0')
    trace.operate('op-1')
    trace.deliver('briefing', 'request-2', 'b' * 12000, version='v1')
    trace.operate('op-2')
    run_dir = tmp_path / 'cut-briefings'
    trace.write(run_dir / 'actors' / '001')
    run, = read_lineage([run_dir])[0]
    b0, extras, counts = recorded_deliveries_for_run(run)[trace.actor]
    assert b0 == 45
    assert extras == [0, 0]
    assert counts['unmatched_deliveries'] == 0
