"""Selected-package admission checks occur before a DB or child exists."""
import hashlib
import json
import os
import signal
from unittest.mock import patch
from unittest.mock import Mock

import pytest

from harness.computer.protocol import ControlError
from tools import campaign_package as packages
from tools import campaign_run
from tools.configure_player_tools import configuration


def package(root):
    directory=root/'.runtime/computer-sessions/selected';directory.mkdir(parents=True)
    for name in ('native','library','options','interpreter','adapter'):(root/name).write_bytes(name.encode())
    from harness.player.knowledge import empty
    from tools.knowledge_export import export
    hashes=export(directory,empty())
    values={
        'delivered-knowledge.json':empty(),
        # 1000 context tokens at $0.45 and 100 output tokens at $1.80 per million: $0.00063 for a request with no cost record.
        'route.json':dict(schema='player-host/5',service_tier='default',max_requests=10,context_reserve_tokens=200,
            spend_limit_usd='1',unpriced_request_usd='0.00063',model=dict(id='fixture',
            contextWindow=1000,maxTokens=100,cost=dict(input=.45,cacheRead=.45,cacheWrite=.45,output=1.8))),
        'mcp-template.json':configuration('@ACTOR_CONFIG@'),
        'context.txt':'Frozen context','prompt.txt':'Frozen mission',
        'target.json':dict(argv=[str(root/'native')],cwd=str(root),env={}),
    }
    values['route.json']['recall']=dict(model=values['route.json']['model'],every=5,max_requests=3,unpriced_request_usd='0.00063')
    for name,value in values.items():(directory/name).write_text(value if isinstance(value,str) else json.dumps(value))
    artifact=lambda p:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    profile=dict(schema='campaign-run/7',session='a'*32,source_commit='f'*40,
        labels=dict(arm='ceiling',start='S1',scenario='Evacuee',lineage=None,admission=None),
        files={name:artifact(directory/name)['sha256'] for name in values},
        private_files={name:hashes['private/'+name] for name in ('knowledge-full.json','units.json')},
        initial_files={str(root/'options'):artifact(root/'options')['sha256']},
        native=artifact(root/'native'),library=artifact(root/'library'),shared_lock=str(root/'.runtime/bridge/game.lock'),
        player_store=str(root/'player.sqlite3'),host=dict(argv=[str(root/'interpreter'),str(root/'adapter')]),effort='off',port=8766,
        wall_seconds=300,host_seconds=100,total_host_seconds=200,max_hosts=2,max_http_attempts=10,
        limits=dict(max_inputs=100,max_requests=100,max_frames=100,max_bytes=1000000),
        ending_reserve=dict(seconds=10,http_attempts=2,inputs=10,requests=10,frames=10,frame_bytes=1000,usd='0.1'),
        spend_limit_usd='1')
    (directory/'manifest.json').write_text(json.dumps(profile))
    return directory,profile


def rewrite_route(directory,profile,**changes):
    path=directory/'route.json';route=json.loads(path.read_text());route.update(changes)
    path.write_text(json.dumps(route));profile['files']['route.json']=hashlib.sha256(path.read_bytes()).hexdigest()


def git(status=b'',untracked=()):
    """Clean-checkpoint double: HEAD, porcelain status and tracked adapter paths."""
    def output(argv,**kwargs):
        if argv[1]=='rev-parse':return 'f'*40
        if argv[1]=='status':return status
        assert argv[1:4]==['ls-files','-z','--']
        return b''.join(path.encode()+b'\0' for path in argv[4:] if path not in untracked)
    return patch.object(packages.subprocess,'check_output',side_effect=output)


def validate(directory,root):
    with patch.object(packages,'ROOT',root),git(),\
            patch.object(packages.subprocess,'run') as validator:
        result=packages.preflight(directory)
        assert 'API_KEY' not in ' '.join(validator.call_args.kwargs['env'])
        argv=validator.call_args.args[0]
        assert argv[:3]==[str(root/'interpreter'),str(root/'adapter'),'validate']
        assert argv[3:]==['--config',str(directory/'route.json'),'--mcp-config',str(directory/'mcp-template.json'),
                          '--model','fixture','--effort','off']
        assert validator.call_args.kwargs['env'].keys()=={'PATH','LANG'}
        return result


