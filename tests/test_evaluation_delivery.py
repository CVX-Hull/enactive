"""Delivery routes and role separation are facts of the trace, never judge choices."""
import json

from harness.evaluation.core.host import host_facts
from harness.evaluation.core.sources import read_host
from tools.knowledge_export import draw, export
from tools.memory_measure import build_facts, recall_measure, read_facts
from tools.memory_screen_checks import read_lineage


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
    full=dict(schema='delivered-knowledge/1',version='v3',coverage=None,
        facts=[dict(id=x,type='claim',text=x,seen=dict(order=1)) for x in ('brief','read-first','lead-first','index','withheld')],
        articles=[dict(id='article-'+x,title=x,lead=x,body=[dict(text=x,facts=[x])],links=[],last_confirmed=dict(order=1))
                  for x in ('brief','read-first','lead-first','withheld')])
    seed=next(n for n in range(1000) if {f['id'] for f in draw(full,n)[0]['facts']}=={'brief','read-first','lead-first','index'})
    hashes=export(package,full,seed)
    (package/'manifest.json').write_text(json.dumps(dict(schema='campaign-run/7',session='a'*32,
        files={'delivered-knowledge.json':hashes['delivered-knowledge.json']},
        private_files={name:hashes['private/'+name] for name in ('knowledge-full.json','units.json')})))
    events=[dict(type='host-start',schema='player-host/5',telemetry_version=5,session='a'*32,actor_id='b'*32),
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
