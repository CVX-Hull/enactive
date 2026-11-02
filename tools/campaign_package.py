"""Read one frozen current campaign package; never inspect unrelated history."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import os
from pathlib import Path
import re
import subprocess

from harness.computer.protocol import ControlError,closed,integer,read_json
from harness.player import recall
from harness.prepared_app import game_lock_path
from tools.configure_player_tools import ROOT,configuration

FILES={'route.json','mcp-template.json','context.txt','prompt.txt','target.json'}
FIELDS={'schema','session','source_commit','files','initial_files','native','library','shared_lock','player_store',
        'host','effort','port','wall_seconds','host_seconds','total_host_seconds','max_hosts','max_http_attempts','limits','accounting',
        'actor_profile','level'}
# Level v4 (ADR-007): the level's own allowance, the episode cutter, the recorder and the derived-state parameters.
LEVEL_FIELDS={'mode','episode_cap','staleness_inputs','budget_fractions','intent_tail_bytes',
              'max_http_attempts','pass_max_requests','pass_seconds',
              'theta','theta_fitting_sha256','min_episode_inputs','stall_settles','confidence_floor','recall','recorder'}
RECORDER_FIELDS={'max_http_attempts','pass_max_requests','pass_seconds','backlog'}
RECALL_FIELDS={'tail_top','tail_exploration','level_items'}
# The owner's K: the longest run of inputs between wakes, which is also the episode cap C (ADR-007 owner parameters).
OWNER_K=10
# The frozen, versioned role prompts (ADR-007 appendix); a change makes a new version and a new digest here.
LEVEL_ROLE=ROOT/'tools/player_roles/subgoal-v4.txt'
EPISODE_ROLE=ROOT/'tools/player_roles/episode-v1.txt'
FROZEN_ROLE_SHA256={
    'subgoal-v4.txt':'08c8558f659dacb1feb61c81b1286e91dca24e8808eab8e5d0b5e56cf53aaad8',
    'episode-v1.txt':'a6c326069bd8fec86bf2c30bcbcf34e51e34f5d1371f5ac32f764b664869a910'}


def level_profile(level,actor_profile:str):
    """Validate the optional subgoal level and episode recorder; null is the zero-level-host configuration."""
    if level is None:return None
    closed(level,LEVEL_FIELDS)
    if actor_profile!='narrowed':raise ControlError('A subgoal level serves only a narrowed-profile actor')
    if level['mode'] not in ('shadow','live'):raise ControlError('Level mode is shadow or live')
    for name,low,high in (('episode_cap',1,1000),('staleness_inputs',1,1000),('intent_tail_bytes',64,4096),
                         ('max_http_attempts',1,10000),('pass_max_requests',1,64),('pass_seconds',30,3600),
                         ('min_episode_inputs',1,1000),('stall_settles',1,1000)):
        integer(level[name],low,high)
    if level['episode_cap']!=OWNER_K:raise ControlError(f'The episode cap C must equal the owner\'s K ({OWNER_K})')
    if level['min_episode_inputs']>level['episode_cap']:raise ControlError('The minimum episode length m cannot exceed the cap C')
    # theta is fitted per game from player-visible captures; it is frozen by value and by the digest of its fitting.
    theta=level['theta']
    if type(theta) is not float or not 0<theta<1:raise ControlError('The episode threshold theta is a float strictly between 0 and 1')
    if not isinstance(level['theta_fitting_sha256'],str) or re.fullmatch('[0-9a-f]{64}',level['theta_fitting_sha256']) is None:
        raise ControlError('Freeze theta with the SHA256 of its fitting')
    floor=level['confidence_floor']
    if type(floor) is not float or not 0<=floor<=1:raise ControlError('The confidence floor c is a float from 0 to 1')
    fractions=level['budget_fractions']
    if (type(fractions) is not list or len(fractions)>8 or any(type(f) is not float or not 0<f<1 for f in fractions)
            or fractions!=sorted(set(fractions))):raise ControlError('Budget fractions are at most 8 increasing values in (0,1)')
    # The recall sizes are fixed by the custodian; the profile records them and refuses any other value.
    closed(level['recall'],RECALL_FIELDS)
    if level['recall']!=dict(tail_top=recall.TAIL_TOP_ITEMS,tail_exploration=1,level_items=recall.LEVEL_ITEMS):
        raise ControlError('The recall sizes differ from the custodian\'s (2 top and 1 exploration line in the tail, 10 for the level)')
    recorder=level['recorder']
    closed(recorder,RECORDER_FIELDS)
    for name,low,high in (('max_http_attempts',1,10000),('pass_max_requests',1,64),('pass_seconds',30,3600),('backlog',1,16)):
        integer(recorder[name],low,high)
    return level


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        value=hashlib.file_digest(stream,'sha256').hexdigest()
    return value


def local_file(value: str) -> Path:
    path=Path(value)
    if not path.is_absolute() or path!=path.resolve() or not path.is_relative_to(ROOT) or path.is_symlink() or not path.is_file():
        raise ControlError('Frozen artifact must be a canonical project-local regular file')
    return path


def host_argv(host) -> list[str]:
    """Validate the closed `player-host/6` adapter selection and return its argv."""
    closed(host,{'argv'})
    argv=host['argv']
    if (type(argv) is not list or not 1<=len(argv)<=8
            or any(type(a) is not str or not a or len(a)>8192 for a in argv)):
        raise ControlError('Select explicit bounded player host argv')
    executable=Path(argv[0])
    if not executable.is_absolute() or not executable.is_file():
        raise ControlError('Player host argv[0] must be an absolute existing regular file')
    for entry in argv[1:]:local_file(entry)
    return argv


def preflight(directory: Path) -> tuple[dict,dict,dict]:
    directory=directory.resolve(strict=True)
    if not directory.is_relative_to(ROOT/'.runtime/computer-sessions') or directory.is_symlink():
        raise ControlError('Select a fresh explicit project-local computer session package')
    profile=read_json(directory/'manifest.json',1048576)
    if type(profile) is not dict or profile.get('schema')!='campaign-run/5':
        raise ControlError('Unsupported campaign package; old admissions are inert history')
    closed(profile,FIELDS)
    host_argv(profile['host'])
    if profile['actor_profile'] not in ('flat','narrowed'):raise ControlError('Actor profile is flat or narrowed')
    level=level_profile(profile['level'],profile['actor_profile'])
    if not isinstance(profile['session'],str) or re.fullmatch('[0-9a-f]{32}',profile['session']) is None:
        raise ControlError('Invalid fresh mechanical session')
    current=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if profile['source_commit']!=current or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):
        raise ControlError('Campaign requires its exact inspected clean source checkpoint')
    # Clean status omits ignored files; tracked plus clean binds adapter bytes to the commit.
    adapter={str(Path(entry).relative_to(ROOT)) for entry in profile['host']['argv'][1:]}
    tracked=subprocess.check_output(['git','ls-files','-z','--',*sorted(adapter)],cwd=ROOT).split(b'\0') if adapter else []
    if adapter-{name.decode() for name in tracked if name}:
        raise ControlError('Player host adapter files must be tracked by the clean source commit')
    if set(profile['files'])!=FILES|({'level-role.txt','episode-role.txt'} if level else set()):
        raise ControlError('Freeze every selected driver input')
    if level:
        # Each role prompt is byte-identical to its frozen repository version, whose digest is pinned in this validator.
        for name,frozen in (('level-role.txt',LEVEL_ROLE),('episode-role.txt',EPISODE_ROLE)):
            if digest(frozen)!=FROZEN_ROLE_SHA256[frozen.name]:raise ControlError(f'{frozen.name} differs from its frozen digest; a change is a new version')
            if digest(directory/name)!=digest(frozen):raise ControlError(f'The {name} prompt must be the frozen current version ({frozen.name})')
    for name,sha in profile['files'].items():
        path=local_file(str(directory/name))
        if path.stat().st_size>1048576 or digest(path)!=sha:raise ControlError('Frozen driver input differs')
    for name in ('native','library'):
        closed(profile[name],{'path','sha256'})
        if digest(local_file(profile[name]['path']))!=profile[name]['sha256']:
            raise ControlError('Frozen target/adapter bytes differ')
    initial=profile['initial_files']
    if type(initial) is not dict or not 1<=len(initial)<=16:raise ControlError('Freeze bounded initial target files')
    for name,sha in initial.items():
        if digest(local_file(name))!=sha:raise ControlError('Initial target configuration differs')
    if any((directory/name).exists() for name in ('started.json','session.sqlite3','native-process.json','actors','contexts')):
        raise ControlError('Selected package has prior/partial application; never reopen it')
    lock=Path(profile['shared_lock']);player=Path(profile['player_store'])
    if lock!=game_lock_path(ROOT/'.runtime').resolve():
        raise ControlError('Current game admission must share the exact preparation/userdir lock')
    for path in (lock,player):
        if not path.is_absolute() or path!=path.resolve() or not path.is_relative_to(ROOT) or path.is_symlink():
            raise ControlError('Selected mutable store/lock must be canonical and project-local')
    closed(profile['limits'],{'max_inputs','max_requests','max_frames','max_bytes'})
    for value in profile['limits'].values():integer(value,1,2**40)
    for name,low,high in (('port',1024,65535),('wall_seconds',60,86400),('host_seconds',30,86400),
                         ('total_host_seconds',30,86400),('max_hosts',1,2),('max_http_attempts',1,10000)):
        integer(profile[name],low,high)
    if not profile['host_seconds']<=profile['total_host_seconds']<profile['wall_seconds']-30:
        raise ControlError('Original host and cleanup horizons do not fit')
    route=read_json(directory/'route.json',1048576)
    if type(route) is not dict or route.get('schema')!='player-host/6':
        raise ControlError('Unsupported player host route; old routes are inert history')
    if route.get('service_tier')!='default':raise ControlError('This campaign allocation supports only the selected default serving tier')
    # Only a live level publishes intent; shadow mode measures it without influencing play.
    tail=level['intent_tail_bytes'] if level and level['mode']=='live' else None
    if route.get('role')!='actor' or route.get('intent_tail_bytes',0)!=tail:
        raise ControlError('The frozen route must be the actor role with the level mode\'s intent tail')
    # Each actor, its level and its recorder are partitioned before launch within the campaign cap.
    if route['max_requests']+((level['max_http_attempts']+level['recorder']['max_http_attempts']) if level else 0)>profile['max_http_attempts']:
        raise ControlError('Per-host attempts exceed original campaign allowance')
    template=read_json(directory/'mcp-template.json',1048576)
    if template!=configuration('@ACTOR_CONFIG@',profile=profile['actor_profile']):raise ControlError('Only the current explicit actor MCP profile is supported')
    target=read_json(directory/'target.json',1048576)
    closed(target,{'argv','cwd','env'})
    if (type(target['argv']) is not list or not 1<=len(target['argv'])<=32
            or any(not isinstance(a,str) or not a or len(a)>8192 for a in target['argv'])
            or not Path(target['argv'][0]).is_absolute()):raise ControlError('Select explicit bounded target argv')
    if not Path(target['cwd']).is_absolute() or Path(target['cwd']).resolve()!=Path(target['cwd']) or not Path(target['cwd']).is_relative_to(ROOT):
        raise ControlError('Target working directory must be canonical and project-local')
    if type(target['env']) is not dict:raise ControlError('Select explicit target environment')
    for key,value in target['env'].items():
        if (key not in {'PATH','LANG','SDL_AUDIODRIVER','SDL_VIDEODRIVER','DYLD_LIBRARY_PATH','DYLD_FRAMEWORK_PATH'}
                or not isinstance(value,str) or len(value)>8192):raise ControlError('Target environment contains unsupported or credential settings')
    # Static refusals precede any adapter code; accounting below relies on the
    # adapter having accepted the route's closed model shape.
    subprocess.run([*profile['host']['argv'],'validate','--config',str(directory/'route.json'),
        '--mcp-config',str(directory/'mcp-template.json'),'--model',route['model']['id'],'--effort',profile['effort']],cwd=ROOT,check=True,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,
        env=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),LANG='en_US.UTF-8'))
    budget=profile['accounting']
    closed(budget,{'prior_attempts','prior_reserved_usd','ceiling_usd','prospective_reserved_usd'})
    integer(budget['prior_attempts'],0,10**9)
    for name in ('prior_reserved_usd','ceiling_usd','prospective_reserved_usd'):
        amount=Decimal(str(budget[name]))
        if not amount.is_finite() or amount<0:raise ControlError('Accounting amounts must be finite and nonnegative')
    costs=route['model']['cost']
    rate=max(Decimal(str(costs[k])) for k in ('input','cacheRead','cacheWrite'))
    per=(Decimal(route['model']['contextWindow'])*rate+Decimal(route['model']['maxTokens'])*Decimal(str(costs['output'])))/Decimal(10**6)
    prospective=Decimal(str(budget['prior_reserved_usd']))+per*profile['max_http_attempts']
    if prospective!=Decimal(str(budget['prospective_reserved_usd'])) or prospective>Decimal(str(budget['ceiling_usd'])):
        raise ControlError('Original conservative allocation does not fit selected cumulative ceiling')
    return profile,route,target
