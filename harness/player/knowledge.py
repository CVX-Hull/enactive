"""Read only the frozen, delivered subset. No curator or evaluation dependency."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .contracts import PlayerError

SCHEMA = 'delivered-knowledge/1'


def empty() -> dict:
    return dict(schema=SCHEMA, version=None, coverage=None, articles=[], facts=[])


class Knowledge:
    def __init__(self, path: Path):
        self.value = json.loads(path.read_text())
        if not isinstance(self.value, dict) or set(self.value) != {'schema', 'version', 'coverage', 'articles', 'facts'} \
                or self.value['schema'] != SCHEMA:
            raise PlayerError(f'{path}: unsupported delivered knowledge')
        self.records = self.value['articles'] + self.value['facts']

    def read(self, identity: str) -> dict:
        found = next((r for r in self.records if r['id'] == identity or r.get('title') == identity), None)
        return dict(schema='player-knowledge/1', version=self.value['version'], grants_authority=False,
                    records=[] if found is None else [copy.deepcopy(found)])

    def query(self, query: str) -> dict:
        words = query.casefold().split()
        records = [copy.deepcopy(r) for r in self.records
                   if all(w in json.dumps(r, ensure_ascii=False).casefold() for w in words)]
        return dict(schema='player-knowledge/1', version=self.value['version'], grants_authority=False, records=records)