def test_only_selected_fresh_package_is_read(tmp_path):
    directory,profile=package(tmp_path)
    unrelated=tmp_path/'.runtime/historical';unrelated.mkdir()
    for i in range(1000):(unrelated/f'{i}.json').write_text('{unsupported partial old data')
    assert validate(directory,tmp_path)[0]==profile
    assert not (directory/'started.json').exists() and not (directory/'session.sqlite3').exists()


def test_knowledge_is_required_private_hashes_are_closed_and_reserve_covers_both_bounds(tmp_path):
    directory,profile=package(tmp_path)
    # Empty knowledge contributes zero to the recall part of the reserve.
    profile['ending_reserve']['usd']='0.00063'
    (directory/'manifest.json').write_text(json.dumps(profile))
    assert validate(directory,tmp_path)
    knowledge=dict(schema='delivered-knowledge/1',version='v1',coverage=None,articles=[],
                   facts=[dict(id='fact',type='claim',text='Fallible data',seen=dict(order=1))])
    path=directory/'delivered-knowledge.json';path.write_text(json.dumps(knowledge))
    profile['files']['delivered-knowledge.json']=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(profile))
    with pytest.raises(ControlError,match='ending_reserve.usd'):validate(directory,tmp_path)
    profile['ending_reserve']['usd']='0.00126'
    (directory/'manifest.json').write_text(json.dumps(profile))
    assert validate(directory,tmp_path)
    profile['private_files']['unexpected.json']='0'*64
    (directory/'manifest.json').write_text(json.dumps(profile))
    with pytest.raises(ControlError):validate(directory,tmp_path)
    profile['private_files'].pop('unexpected.json');profile['files'].pop('delivered-knowledge.json')
    (directory/'manifest.json').write_text(json.dumps(profile))
    with pytest.raises(ControlError,match='Freeze every'):validate(directory,tmp_path)


@pytest.mark.parametrize('fault',['old','previous_package','previous_labelless','reservation_package','pre_delivery_package','old_node','old_route','previous_route',
                                  'reservation_route','untracked_adapter','partial','changed','dirty','credentials','different_lock'])
def test_invalid_selected_package_never_launches_or_opens_store(tmp_path,fault):
    directory,profile=package(tmp_path)
    if fault=='old':profile['schema']='campaign-run/1'
    if fault=='pre_delivery_package':profile['schema']='campaign-run/6'
    if fault=='previous_package':profile['schema']='campaign-run/3'
    if fault=='previous_labelless':profile['schema']='campaign-run/4';del profile['labels']
    if fault=='reservation_package':
        # The package version that declared a worst-case reservation instead of a dollar limit.
        profile['schema']='campaign-run/5';del profile['spend_limit_usd'];del profile['ending_reserve']['usd']
        profile['accounting']=dict(prior_attempts=0,prior_reserved_usd=0,prospective_reserved_usd=.0063,ceiling_usd=1)
    if fault=='old_node':
        profile['schema']='campaign-run/2';profile['node']=profile.pop('host')['argv'][0]
    if fault in ('old_route','previous_route','reservation_route'):
        rewrite_route(directory,profile,schema=dict(old_route='pi-player-host/5',previous_route='player-host/2',reservation_route='player-host/3')[fault])
    if fault=='partial':(directory/'started.json').write_text('{}')
    if fault=='changed':(directory/'prompt.txt').write_text('different')
    if fault=='different_lock':profile['shared_lock']=str(tmp_path/'another.lock')
    if fault=='credentials':
        path=directory/'target.json';target=json.loads(path.read_text());target['env']['API_KEY']='fixture'
        path.write_text(json.dumps(target));profile['files']['target.json']=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(profile))
    expected={'old':'inert history','previous_package':'inert history','previous_labelless':'inert history','reservation_package':'inert history',
              'old_node':'inert history','old_route':'inert history','previous_route':'inert history','reservation_route':'inert history',
              'untracked_adapter':'tracked by the clean source commit'}.get(fault)
    # Ignored files never appear in porcelain status; only tracking binds them to the commit.
    with patch.object(packages,'ROOT',tmp_path),\
            git(b' M source' if fault=='dirty' else b'',untracked={'adapter'} if fault=='untracked_adapter' else ()),\
            patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError,match=expected):
        packages.preflight(directory)
    assert not validator.called
    assert not (directory/'session.sqlite3').exists() and not (directory/'native-process.json').exists()


