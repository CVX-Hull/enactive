"""Delivery routes and role separation are facts of the trace, never judge choices."""
import json
import pytest

from harness.evaluation.core.host import host_facts
from harness.evaluation.core.sources import read_host
from harness.jsonio import file_sha256
from tools.knowledge_export import draw, export
from tools.memory_measure import MeasureError, build_facts, recall_measure, read_facts
from tools.memory_screen_checks import read_lineage


def test_recall_has_no_player_decision_and_never_charges_a_successor_briefing_to_its_predecessor():
    from harness.evaluation.core.sources import HostEvent
    def request(actor,key,cost):
        return [HostEvent(actor,1,'request-start',1,0,dict(request_id=key)),
                HostEvent(actor,2,'response-complete',2,1,dict(request_id=key,stop_reason='stop',usage_available=True,
                    usage=dict(input=1,output=0,cacheRead=0,cacheWrite=0,cost=dict(total=cost))))]
    facts=host_facts(['a','b','c'],{'a':request('a','request-1',.1),
        'b':request('b','recall-1',.7)+request('b','request-1',.2),'c':request('c','recall-1',.9)})
    assert [r.decision for r in facts.requests]==[1,None,2,None]
    assert facts.cumulative(1)==(1,.1)
    tokens,cost=facts.cumulative(2)
    assert tokens==3 and cost==pytest.approx(1)
    assert facts.cumulative(None)==(0,0)
    assert [r.request_id for r in facts.request_rows()]==['request-1','recall-1','request-1','recall-1']


@pytest.mark.parametrize('articles_delivered',[0,1,2])
def test_judged_facts_builder_resolves_shared_facts_from_the_recorded_citing_articles(tmp_path,articles_delivered):
    from tests.test_knowledge_export import store
    full=store()
    seed=next(s for s in range(100) if len(draw(full,s)[0]['articles'])==articles_delivered)
    package=tmp_path/'package';hashes=export(package,full,seed)
    (package/'manifest.json').write_text(json.dumps(dict(schema='campaign-run/12',session='a'*32, labels=dict(world=None),
        live_knowledge_updates=False,files={'delivered-knowledge.json':hashes['delivered-knowledge.json']},
        private_files={n:hashes['private/'+n] for n in ('knowledge-full.json','units.json')})))
    actor=package/'actors/001';actor.mkdir(parents=True)
    (actor/'host.jsonl').write_text(json.dumps(dict(type='host-start',schema='player-host/10',telemetry_version=10,actor_id='actor'))+'\n')
    value=build_facts(tmp_path/'memory-measure/result',[package])['admissions']['package']['001']
    route='index' if articles_delivered else 'withheld'
    assert any(f['id']=='fact-3' for f in value[route])


def test_end_facts_docstring_names_the_current_receipt_and_driver_versions():
    from harness.evaluation.core.sources import read_end_facts,RECEIPT_SCHEMA,DRIVER_SCHEMA
    assert RECEIPT_SCHEMA in read_end_facts.__doc__ and DRIVER_SCHEMA in read_end_facts.__doc__


ARCHIVED_SESSION = '2cda0867c34442f394299555aece7009'  # a sealed campaign-run/10 session of the archive index
ARCHIVED_EMPTY = dict(schema='delivered-knowledge/1', version=None, coverage=None, articles=[], facts=[])


def frozen_package(tmp_path, schema, knowledge, *, selection=True, **manifest):
    """A package with its frozen knowledge and no actor: `campaign-run/12`, or a sealed `/10` one of the archive."""
    package = tmp_path/'package'
    hashes = export(package, knowledge)
    full = package/'private/knowledge-full.json'
    if not selection:
        legacy = json.loads(full.read_text())
        del legacy['selection']
        full.write_text(json.dumps(legacy))
    current = schema == 'campaign-run/12'
    (package/'manifest.json').write_text(json.dumps(dict(dict(schema=schema, session='a' * 32 if current else ARCHIVED_SESSION,
        labels=dict(world=None), files={'delivered-knowledge.json': hashes['delivered-knowledge.json']},
        private_files={'knowledge-full.json': file_sha256(full), 'units.json': hashes['private/units.json']},
        **(dict(live_knowledge_updates=False) if current else {})), **manifest)))
    (package/'actors').mkdir()
    return package


