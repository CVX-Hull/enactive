"""The only CLI execution route is the current frozen campaign."""
from unittest.mock import patch

import pytest

from harness.__main__ import main


def test_run_delegates_explicit_selected_package():
    with patch('tools.campaign_run.main',return_value=3) as run:
        assert main(['run','--run','selected'])==3
    run.assert_called_once_with(['--run','selected'])


@pytest.mark.parametrize('arguments',[
    ['mission-start'],['start'],['resume'],['status','--url','https://127.0.0.1:8766'],
    ['pause','--url','http://example.com:8766'],['status','--url','http://127.0.0.1:8766/old'],
])
def test_old_routes_and_nonlocal_targets_refuse(arguments):
    with patch('harness.__main__.urlopen') as send,pytest.raises(SystemExit):main(arguments)
    send.assert_not_called()