def test_labels_are_required_and_current_schema_only(tmp_path):
    directory,profile=package(tmp_path)
    assert validate(directory,tmp_path)[0]['labels']==dict(arm='ceiling',start='S1',scenario='Evacuee',lineage=None,admission=None)
    del profile['labels']
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,\
            pytest.raises(ControlError,match='Invalid mechanical object fields'):packages.preflight(directory)
    assert not validator.called


@pytest.mark.parametrize('labels',[
    'text',None,[],dict(arm='a',start='S1',scenario='x',lineage=None),
    dict(arm='a',start='S1',scenario='x',lineage=None,admission=None,extra=1),
    dict(arm='',start='S1',scenario='x',lineage=None,admission=None),
    dict(arm='a'*41,start='S1',scenario='x',lineage=None,admission=None),
    dict(arm='a',start='S'*41,scenario='x',lineage=None,admission=None),
    dict(arm='a',start='S1',scenario='x'*81,lineage=None,admission=None),
    dict(arm='a',start='S1',scenario='',lineage=None,admission=None),
    dict(arm='a',start='S1',scenario='x',lineage='',admission=1),
    dict(arm='a',start='S1',scenario='x',lineage='l'*41,admission=1),
    dict(arm=None,start='S1',scenario='x',lineage=None,admission=None),
    dict(arm=1,start='S1',scenario='x',lineage=None,admission=None),
    dict(arm='café',start='S1',scenario='x',lineage=None,admission=None),
    dict(arm='a\nb',start='S1',scenario='x',lineage=None,admission=None),
    dict(arm='a',start='S1\x00',scenario='x',lineage=None,admission=None),
    dict(arm='a',start='S1',scenario='x\x7f',lineage=None,admission=None),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=None),
    dict(arm='a',start='S1',scenario='x',lineage=None,admission=1),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=0),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=10001),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=True),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission='1'),
])
def test_invalid_operator_labels_refuse_before_effects(tmp_path,labels):
    directory,profile=package(tmp_path)
    profile['labels']=labels
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError):
        packages.preflight(directory)
    assert not validator.called


@pytest.mark.parametrize('labels',[
    dict(arm='a'*40,start='S'*40,scenario='x'*80,lineage='l'*40,admission=10000),
    dict(arm='long-horizon',start='S2',scenario='Mixed printable ~!@# punctuation',lineage='survivor-1',admission=1),
    dict(arm='ceiling',start='S1',scenario='Evacuee',lineage=None,admission=None),
])
def test_valid_operator_labels_are_admitted(tmp_path,labels):
    directory,profile=package(tmp_path)
    profile['labels']=labels
    (directory/'manifest.json').write_text(json.dumps(profile))
    assert validate(directory,tmp_path)[0]['labels']==labels