@pytest.mark.parametrize('schema', ['campaign-run/12', 'campaign-run/10'])
def test_facts_builder_requires_private_selection_only_on_current_packages(tmp_path, schema):
    from harness.player.knowledge import empty
    current = schema == 'campaign-run/12'
    package = frozen_package(tmp_path, schema, empty() if current else ARCHIVED_EMPTY, selection=False)
    run = tmp_path/'memory-measure/result'
    if current:
        with pytest.raises(MeasureError, match='private knowledge selection differs'):
            build_facts(run, [package])
    else:
        assert build_facts(run, [package])['admissions'] == {'package': {}}


@pytest.mark.parametrize('schema', ['campaign-run/12', 'campaign-run/10'])
def test_facts_builder_reads_each_package_version_with_the_knowledge_version_it_was_frozen_with(tmp_path, schema):
    """S-MIGRATION, closed archive reads: a sealed `/10` package keeps `delivered-knowledge/1`; a current one holds `/2`."""
    from harness.player.knowledge import empty
    current = schema == 'campaign-run/12'
    other = frozen_package(tmp_path/'other', schema, ARCHIVED_EMPTY if current else empty())
    with pytest.raises(MeasureError, match='unsupported frozen knowledge'):
        build_facts(tmp_path/'memory-measure/other', [other])
    own = frozen_package(tmp_path/'own', schema, empty() if current else ARCHIVED_EMPTY)
    assert build_facts(tmp_path/'memory-measure/own', [own])['admissions'] == {'package': {}}


def test_facts_builder_refuses_a_run_that_delivered_versions_outside_its_frozen_file(tmp_path):
    from harness.player.knowledge import empty
    package = frozen_package(tmp_path, 'campaign-run/12', empty(), live_knowledge_updates=True)
    with pytest.raises(MeasureError, match='live_knowledge_updates delivers versions outside it'):
        build_facts(tmp_path/'memory-measure/result', [package])


def test_the_newly_archived_spend_limit_run_retains_its_recorded_spend(tmp_path):
    from tools.host_analysis import campaign_evidence
    from harness.evaluation.core.sources import run_archive_entry
    run=tmp_path/'spend-limit-run-555';actor=run/'actors/001';actor.mkdir(parents=True)
    (run/'manifest.json').write_text(json.dumps(dict(schema='campaign-run/6',session='c60d96bb52bd296f4da71210b1113b3a')))
    (run/'receipt.json').write_text(json.dumps(dict(schema='campaign-receipt/4',driver=dict(schema='player-driver/4',
        reported_usd='0.1135458',unpriced_requests=0,unpriced_request_usd='0.4096',spent_usd='0.1135458',spend_complete=True))))
    value=campaign_evidence(actor/'host.jsonl',run_archive_entry(run))
    assert value['metadata_coverage']['receipt.json']=='recorded'
    driver=value['receipt.json']['driver']
    assert driver['spent_usd']=='0.1135458' and driver['unpriced_requests']==0
    assert 'unpriced_recall_requests' not in driver


