"""Generated lead-side MCP entries derive tools and paths from source only."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from harness.player_tools import tool_specs
from tools.configure_player_tools import FORMATS,ROOT,SERVER,coding_agent_configuration


def test_json_entry_launches_current_adapter_for_explicit_actor(tmp_path):
    value=json.loads(coding_agent_configuration('/project/actor.json','mcp-servers-json',tmp_path))
    entry=value['mcpServers'][SERVER]
    assert entry==dict(type='stdio',command=str(tmp_path/'.venv/bin/python'),
        args=['-m','harness.player_mcp','--actor-config','/project/actor.json'],env=dict(PYTHONPATH=str(tmp_path)))


def test_toml_entry_enables_exactly_current_tool_schema(tmp_path):
    value=tomllib.loads(coding_agent_configuration('/project/actor.json','mcp-servers-toml',tmp_path))
    entry=value['mcp_servers'][SERVER]
    assert entry['enabled_tools']==list(tool_specs()) and entry['enabled'] is True
    assert entry['cwd']==str(tmp_path) and entry['command']==str(tmp_path/'.venv/bin/python')
    assert entry['args'][-1]=='/project/actor.json'


def test_unknown_format_is_rejected():
    assert set(FORMATS)=={'mcp-servers-json','mcp-servers-toml'}
    with pytest.raises(ValueError):coding_agent_configuration('/project/actor.json','yaml')


@pytest.mark.parametrize('arguments',[
    ['--coding-agent-format','mcp-servers-json','--template','--output','.runtime/never.json'],
    ['--coding-agent-format','mcp-servers-toml','--actor-config','/etc/hosts','--output','.runtime/never.toml'],
])
def test_entries_need_an_explicit_project_local_actor(arguments):
    result=subprocess.run([sys.executable,'-m','tools.configure_player_tools',*arguments],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode!=0 and not Path(ROOT/arguments[-1]).exists()
