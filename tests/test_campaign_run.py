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
    values={
        'route.json':dict(schema='player-host/1',service_tier='default',max_requests=10,model=dict(id='fixture',
            contextWindow=1000,maxTokens=100,cost=dict(input=.45,cacheRead=.45,cacheWrite=.45,output=1.8))),
        'mcp-template.json':configuration('@ACTOR_CONFIG@'),
        'context.txt':'Frozen context','prompt.txt':'Frozen mission',
        'target.json':dict(argv=[str(root/'native')],cwd=str(root),env={}),
    }
    for name,value in values.items():(directory/name).write_text(value if isinstance(value,str) else json.dumps(value))
    artifact=lambda p:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    profile=dict(schema='campaign-run/3',session='a'*32,source_commit='f'*40,
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


@pytest.mark.parametrize('fault',['old','old_node','old_route','untracked_adapter','partial','changed','dirty',
                                  'credentials','different_lock'])
def test_invalid_selected_package_never_launches_or_opens_store(tmp_path,fault):
    directory,profile=package(tmp_path)
    if fault=='old':profile['schema']='campaign-run/1'
    if fault=='old_node':
        profile['schema']='campaign-run/2';profile['node']=profile.pop('host')['argv'][0]
    if fault=='old_route':
        path=directory/'route.json';route=json.loads(path.read_text());route['schema']='pi-player-host/4'
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