@pytest.mark.parametrize('when',['before','during'])
def test_prelaunch_cancellation_does_not_wait_for_target_or_admit_actor(tmp_path,when):
    directory,profile=package(tmp_path)
    handlers={};calls=[]
    def install(sig,handler):
        prior=handlers.get(sig);handlers[sig]=handler;return prior
    class Owner:
        channel=None
        def __init__(self,*args):pass
        def reserve(self):
            if when=='before':handlers[signal.SIGTERM](signal.SIGTERM,None)
        def start(self):
            calls.append('start');self.channel=Mock()
            handlers[signal.SIGTERM](signal.SIGTERM,None)
            return self.channel
        def wait_target(self):calls.append('wait')
        def close(self):return dict(native_absence_verified=True,normal_native_exit_zero=False)
    with patch.object(campaign_run,'preflight',return_value=(profile,dict(api_key_env='OFFLINE_KEY',unpriced_request_usd='0.00063',recall=dict(unpriced_request_usd='0.00063')),{})),\
            patch.object(campaign_run,'OwnedTarget',Owner),patch.object(campaign_run.signal,'signal',side_effect=install),\
            patch.dict(os.environ,{'OFFLINE_KEY':'fixture-secret'}),patch.object(campaign_run,'run_hosts') as host:
        result=campaign_run.run_campaign(directory)
    assert calls==([] if when=='before' else ['start']) and not host.called
    assert result['schema']=='campaign-receipt/5'
    # No host was started, so nothing was spent and the record is complete.
    assert result['accounting']==dict(spend_limit_usd='1',reported_usd='0',unpriced_requests=0,unpriced_recall_requests=0,unpriced_request_usd='0.00063',unpriced_recall_request_usd='0.00063',
        spent_usd='0',attempts_charged=0,allocated_max_attempts=10,spend_complete=True)
    assert result['deciding_hosts_quiescent']
    assert 'Cancelled' in result['reason']


def test_receipt_spend_is_reported_cost_plus_unpriced_requests_at_the_bound():
    profile=dict(spend_limit_usd='5',max_http_attempts=40);route=dict(recall=dict(unpriced_request_usd='0'),unpriced_request_usd='0.4096')
    driver=dict(reported_usd='0.1337',unpriced_requests=2,unpriced_recall_requests=0,attempts_charged=31,spend_complete=True)
    assert campaign_run.accounting(profile,route,driver,True)==dict(spend_limit_usd='5',reported_usd='0.1337',unpriced_requests=2,unpriced_recall_requests=0,
        unpriced_request_usd='0.4096',unpriced_recall_request_usd='0',spent_usd='0.9529',attempts_charged=31,allocated_max_attempts=40,spend_complete=True)
    # Hosts were started but the driver left no record: the whole allowance is charged and the spend is unknown.
    lost=campaign_run.accounting(profile,route,None,True)
    assert (lost['attempts_charged'],lost['spent_usd'],lost['spend_complete'])==(40,'0',False)


@pytest.mark.parametrize('limit',[None,'0','0.0','-1',1,0.5,'NaN','Infinity','1e3','+1','1.',''])
def test_a_missing_or_unusable_dollar_limit_refuses_before_effects(tmp_path,limit):
    directory,profile=package(tmp_path)
    if limit is None:del profile['spend_limit_usd']
    else:profile['spend_limit_usd']=limit
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError):
        packages.preflight(directory)
    assert not validator.called and not (directory/'started.json').exists()


@pytest.mark.parametrize('reserve',[None,'0','1','1.5',0.1,'-0.1','NaN'])
def test_a_dollar_reserve_that_is_not_below_the_limit_refuses_before_effects(tmp_path,reserve):
    directory,profile=package(tmp_path)
    if reserve is None:del profile['ending_reserve']['usd']
    else:profile['ending_reserve']['usd']=reserve
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError):
        packages.preflight(directory)
    assert not validator.called


