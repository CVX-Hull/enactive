"""Selected-package admission checks occur before a DB or child exists."""
import copy
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


# Level v4 (#345's development parameters): theta with the digest of its fitting, m = 2, C = K = 10, N = 3, c = 0.0.
LEVEL=dict(mode='live',episode_cap=10,staleness_inputs=10,budget_fractions=[.25,.5,.75],intent_tail_bytes=1024,
           max_http_attempts=2,pass_max_requests=2,pass_seconds=120,
           theta=0.1251514705882353,theta_fitting_sha256='8a80f12b736b6d993fcf6c356a7686a03c85508779d52c376d2ce1394893c76b',
           min_episode_inputs=2,stall_settles=3,confidence_floor=0.0,
           recall=dict(tail_top=2,tail_exploration=1,level_items=10),
           recorder=dict(max_http_attempts=2,pass_max_requests=2,pass_seconds=60,backlog=3))
# The frozen role prompts' digests, pinned here independently of the validator that also pins them.
FROZEN={'subgoal-v4.txt':'08c8558f659dacb1feb61c81b1286e91dca24e8808eab8e5d0b5e56cf53aaad8',
        'episode-v1.txt':'a6c326069bd8fec86bf2c30bcbcf34e51e34f5d1371f5ac32f764b664869a910'}


def package(root,level=None,route_requests=10):
    level=copy.deepcopy(level)
    directory=root/'.runtime/computer-sessions/selected';directory.mkdir(parents=True)
    for name in ('native','library','options','interpreter','adapter'):(root/name).write_bytes(name.encode())
    tail=level['intent_tail_bytes'] if level and level['mode']=='live' else None
    values={
        'route.json':dict(schema='player-host/6',role='actor',intent_tail_bytes=tail,service_tier='default',
            max_requests=route_requests,max_context_images=8,context_image_block=1,model=dict(id='fixture',
            contextWindow=1000,maxTokens=100,cost=dict(input=.45,cacheRead=.45,cacheWrite=.45,output=1.8))),
        'mcp-template.json':configuration('@ACTOR_CONFIG@',profile='narrowed' if level else 'flat'),
        'context.txt':'Frozen context','prompt.txt':'Frozen mission',
        'target.json':dict(argv=[str(root/'native')],cwd=str(root),env={}),
    }
    if level:
        values['level-role.txt']=packages.LEVEL_ROLE.read_text();values['episode-role.txt']=packages.EPISODE_ROLE.read_text()
    for name,value in values.items():(directory/name).write_text(value if isinstance(value,str) else json.dumps(value))
    artifact=lambda p:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    profile=dict(schema='campaign-run/5',session='a'*32,source_commit='f'*40,
        actor_profile='narrowed' if level else 'flat',level=level,
        files={name:artifact(directory/name)['sha256'] for name in values},
        initial_files={str(root/'options'):artifact(root/'options')['sha256']},
        native=artifact(root/'native'),library=artifact(root/'library'),shared_lock=str(root/'.runtime/bridge/game.lock'),
        player_store=str(root/'player.sqlite3'),host=dict(argv=[str(root/'interpreter'),str(root/'adapter')]),effort='off',port=8766,
        wall_seconds=300,host_seconds=100,total_host_seconds=200,max_hosts=2,max_http_attempts=10,
        limits=dict(max_inputs=100,max_requests=100,max_frames=100,max_bytes=1000000),
        accounting=dict(prior_attempts=0,prior_reserved_usd=0,prospective_reserved_usd=.0063,ceiling_usd=1))
    (directory/'manifest.json').write_text(json.dumps(profile))
    return directory,profile


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


@pytest.mark.parametrize('mode',['live','shadow'])
def test_level_package_freezes_its_role_profile_and_partition(tmp_path,mode):
    directory,profile=package(tmp_path,dict(LEVEL,mode=mode),route_requests=6)
    frozen=validate(directory,tmp_path)[0]
    assert frozen['level']['mode']==mode and frozen['schema']=='campaign-run/5'
    # theta is frozen by value and by the digest of its fitting; the recorder has its own partition.
    assert frozen['level']['theta']==0.1251514705882353 and len(frozen['level']['theta_fitting_sha256'])==64
    assert frozen['level']['recorder']['max_http_attempts']==2


def test_the_frozen_role_prompts_match_their_pinned_digests_and_the_adr_appendix():
    for name,sha in FROZEN.items():
        assert hashlib.sha256((packages.ROOT/'tools/player_roles'/name).read_bytes()).hexdigest()==sha
        assert packages.FROZEN_ROLE_SHA256[name]==sha
    # Verbatim: the ADR's blockquote, its wrapped lines joined with single spaces.
    adr=(packages.ROOT/'docs/decisions/007-player-subgoal-level.md').read_text()
    appendix=adr[adr.index('## Appendix: v4 role prompts'):]
    for title,name in (('episode-v1','episode-v1.txt'),('subgoal-v4','subgoal-v4.txt')):
        lines=appendix[appendix.index(f'**`{title}`:**'):].splitlines()[1:]
        quote=[];
        for line in lines:
            if line.startswith('>'):quote.append(line[1:].strip())
            elif quote:break
        assert (packages.ROOT/'tools/player_roles'/name).read_text()==' '.join(quote)+'\n'
    assert not (packages.ROOT/'tools/player_roles/subgoal-v3.txt').exists()


