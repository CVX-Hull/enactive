"""Real application/MCP over the existing receiver stand-in, with frozen knowledge."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tests import player_service_fixture as fixture

knowledge = Path(sys.argv.pop(1))
application = fixture.Application
fixture.Application = lambda *args, **kwargs: application(*args, **dict(kwargs, knowledge=knowledge))
fixture.main()