def test_a_reserve_below_one_unpriced_request_or_a_zero_bound_refuses_the_package(tmp_path):
    """With less than one request's bound in reserve, a single failed request would end the run abruptly; with a
    zero bound a failed request would count as free."""
    directory,profile=package(tmp_path)
    profile['ending_reserve']['usd']='0.0006'
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run'),\
            pytest.raises(ControlError,match=r'ending_reserve\.usd 0\.0006 must be at least unpriced_request_usd 0\.00063'):
        packages.preflight(directory)
    profile['ending_reserve']['usd']='0.00063'
    (directory/'manifest.json').write_text(json.dumps(profile))
    validate(directory,tmp_path)
    model=json.loads((directory/'route.json').read_text())['model']
    rewrite_route(directory,profile,unpriced_request_usd='0',model=dict(model,cost=dict(input=0,cacheRead=0,cacheWrite=0,output=0)))
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run'),\
            pytest.raises(ControlError,match='give no bound for a request with no cost record'):
        packages.preflight(directory)


@pytest.mark.parametrize('field,value,message',[('spend_limit_usd','0.5',"must be the package's spend_limit_usd, 1"),
    ('unpriced_request_usd','0.0006','must be 0.00063 for this route')])
def test_the_route_repeats_the_limit_and_carries_the_one_computed_bound(tmp_path,field,value,message):
    directory,profile=package(tmp_path)
    assert packages.usd_text(packages.unpriced_request_usd(json.loads((directory/'route.json').read_text())))=='0.00063'
    rewrite_route(directory,profile,**{field:value})
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run'),pytest.raises(ControlError,match=message):
        packages.preflight(directory)


def selected_host(root,host):
    directory,profile=package(root)
    profile['host']=host
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',root),git(),\
            patch.object(packages.subprocess,'run') as validator:
        try:packages.preflight(directory)
        finally:launched=validator.called
    return launched


@pytest.mark.parametrize('fault',['extra_field','empty','too_many','empty_entry','long_entry','not_list','relative_interpreter',
                                  'missing_interpreter','outside_adapter','missing_adapter','symlink_adapter'])
def test_invalid_host_selection_never_launches_a_validator(tmp_path,fault):
    root=tmp_path/'project';root.mkdir()
    interpreter,adapter=str(root/'interpreter'),str(root/'adapter')
    (root/'link').symlink_to(root/'adapter') if fault=='symlink_adapter' else None
    outside=tmp_path/'outside-adapter';outside.write_bytes(b'x')
    host={
        'extra_field':dict(argv=[interpreter,adapter],extra=1),'empty':dict(argv=[]),
        'too_many':dict(argv=[interpreter]+[adapter]*8),'empty_entry':dict(argv=[interpreter,'']),
        'long_entry':dict(argv=[interpreter,'x'*8193]),'not_list':dict(argv=interpreter),
        'relative_interpreter':dict(argv=['interpreter',adapter]),
        'missing_interpreter':dict(argv=[str(root/'absent'),adapter]),
        'outside_adapter':dict(argv=[interpreter,str(outside)]),
        'missing_adapter':dict(argv=[interpreter,str(root/'absent')]),
        'symlink_adapter':dict(argv=[interpreter,str(root/'link')]),
    }[fault]
    # Selection is checked from the frozen manifest alone, before any process exists.
    directory,profile=package(root)
    profile['host']=host
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',root),git(),\
            patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError):packages.preflight(directory)
    assert not validator.called


def test_external_interpreter_outside_project_is_selectable(tmp_path):
    root=tmp_path/'project';root.mkdir()
    outside=tmp_path/'external-interpreter';outside.write_bytes(b'x')
    assert selected_host(root,dict(argv=[str(outside),str(root/'adapter')])) is True


@pytest.mark.parametrize('field',['seconds','http_attempts','inputs','requests','frames','frame_bytes'])
@pytest.mark.parametrize('fault',['missing','zero','over','boolean'])
def test_invalid_original_ending_reserves_refuse_before_effects(tmp_path,field,fault):
    directory,profile=package(tmp_path)
    if fault=='missing':profile['ending_reserve'].pop(field)
    else:profile['ending_reserve'][field]={'zero':0,'over':10**12,'boolean':True}[fault]
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError):
        packages.preflight(directory)
    assert not validator.called and not (directory/'started.json').exists()