@pytest.mark.parametrize('fault,expected',[
    ('flat_actor','narrowed-profile'),('role_text','frozen current version'),('missing_role','every selected driver input'),
    ('shadow_tail','intent tail'),('live_without_tail','intent tail'),('over_cap','campaign allowance'),
    ('fractions','Budget fractions'),('previous','inert history'),
    ('missing_episode_role','every selected driver input'),('episode_role_text','frozen current version'),
    ('v3_role_text','frozen current version'),('cap_not_k','owner'),('m_over_cap','cannot exceed'),
    ('theta_int','theta'),('theta_zero','theta'),('theta_without_digest','SHA256'),('floor_int','confidence floor'),
    ('recall_sizes','recall sizes'),('recorder_backlog','Integer'),('recorder_over_cap','campaign allowance'),
    ('old_field','Invalid mechanical'),('missing_recorder','Invalid mechanical'),('tail_not_1024','Integer'),('backlog_not_three','Integer'),('few_images','max_context_images')])
def test_invalid_level_package_never_launches(tmp_path,fault,expected):
    directory,profile=package(tmp_path,dict(LEVEL),route_requests=6)
    (tmp_path/'v3').write_text('Role (software-defined). You are the player\'s subgoal level; the log since your last pass is pushed.')
    def refreeze(name,text):
        (directory/name).write_text(text);profile['files'][name]=hashlib.sha256((directory/name).read_bytes()).hexdigest()
    route=json.loads((directory/'route.json').read_text())
    if fault=='flat_actor':profile['actor_profile']='flat'
    if fault=='role_text':refreeze('level-role.txt','Pursue the nearest door.')
    if fault=='missing_role':profile['files'].pop('level-role.txt')
    if fault=='shadow_tail':profile['level']['mode']='shadow'
    if fault=='live_without_tail':refreeze('route.json',json.dumps(dict(route,intent_tail_bytes=None)))
    if fault=='over_cap':refreeze('route.json',json.dumps(dict(route,max_requests=7)))
    if fault=='fractions':profile['level']['budget_fractions']=[.5,.25]
    if fault=='previous':profile['schema']='campaign-run/4'
    if fault=='missing_episode_role':profile['files'].pop('episode-role.txt')
    if fault=='episode_role_text':refreeze('episode-role.txt','Record whatever looks useful.')
    if fault=='v3_role_text':refreeze('level-role.txt',(tmp_path/'v3').read_text())
    if fault=='cap_not_k':profile['level']['episode_cap']=8
    if fault=='m_over_cap':profile['level']['min_episode_inputs']=11
    if fault=='theta_int':profile['level']['theta']=1
    if fault=='theta_zero':profile['level']['theta']=0.0
    if fault=='theta_without_digest':profile['level']['theta_fitting_sha256']='abc'
    if fault=='floor_int':profile['level']['confidence_floor']=0
    if fault=='recall_sizes':profile['level']['recall']=dict(tail_top=3,tail_exploration=1,level_items=10)
    if fault=='recorder_backlog':profile['level']['recorder']['backlog']=0
    if fault=='recorder_over_cap':profile['level']['recorder']['max_http_attempts']=3
    if fault=='backlog_not_three':profile['level']['recorder']['backlog']=4
    if fault=='few_images':refreeze('route.json',json.dumps(dict(route,max_context_images=7)))
    if fault=='tail_not_1024':profile['level']['intent_tail_bytes']=512
    if fault=='old_field':profile['level']['inputs_per_pass']=10
    if fault=='missing_recorder':profile['level'].pop('recorder')
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,\
            pytest.raises(ControlError,match=expected):
        packages.preflight(directory)
    assert not validator.called


@pytest.mark.parametrize('fault',['old','old_node','old_route','untracked_adapter','partial','changed','dirty',
                                  'credentials','different_lock'])
def test_invalid_selected_package_never_launches_or_opens_store(tmp_path,fault):
    directory,profile=package(tmp_path)
    if fault=='old':profile['schema']='campaign-run/1'
    if fault=='old_node':
        profile['schema']='campaign-run/2';profile['node']=profile.pop('host')['argv'][0]
    if fault=='old_route':
        path=directory/'route.json';route=json.loads(path.read_text());route['schema']='player-host/5'
        path.write_text(json.dumps(route));profile['files']['route.json']=hashlib.sha256(path.read_bytes()).hexdigest()
    if fault=='partial':(directory/'started.json').write_text('{}')
    if fault=='changed':(directory/'prompt.txt').write_text('different')
    if fault=='different_lock':profile['shared_lock']=str(tmp_path/'another.lock')
    if fault=='credentials':
        path=directory/'target.json';target=json.loads(path.read_text());target['env']['API_KEY']='fixture'
        path.write_text(json.dumps(target));profile['files']['target.json']=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(profile))
    expected={'old':'inert history','old_node':'inert history','old_route':'inert history',
              'untracked_adapter':'tracked by the clean source commit'}.get(fault)
    # Ignored files never appear in porcelain status; only tracking binds them to the commit.
    with patch.object(packages,'ROOT',tmp_path),\
            git(b' M source' if fault=='dirty' else b'',untracked={'adapter'} if fault=='untracked_adapter' else ()),\
            patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError,match=expected):
        packages.preflight(directory)
    assert not validator.called
    assert not (directory/'session.sqlite3').exists() and not (directory/'native-process.json').exists()


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
    with patch.object(campaign_run,'preflight',return_value=(profile,dict(api_key_env='OFFLINE_KEY'),{})),\
            patch.object(campaign_run,'OwnedTarget',Owner),patch.object(campaign_run.signal,'signal',side_effect=install),\
            patch.dict(os.environ,{'OFFLINE_KEY':'fixture-secret'}),patch.object(campaign_run,'run_hosts') as host:
        result=campaign_run.run_campaign(directory)
    assert calls==([] if when=='before' else ['start']) and not host.called
    assert result['accounting']['attempts_charged']==0 and result['deciding_hosts_quiescent']
    assert 'Cancelled' in result['reason']


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
