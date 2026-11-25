"""Selected-package admission checks occur before a DB or child exists."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from unittest.mock import patch
from unittest.mock import Mock

import pytest

from harness.computer.protocol import MAX_FRAME_BYTES, ControlError
from tools import campaign_package as packages
from tools import campaign_run
from tools.configure_player_tools import configuration


from tests.test_knowledge_export import delivered_fixture


KNOWLEDGE = delivered_fixture(['fact'])
KNOWLEDGE['facts'][0]['text'] = 'Fallible data'


def package(root, *, world=None, lineage=None, context=None, knowledge=None, live=False, seed=None):
    directory=root/'.runtime/computer-sessions/selected';directory.mkdir(parents=True)
    for name in ('native','library','options','interpreter','adapter'):(root/name).write_bytes(name.encode())
    from harness.player.knowledge import empty
    from tools.knowledge_export import export
    hashes=export(directory,empty() if knowledge is None else knowledge,seed,world=world,lineage=lineage,context=context)
    values={
        # 1000 context tokens at $0.45 and 100 output tokens at $1.80 per million: $0.00063 for a request with no cost record.
        'route.json':dict(schema='player-host/12',endpoint_costs=None,service_tier='default',context_reserve_tokens=200,context_cut=None,
            spend_limit_usd='1',unpriced_request_usd='0.00063',model=dict(id='fixture',
            contextWindow=1000,maxTokens=100,cost=dict(input=.45,cacheRead=.45,cacheWrite=.45,output=1.8))),
        'mcp-template.json':configuration('@ACTOR_CONFIG@'),
        'context.txt':'Frozen context','prompt.txt':'Frozen mission',
        'target.json':dict(argv=[str(root/'native')],cwd=str(root),env={}),
    }
    values['route.json']['recall']=dict(model=values['route.json']['model'],every=5,unpriced_request_usd='0.00063',endpoint_costs=None)
    for name,value in values.items():(directory/name).write_text(value if isinstance(value,str) else json.dumps(value))
    artifact=lambda p:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    profile=dict(schema='campaign-run/13',context={} if context is None else context,session='a'*32,
        source_commit='f'*40,live_knowledge_updates=live,
        labels=dict(arm='ceiling',start='S1',scenario='Evacuee',lineage=lineage,
                    admission=None if lineage is None else 1,world=world),
        files={name:artifact(directory/name)['sha256'] for name in (*values, 'delivered-knowledge.json')},
        private_files={name:hashes['private/'+name] for name in ('knowledge-full.json','units.json')},
        initial_files={str(root/'options'):artifact(root/'options')['sha256']},
        native=artifact(root/'native'),library=artifact(root/'library'),shared_lock=str(root/'.runtime/bridge/game.lock'),
        player_store=str(root/'player.sqlite3'),host=dict(argv=[str(root/'interpreter'),str(root/'adapter')]),effort='off',port=8766,
        wall_seconds=300,host_seconds=100,total_host_seconds=200,max_hosts=2,
        limits=dict(max_inputs=100,max_requests=100,max_frames=100,max_bytes=1000000),
        ending_reserve=dict(seconds=10,inputs=10,requests=10,frames=10,frame_bytes=1000,usd='0.1'),
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


@pytest.mark.parametrize('version', [9, 10, 11])
def test_preflight_rejects_an_old_host_route_before_dispatch(tmp_path, version):
    directory,profile=package(tmp_path)
    rewrite_route(directory,profile,schema=f'player-host/{version}')
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as adapter:
        with pytest.raises(ControlError,match='Unsupported player host route'):
            packages.preflight(directory)
    adapter.assert_not_called()


@pytest.mark.parametrize('start', ['home-mechanic-open-shelter', 'S0', 'S01', 'S100'])
def test_preflight_rejects_invalid_ledger_start_codes_without_dispatch(tmp_path, start):
    directory, profile = package(tmp_path)
    profile['labels']['start'] = start
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages, 'ROOT', tmp_path), patch.object(packages.subprocess, 'run') as adapter:
        with pytest.raises(ControlError, match='valid development run ledger start code'):
            packages.preflight(directory)
    adapter.assert_not_called()
    assert not (directory/'started.json').exists() and not (directory/'session.sqlite3').exists()


def test_capture_plan_catches_the_failed_evacuee_start(tmp_path):
    _, profile = package(tmp_path)
    profile['limits']['max_bytes'] = 64 * 1024 * 1024
    profile['ending_reserve']['frame_bytes'] = 8 * 1024 * 1024
    with pytest.raises(ControlError, match=r'work capture with 12802 retained bytes, 67096062 remaining bytes, '
                       r'67108864 pending capture bytes'):
        packages.capture_headroom(profile, work_before_bytes=12802)


def test_capture_plan_hard_reservation_allows_equality(tmp_path):
    _, profile = package(tmp_path)
    profile['limits']['max_bytes'] = MAX_FRAME_BYTES + 12802
    plan = packages.capture_headroom(profile, work_before_bytes=12802)
    assert plan['checkpoints']['work']['remaining_bytes'] == MAX_FRAME_BYTES
    with pytest.raises(ControlError, match='Insufficient pending capture headroom'):
        packages.capture_headroom(profile, work_before_bytes=12803)


def test_capture_plan_distinguishes_the_ending_threshold_from_the_capture_floor(tmp_path):
    _, profile = package(tmp_path)
    profile['limits']['max_bytes'] = 3 * MAX_FRAME_BYTES
    profile['ending_reserve']['frame_bytes'] = MAX_FRAME_BYTES
    at_reserve = 2 * MAX_FRAME_BYTES
    with pytest.raises(ControlError, match='Ending reserve reached before planned work capture'):
        packages.capture_headroom(profile, work_before_bytes=at_reserve)
    plan = packages.capture_headroom(profile, work_before_bytes=at_reserve - 1, ending_before_bytes=at_reserve)
    assert plan['checkpoints']['work']['remaining_bytes'] == MAX_FRAME_BYTES + 1
    assert plan['checkpoints']['ending']['remaining_bytes'] == MAX_FRAME_BYTES
    with pytest.raises(ControlError, match='Insufficient pending capture headroom for ending capture'):
        packages.capture_headroom(profile, work_before_bytes=12802, ending_before_bytes=at_reserve + 1)


def test_offline_capture_check_uses_the_frozen_manifest_without_launching(tmp_path, capsys):
    directory, profile = package(tmp_path)
    profile['limits']['max_bytes'] = 3 * MAX_FRAME_BYTES
    profile['ending_reserve']['frame_bytes'] = MAX_FRAME_BYTES
    manifest = directory/'manifest.json'
    manifest.write_text(json.dumps(profile))
    with patch.object(packages, 'ROOT', tmp_path), git(), patch.object(packages.subprocess, 'run') as adapter:
        assert packages.main(['--run', str(directory), '--work-before-bytes', '12802',
                              '--ending-before-bytes', '524288']) == 0
        adapter.assert_called_once()
        assert adapter.call_args.args[0][2] == 'validate'
        assert adapter.call_args.kwargs['env'].keys() == {'PATH', 'LANG'}
    result = json.loads(capsys.readouterr().out)
    assert result == dict(session=profile['session'], manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                          total_bytes=3*MAX_FRAME_BYTES, pending_capture_bytes=MAX_FRAME_BYTES,
                          ending_reserve_bytes=MAX_FRAME_BYTES, checkpoints={
                              'work': {'retained_bytes': 12802, 'remaining_bytes': 3*MAX_FRAME_BYTES-12802},
                              'ending': {'retained_bytes': 524288, 'remaining_bytes': 3*MAX_FRAME_BYTES-524288},
                          })
    assert not (directory/'started.json').exists() and not (directory/'session.sqlite3').exists()


def test_capture_plan_rejects_a_backwards_retained_byte_forecast(tmp_path):
    _, profile = package(tmp_path)
    with pytest.raises(ControlError):
        packages.capture_headroom(profile, work_before_bytes=8, ending_before_bytes=7)


def test_capture_plan_hash_names_the_manifest_bytes_it_validated(tmp_path, capsys):
    directory, profile = package(tmp_path)
    profile['limits']['max_bytes'] = 3 * MAX_FRAME_BYTES
    manifest = directory/'manifest.json'
    manifest.write_text(json.dumps(profile))
    original_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()

    def replace_manifest(*args, **kwargs):
        replacement = {**profile, 'limits': {**profile['limits'], 'max_bytes': MAX_FRAME_BYTES}}
        manifest.write_text(json.dumps(replacement))

    with patch.object(packages, 'ROOT', tmp_path), git(), patch.object(packages.subprocess, 'run', replace_manifest):
        assert packages.main(['--run', str(directory), '--work-before-bytes', '12802']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['total_bytes'] == 3 * MAX_FRAME_BYTES
    assert result['manifest_sha256'] == original_hash != hashlib.sha256(manifest.read_bytes()).hexdigest()


def test_knowledge_is_required_private_hashes_are_closed_and_reserve_covers_both_bounds(tmp_path):
    directory,profile=package(tmp_path)
    # Empty knowledge contributes zero to the recall part of the reserve.
    profile['ending_reserve']['usd']='0.00063'
    (directory/'manifest.json').write_text(json.dumps(profile))
    assert validate(directory,tmp_path)
    tmp_path = tmp_path/'with-knowledge'
    directory,profile=package(tmp_path, knowledge=KNOWLEDGE)
    profile['ending_reserve']['usd']='0.00063'
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


def test_preflight_requires_room_for_ordinary_work_beyond_ending_reserve_and_bound(tmp_path):
    """Ballot 7: `ending_reserve.usd + reserve_bound < spend_limit_usd` prevents Turn-1 deadlock."""
    directory, profile = package(tmp_path)
    # Empty knowledge: reserve_bound == 0.00063; spend_limit_usd == 1.
    for reserve_usd in ('0.99937', '0.9995'):
        profile['ending_reserve']['usd'] = reserve_usd
        (directory/'manifest.json').write_text(json.dumps(profile))
        with pytest.raises(ControlError, match='below spend_limit_usd'):
            validate(directory, tmp_path)
    profile['ending_reserve']['usd'] = '0.99936'
    (directory/'manifest.json').write_text(json.dumps(profile))
    assert validate(directory, tmp_path)
    with_kb = tmp_path / 'with-kb'
    directory, profile = package(with_kb, knowledge=KNOWLEDGE)
    # Populated knowledge: reserve_bound == 0.00126 (player + recall); equality fails.
    profile['ending_reserve']['usd'] = '0.99874'
    (directory/'manifest.json').write_text(json.dumps(profile))
    with pytest.raises(ControlError, match='below spend_limit_usd'):
        validate(directory, with_kb)
    profile['ending_reserve']['usd'] = '0.99873'
    (directory/'manifest.json').write_text(json.dumps(profile))
    assert validate(directory, with_kb)


def test_live_knowledge_updates_is_a_required_boolean_that_reserves_a_recall_and_excludes_withholding(tmp_path):
    """R-OVERSPEND: a recall can follow a version adopted from an empty frozen file, so the reserve holds its bound.
    A newer version is exported whole, so it cannot be combined with a withholding draw."""
    directory,profile=package(tmp_path/'empty',live=True)
    profile['ending_reserve']['usd']='0.00063'
    (directory/'manifest.json').write_text(json.dumps(profile))
    with pytest.raises(ControlError,match=r'ending_reserve\.usd 0\.00063 must be at least unpriced_request_usd 0\.00126'):
        validate(directory,tmp_path/'empty')
    profile['ending_reserve']['usd']='0.00126'
    (directory/'manifest.json').write_text(json.dumps(profile))
    assert validate(directory,tmp_path/'empty')[0]['live_knowledge_updates'] is True
    for value in (None,'true',1,0):
        profile['live_knowledge_updates']=value
        (directory/'manifest.json').write_text(json.dumps(profile))
        with patch.object(packages,'ROOT',tmp_path/'empty'),git(),patch.object(packages.subprocess,'run') as validator,\
                pytest.raises(ControlError,match='live_knowledge_updates must be true or false'):packages.preflight(directory)
        assert not validator.called
    del profile['live_knowledge_updates']
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path/'empty'),git(),patch.object(packages.subprocess,'run'),\
            pytest.raises(ControlError,match='Invalid mechanical object fields'):packages.preflight(directory)
    # A seeded draw, even one that withheld nothing, and a study draw both refuse live updates; the same packages pass without them.
    for name,seed,live in (('seeded',7,True),('seeded-frozen',7,False),('unseeded',None,True)):
        directory,profile=package(tmp_path/name,knowledge=KNOWLEDGE,live=live,seed=seed)
        if seed is None or not live:
            assert validate(directory,tmp_path/name)
            continue
        with patch.object(packages,'ROOT',tmp_path/name),git(),patch.object(packages.subprocess,'run') as validator,\
                pytest.raises(ControlError,match='cannot be combined with withholding'):packages.preflight(directory)
        assert not validator.called
    directory,profile=package(tmp_path/'study',knowledge=KNOWLEDGE,live=True)
    units=directory/'private/units.json'
    units.write_text(json.dumps(dict(json.loads(units.read_text()),schema='knowledge-units/2',draw_sha256='0'*64)))
    profile['private_files']['units.json']=hashlib.sha256(units.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path/'study'),git(),patch.object(packages.subprocess,'run'),\
            pytest.raises(ControlError,match='cannot be combined with withholding'):packages.preflight(directory)


@pytest.mark.parametrize('name',['knowledge-full.json','units.json'])
def test_private_knowledge_hash_mismatch_refuses_preflight(tmp_path,name):
    directory,profile=package(tmp_path)
    path=directory/'private'/name
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ControlError,match='Frozen private knowledge differs'):
        validate(directory,tmp_path)


@pytest.mark.parametrize('fault',['old','previous_package','previous_labelless','reservation_package','pre_delivery_package','attempt_limited_package','unscoped_package','frozen_knowledge_package','old_node','old_route','previous_route',
                                  'reservation_route','frozen_knowledge_route','untracked_adapter','partial','changed','dirty','credentials','different_lock'])
def test_invalid_selected_package_never_launches_or_opens_store(tmp_path,fault):
    directory,profile=package(tmp_path)
    if fault=='old':profile['schema']='campaign-run/1'
    # The version before delivery of a newer knowledge version to a running actor: no `live_knowledge_updates`.
    if fault=='frozen_knowledge_package':profile['schema']='campaign-run/11';del profile['live_knowledge_updates']
    if fault=='frozen_knowledge_route':rewrite_route(directory,profile,schema='player-host/8')
    if fault=='attempt_limited_package':profile['schema']='campaign-run/9'
    if fault=='unscoped_package':profile['schema']='campaign-run/10';profile['labels'].pop('world')
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
        rewrite_route(directory,profile,schema=dict(old_route='pi-player-host/7',previous_route='player-host/2',reservation_route='player-host/3')[fault])
    if fault=='partial':(directory/'started.json').write_text('{}')
    if fault=='changed':(directory/'prompt.txt').write_text('different')
    if fault=='different_lock':profile['shared_lock']=str(tmp_path/'another.lock')
    if fault=='credentials':
        path=directory/'target.json';target=json.loads(path.read_text());target['env']['API_KEY']='fixture'
        path.write_text(json.dumps(target));profile['files']['target.json']=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(profile))
    expected={'old':'inert history','previous_package':'inert history','previous_labelless':'inert history','reservation_package':'inert history',
              'attempt_limited_package':'inert history','unscoped_package':'inert history','frozen_knowledge_package':'inert history','old_node':'inert history','old_route':'inert history','previous_route':'inert history','reservation_route':'inert history',
              'frozen_knowledge_route':'inert history',
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
    assert validate(directory,tmp_path)[0]['labels']==dict(arm='ceiling',start='S1',scenario='Evacuee',lineage=None,admission=None,world=None)
    del profile['labels']
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,\
            pytest.raises(ControlError,match='Invalid mechanical object fields'):packages.preflight(directory)
    assert not validator.called


@pytest.mark.parametrize('labels',[
    'text',None,[],dict(arm='a',start='S1',scenario='x',lineage=None,world=None),
    dict(arm='a',start='S1',scenario='x',lineage=None,admission=None,world=None,extra=1),
    dict(arm='a',start='S1',scenario='x',lineage=None,admission=None),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=1,world=None),
    *[dict(arm='a',start='S1',scenario='x',lineage=None,admission=None,world=world)
      for world in ('', 'w'*41, 'forêt', 'town\n', 2)],
    dict(arm='',start='S1',scenario='x',lineage=None,admission=None,world='w'),
    dict(arm='a'*41,start='S1',scenario='x',lineage=None,admission=None,world='w'),
    dict(arm='a',start='S'*41,scenario='x',lineage=None,admission=None,world='w'),
    dict(arm='a',start='S1',scenario='x'*81,lineage=None,admission=None,world='w'),
    dict(arm='a',start='S1',scenario='',lineage=None,admission=None,world='w'),
    dict(arm='a',start='S1',scenario='x',lineage='',admission=1,world='w'),
    dict(arm='a',start='S1',scenario='x',lineage='l'*41,admission=1,world='w'),
    dict(arm=None,start='S1',scenario='x',lineage=None,admission=None,world='w'),
    dict(arm=1,start='S1',scenario='x',lineage=None,admission=None,world='w'),
    dict(arm='café',start='S1',scenario='x',lineage=None,admission=None,world='w'),
    dict(arm='a\nb',start='S1',scenario='x',lineage=None,admission=None,world='w'),
    dict(arm='a',start='S1\x00',scenario='x',lineage=None,admission=None,world='w'),
    dict(arm='a',start='S1',scenario='x\x7f',lineage=None,admission=None,world='w'),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=None,world='w'),
    dict(arm='a',start='S1',scenario='x',lineage=None,admission=1,world='w'),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=0,world='w'),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=10001,world='w'),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission=True,world='w'),
    dict(arm='a',start='S1',scenario='x',lineage='l',admission='1',world='w'),
])
def test_invalid_operator_labels_refuse_before_effects(tmp_path,labels):
    directory,profile=package(tmp_path)
    profile['labels']=labels
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError):
        packages.preflight(directory)
    assert not validator.called


@pytest.mark.parametrize('labels',[
    dict(arm='a'*40,start='S99',scenario='x'*80,lineage='l'*40,admission=10000,world='w'*40),
    dict(arm='long-horizon',start='S2',scenario='Mixed printable ~!@# punctuation',lineage='survivor-1',admission=1,world='A'),
    dict(arm='ceiling',start='S1',scenario='Evacuee',lineage=None,admission=None,world=None),
    dict(arm='ceiling',start='S1',scenario='Evacuee',lineage=None,admission=None,world='World !@#'),
])
def test_valid_operator_labels_are_admitted(tmp_path,labels):
    directory,profile=package(tmp_path,world=labels['world'],lineage=labels['lineage'])
    profile['labels']=labels
    (directory/'manifest.json').write_text(json.dumps(profile))
    assert validate(directory,tmp_path)[0]['labels']==labels


@pytest.mark.parametrize('fault', ['missing', 'world', 'lineage', 'context', 'extra', 'delivered'])
def test_mismatched_private_selection_refuses_preflight_with_matching_manifest_hashes(tmp_path, fault):
    directory, profile = package(tmp_path, world='the farm')
    path = directory/'private/knowledge-full.json'
    full = json.loads(path.read_text())
    if fault == 'missing':
        del full['selection']
    elif fault == 'world':
        profile['labels']['world'] = 'another world'
    elif fault == 'lineage':
        profile['labels'].update(lineage='different lineage', admission=1)
    elif fault == 'context':
        profile['context'] = {'ruleset': 'different'}
    elif fault == 'extra':
        full['selection']['extra'] = 1
    else:
        delivered = directory/'delivered-knowledge.json'
        delivered.write_bytes(delivered.read_bytes() + b'\n')
        profile['files'][delivered.name] = hashlib.sha256(delivered.read_bytes()).hexdigest()
    path.write_text(json.dumps(full))
    profile['private_files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages, 'ROOT', tmp_path), git(), patch.object(packages.subprocess, 'run') as validator:
        with pytest.raises(ControlError, match='Private knowledge selection differs'):
            packages.preflight(directory)
    validator.assert_not_called()


def test_a_current_package_with_a_private_export_of_the_retired_knowledge_version_refuses_preflight(tmp_path):
    """R-REGRESSION (B5), S-MIGRATION: a `/13` package whose private full export is `delivered-knowledge/2` is
    refused even when its hashes and selection match the manifest."""
    directory, profile = package(tmp_path, world='the farm')
    path = directory/'private/knowledge-full.json'
    full = json.loads(path.read_text())
    assert full['schema'] == 'delivered-knowledge/3' and full['selection']['world'] == 'the farm'
    path.write_text(json.dumps(dict(full, schema='delivered-knowledge/2')))
    profile['private_files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages, 'ROOT', tmp_path), git(), patch.object(packages.subprocess, 'run') as validator:
        with pytest.raises(ControlError, match='Unsupported private full knowledge'):
            packages.preflight(directory)
    validator.assert_not_called()


@pytest.mark.parametrize('when',['before','during'])
def test_prelaunch_cancellation_does_not_wait_for_target_or_admit_actor(tmp_path,when):
    directory,profile=package(tmp_path)
    logs=tmp_path/'.runtime/logs'
    assert not logs.exists()
    handlers={};calls=[]
    def install(sig,handler):
        prior=handlers.get(sig);handlers[sig]=handler;return prior
    class Owner:
        channel=None
        def __init__(self,*args):pass
        def reserve(self):
            if when=='before':handlers[signal.SIGTERM](signal.SIGTERM,None)
        def start(self):
            assert logs.is_dir()
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
    assert logs.exists() == (when == 'during')
    assert result['schema']=='campaign-receipt/7'
    # No host was started, so nothing was spent and the record is complete.
    assert result['accounting']==dict(spend_limit_usd='1',reported_usd='0',unpriced_requests=0,unpriced_recall_requests=0,unpriced_request_usd='0.00063',unpriced_recall_request_usd='0.00063',
        spent_usd='0',observed_attempts=0,observed_recall_attempts=0,spend_complete=True)
    assert result['deciding_hosts_quiescent']
    assert 'Cancelled' in result['reason']


def test_receipt_spend_preserves_reported_cost_and_unknown_attempt_counts():
    profile=dict(spend_limit_usd='5');route=dict(recall=dict(unpriced_request_usd='0'),unpriced_request_usd='0.4096')
    driver=dict(reported_usd='0.1337',unpriced_requests=2,unpriced_recall_requests=0,observed_attempts=31,observed_recall_attempts=0,spend_complete=True)
    assert campaign_run.accounting(profile,route,driver,True)==dict(spend_limit_usd='5',reported_usd='0.1337',unpriced_requests=2,unpriced_recall_requests=0,
        unpriced_request_usd='0.4096',unpriced_recall_request_usd='0',spent_usd='0.1337',observed_attempts=31,observed_recall_attempts=0,spend_complete=True)
    # Hosts were started but the driver left no record: there are no observed starts and the spend is incomplete.
    lost=campaign_run.accounting(profile,route,None,True)
    assert (lost['observed_attempts'],lost['spent_usd'],lost['spend_complete'])==(0,'0',False)


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


def test_a_reserve_below_one_in_flight_request_or_a_zero_bound_refuses_the_package(tmp_path):
    """The package needs a positive planning bound and enough reserve for an in-flight request."""
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
            pytest.raises(ControlError,match='give no in-flight request bound'):
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


@pytest.mark.parametrize('field',['seconds','inputs','requests','frames','frame_bytes'])
@pytest.mark.parametrize('fault',['missing','zero','over','boolean'])
def test_invalid_original_ending_reserves_refuse_before_effects(tmp_path,field,fault):
    directory,profile=package(tmp_path)
    if fault=='missing':profile['ending_reserve'].pop(field)
    else:profile['ending_reserve'][field]={'zero':0,'over':10**12,'boolean':True}[fault]
    (directory/'manifest.json').write_text(json.dumps(profile))
    with patch.object(packages,'ROOT',tmp_path),git(),patch.object(packages.subprocess,'run') as validator,pytest.raises(ControlError):
        packages.preflight(directory)
    assert not validator.called and not (directory/'started.json').exists()


# A curator reader process in the admission order of the live curator design: open the existing
# lock, take it shared, refuse on the marker, then hold one read transaction for argv[2] seconds.
READER='''import fcntl,os,sqlite3,sys,time
from pathlib import Path
directory=Path(sys.argv[1]);descriptor=os.open(directory/'curator-read.lock',os.O_RDONLY)
fcntl.flock(descriptor,fcntl.LOCK_SH|fcntl.LOCK_NB)
assert not (directory/'store-closing.json').exists()
db=sqlite3.connect((directory/'session.sqlite3').as_uri()+'?mode=ro',uri=True)
db.execute('BEGIN');db.execute('SELECT count(*) FROM actors').fetchone()
print('admitted',flush=True);time.sleep(float(sys.argv[2]))
db.close();os.close(descriptor)
'''


def live_store(directory):
    from harness.computer.store import SessionStore
    store=SessionStore(directory,'a'*32,dict(max_inputs=1,max_requests=1,max_frames=1,max_bytes=1),time.monotonic()+60)
    store.add_actor('actor','0'*64)
    return store


def reader(directory,hold):
    process=subprocess.Popen([sys.executable,'-c',READER,str(directory),str(hold)],stdout=subprocess.PIPE,text=True)
    try:assert process.stdout.readline()=='admitted\n'
    except BaseException:
        stop(process);raise
    return process


def stop(process):
    process.kill();process.wait(5);process.stdout.close()


def close_out(directory,store):
    errors={}
    def attempt(name,function):
        try:return function()
        except BaseException as exc:errors[name+'_error']=type(exc).__name__
    started=time.monotonic();campaign_run.close_store(directory,'a'*32,store.close,attempt)
    return time.monotonic()-started,errors


def test_close_out_waits_for_an_admitted_read_and_leaves_a_sealed_store(tmp_path):
    from harness.trace.stores import sealed
    store=live_store(tmp_path);(tmp_path/'curator-read.lock').touch()
    process=reader(tmp_path,.5)
    try:
        before=time.time();elapsed,errors=close_out(tmp_path,store)
        assert process.wait(5)==0 and errors=={}
    finally:stop(process)
    # No lower limit on the wait: had it not waited, the log below would be non-empty.
    assert elapsed<campaign_run.READ_HOLD_BOUND_SECONDS
    wal=tmp_path/'session.sqlite3-wal'
    assert not wal.exists() or wal.stat().st_size==0
    with sealed(tmp_path/'session.sqlite3') as db:assert db.execute('SELECT id FROM actors').fetchall()==[('actor',)]
    marker=json.loads((tmp_path/'store-closing.json').read_text())
    assert marker.keys()=={'schema','session','closing_wall'} and marker['schema']=='store-closing/1'
    assert marker['session']=='a'*32 and before<=marker['closing_wall']<=time.time()


def test_close_out_stops_waiting_at_the_read_bound_and_still_closes(tmp_path):
    from harness.trace.stores import SealedStoreError,sealed
    store=live_store(tmp_path);(tmp_path/'curator-read.lock').touch()
    process=reader(tmp_path,60)
    try:
        elapsed,errors=close_out(tmp_path,store)
        assert errors=={} and campaign_run.READ_HOLD_BOUND_SECONDS<=elapsed<campaign_run.READ_HOLD_BOUND_SECONDS+1
        with pytest.raises(Exception,match='closed'):store.counts()
        # The residual: a read held past the bound keeps the log, and the sealed check refuses it.
        assert (tmp_path/'session.sqlite3-wal').stat().st_size>0
        with pytest.raises(SealedStoreError),sealed(tmp_path/'session.sqlite3'):pass
    finally:stop(process)
    assert (tmp_path/'store-closing.json').exists()


def test_a_failed_marker_or_lock_step_is_recorded_and_the_store_still_closes(tmp_path):
    from harness.trace.stores import sealed
    store=live_store(tmp_path);(tmp_path/'curator-read.lock').touch(mode=0);(tmp_path/'store-closing.json').write_text('{}')
    elapsed,errors=close_out(tmp_path,store)
    assert errors=={'store_closing_marker_error':'FileExistsError','curator_read_wait_error':'PermissionError'}
    assert elapsed<campaign_run.READ_HOLD_BOUND_SECONDS
    with sealed(tmp_path/'session.sqlite3') as db:assert db.execute('SELECT id FROM actors').fetchall()==[('actor',)]


def test_close_out_without_a_configured_reader_writes_no_marker_and_does_not_wait(tmp_path):
    from harness.trace.stores import sealed
    store=live_store(tmp_path)
    elapsed,errors=close_out(tmp_path,store)
    assert errors=={} and elapsed<.25 and not (tmp_path/'store-closing.json').exists()
    with sealed(tmp_path/'session.sqlite3') as db:assert db.execute('SELECT count(*) FROM actors').fetchone()==(1,)


@pytest.mark.parametrize('live',[False,True])
def test_the_store_closes_only_after_input_authority_is_revoked(tmp_path,live):
    directory,profile=package(tmp_path,live=live)
    events=[];channel=Mock();channel.stopped=threading.Event()
    class Owner:
        def __init__(self,*args):self.channel=None;self.process=Mock(pid=4242)
        def reserve(self):pass
        def start(self):self.channel=channel;return channel
        def wait_target(self):pass
        def close(self):
            events.append('native_cleanup');channel.stopped.set()
            return dict(native_absence_verified=True,normal_native_exit_zero=True)
    runtime=Mock();runtime.stop.side_effect=lambda reason:events.append('pause')
    server=Mock();server.shutdown.side_effect=lambda:events.append('server_shutdown')
    def close_store(directory,session,close,attempt):
        assert channel.stopped.is_set();events.append('close_store')
    driver=dict(outcome='player_task_complete_unassessed',actors=[],reported_usd='0',unpriced_requests=0,unpriced_recall_requests=0,
                observed_attempts=0,observed_recall_attempts=0,spend_complete=True)
    with patch.object(campaign_run,'preflight',return_value=(profile,dict(api_key_env='OFFLINE_KEY',unpriced_request_usd='0.00063',recall=dict(unpriced_request_usd='0.00063')),{})),\
            patch.object(campaign_run,'OwnedTarget',Owner),patch.object(campaign_run,'ComputerRuntime',return_value=runtime),\
            patch.object(campaign_run,'Journal'),patch.object(campaign_run,'Application'),\
            patch.object(campaign_run,'serve',return_value=(server,Mock())),patch.object(campaign_run,'run_hosts',return_value=driver) as hosts,\
            patch.object(campaign_run,'close_store',close_store),patch.object(campaign_run.signal,'signal'),\
            patch.dict(os.environ,{'OFFLINE_KEY':'fixture-secret'}):
        result=campaign_run.run_campaign(directory)
    # Only a package that delivers newer knowledge versions gives the driver the runner's delivery directory.
    assert hosts.call_args.args[7]==(directory.resolve()/'curator-runner'/'delivered' if live else None)
    assert events==['pause','native_cleanup','server_shutdown','close_store']
    assert result['input_authority_revoked'] and not [key for key in result if key.endswith('_error')]


@pytest.mark.parametrize('suffix,returncode,native_signals,expected',[
    ('',0,[],'player_task_complete_unassessed'),
    (' READ_CONTROL',0,[],'player_external_stop_complete_unassessed'),
    ('',1,[],'interrupted'),
    ('',-11,[],'interrupted'),
    ('',0,['SIGTERM'],'interrupted'),
    ('',0,['SIGKILL'],'interrupted'),
    (' NO_FINISH',0,[],'interrupted'),
    (' HOST_FAILURE',0,[],'interrupted'),
])
def test_cli_uses_host_finish_and_owned_native_exit_evidence(tmp_path,monkeypatch,capsys,suffix,returncode,native_signals,expected):
    from tests.test_campaign_player import driver_case,fence_on_host_settlement

    directory,profile=package(tmp_path)
    host_profile,route,application=driver_case(directory,'Frozen mission'+suffix)
    profile.update(host_profile)
    runtime=application.runtime
    runtime.store=Mock()
    runtime.channel.stop=Mock()
    fence_on_host_settlement(monkeypatch,runtime)
    native_calls=[]

    class Owner:
        channel=None
        process=Mock(pid=4242)

        def __init__(self,*args):pass
        def reserve(self):pass
        def wait_target(self):pass
        def start(self):
            self.channel=runtime.channel
            return self.channel
        def close(self):
            assert self.channel.stopped.is_set()
            native_calls.append('close')
            return dict(native_absence_verified=True,normal_native_exit_zero=returncode==0,
                native=dict(returncode=returncode,signals=native_signals))

    monkeypatch.setattr(campaign_run,'preflight',lambda directory:(profile,route,{}))
    monkeypatch.setattr(campaign_run,'OwnedTarget',Owner)
    monkeypatch.setattr(campaign_run,'ComputerRuntime',Mock(return_value=runtime))
    monkeypatch.setattr(campaign_run,'Journal',Mock())
    monkeypatch.setattr(campaign_run,'Application',Mock(return_value=application))
    monkeypatch.setattr(campaign_run,'serve',lambda *args:(Mock(),Mock()))
    monkeypatch.setenv('FIXTURE_KEY','fixture-secret')

    code=campaign_run.main(['--run',str(directory)])
    report=json.loads(capsys.readouterr().out)
    assert code==int(expected=='interrupted'),report
    assert report==json.loads((directory/'receipt.json').read_text())
    assert report['outcome']==report['driver']['outcome']==expected
    assert report['normal_native_exit_zero']==(returncode==0 and not native_signals)
    assert report['cleanup']['native']==dict(returncode=returncode,signals=native_signals)
    assert report['input_authority_revoked'] and native_calls==['close']
    actor,=report['driver']['actors']
    assert actor['accounting_complete'] and actor['settled']['ok']==('HOST_FAILURE' not in suffix)
    if 'READ_CONTROL' in suffix:assert report['driver']['ending_request']['trigger']=='spend'


def test_cli_keeps_operator_signal_during_clean_eof_as_interrupted(tmp_path,monkeypatch,capsys):
    from tests.test_campaign_player import driver_case,fence_on_host_settlement

    directory,profile=package(tmp_path)
    host_profile,route,application=driver_case(directory,'Frozen mission')
    profile.update(host_profile)
    runtime=application.runtime
    runtime.store=Mock()
    runtime.channel.stop=Mock()
    fence_on_host_settlement(monkeypatch,runtime)
    handlers={}
    real_signal=campaign_run.signal.signal

    def capture_signal(sig,handler):
        handlers[sig]=handler
        return real_signal(sig,handler)

    class Owner:
        channel=None
        process=Mock(pid=4242)

        def __init__(self,*args):pass
        def reserve(self):pass
        def wait_target(self):pass
        def start(self):
            self.channel=runtime.channel
            return self.channel
        def close(self):
            handlers[campaign_run.signal.SIGINT](campaign_run.signal.SIGINT,None)
            return dict(native_absence_verified=True,normal_native_exit_zero=True,
                native=dict(returncode=0,signals=[]))

    monkeypatch.setattr(campaign_run,'preflight',lambda directory:(profile,route,{}))
    monkeypatch.setattr(campaign_run,'OwnedTarget',Owner)
    monkeypatch.setattr(campaign_run,'ComputerRuntime',Mock(return_value=runtime))
    monkeypatch.setattr(campaign_run,'Journal',Mock())
    monkeypatch.setattr(campaign_run,'Application',Mock(return_value=application))
    monkeypatch.setattr(campaign_run,'serve',lambda *args:(Mock(),Mock()))
    monkeypatch.setattr(campaign_run.signal,'signal',capture_signal)
    monkeypatch.setenv('FIXTURE_KEY','fixture-secret')

    code=campaign_run.main(['--run',str(directory)])
    report=json.loads(capsys.readouterr().out)
    assert code==1
    assert report['outcome']==report['driver']['outcome']=='interrupted'
    assert report['normal_native_exit_zero'] is True