def test_builder_uses_first_text_exposure_and_last_completed_player_decision(tmp_path):
    package=tmp_path/'admission';actor=package/'actors/001';actor.mkdir(parents=True)
    full=dict(schema='delivered-knowledge/2',version='v3',commit='c'*40,repository_id='d'*40,coverage=None,
        facts=[dict(id=x,type='claim',text=x,seen=dict(session='s1',actor='001',step=1,order=[1,'001',1])) for x in ('brief','read-first','lead-first','index','withheld')],
        articles=[dict(id='article-'+x,title=x,lead=x,body=[dict(text=x,facts=[x])],links=[],last_confirmed=dict(session='s1',actor='001',step=1,order=[1,'001',1]))
                  for x in ('brief','read-first','lead-first','withheld')])
    seed=next(n for n in range(1000) if {f['id'] for f in draw(full,n)[0]['facts']}=={'brief','read-first','lead-first','index'})
    hashes=export(package,full,seed)
    (package/'manifest.json').write_text(json.dumps(dict(schema='campaign-run/12',session='a'*32, labels=dict(world=None),
        live_knowledge_updates=False,files={'delivered-knowledge.json':hashes['delivered-knowledge.json']},
        private_files={name:hashes['private/'+name] for name in ('knowledge-full.json','units.json')})))
    events=[dict(type='host-start',schema='player-host/10',telemetry_version=10,session='a'*32,actor_id='b'*32),
            dict(type='request-start',request_id='recall-1',request_role='recall'),
            dict(type='response-complete',request_id='recall-1',stop_reason='stop'),
            dict(type='knowledge-delivery',kind='briefing',text='briefing',fact_ids=['brief'],receiving_player_request_id='request-1')]
    for number,identity in ((1,None),(2,'read-first'),(3,None),(4,'lead-first')):
        if number==3:
            events.extend([dict(type='knowledge-recall',kind='reminder',status='selected',article_ids=['article-lead-first'],request_id='recall-2'),
                dict(type='knowledge-delivery',kind='reminder',text='reminder',fact_ids=['read-first','lead-first'],
                     recall_request_id='recall-2',receiving_player_request_id='request-3')])
        request=f'request-{number}'
        events.extend([dict(type='request-start',request_id=request),
            dict(type='response-complete',request_id=request,stop_reason='toolUse'),
            dict(type='tool-start',request_id=request,tool_call_id='call',tool='player_knowledge_read' if identity else 'computer_input',arguments={}),
            dict(type='tool-result',request_id=request,tool_call_id='call',tool='player_knowledge_read' if identity else 'computer_input',
                 result=dict(content=[dict(type='text',text=json.dumps(dict(records=[dict(id=identity,text=identity)] if identity else [])))]))])
    events.append(dict(type='knowledge-recall',kind='reminder',status='silence',request_id='recall-3'))
    events.append(dict(type='knowledge-undelivered',kind='reminder',text='unsent',fact_ids=['index']))
    for n,e in enumerate(events):e.update(monotonic_ms=n,wall_time=f'2026-11-13T00:00:{n:02d}Z')
    path=actor/'host.jsonl';path.write_text(''.join(json.dumps(e)+'\n' for e in events))
    out=tmp_path/'memory-measure/demo'
    value=build_facts(out,[package])['admissions']['admission']['001']
    assert value['lead']==[dict(id='brief',text='brief'),dict(id='lead-first',text='lead-first',from_decision=2)]
    assert value['read']==[dict(id='read-first',text='read-first',from_decision=2)]
    assert value['index']==[dict(id='index',text='index')]
    assert value['withheld']==[dict(id='withheld',text='withheld')]
    assert value['reminders']==[dict(decision=2,text='reminder')]
    assert read_facts(out/'judged-facts.json',{'admission':{'001':(1,4)}})
    actor_id,parsed=read_host(path,'001')
    facts=host_facts([actor_id],{actor_id:parsed})
    assert [c.decision for c in facts.calls]==[1,2,3,4]
    assert facts.requests[0].role=='recall' and not facts.requests[0].completed
    _,actors=read_lineage([package])
    assert (actors[0].first,actors[0].requests)==(1,4)
    report=recall_measure(out,[dict(start='admission',actor='001',fact='lead-first',last=3,label='in_line'),dict(start='admission',actor='001',fact='lead-first',last=4,label='did_not_apply')])
    assert report['silence']==dict(numerator=1,denominator=2,value=.5)
    assert report['precision']==dict(numerator=1,denominator=2,value=.5)
