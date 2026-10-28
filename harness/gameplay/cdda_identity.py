"""Visible CDDA identity interpretation, separate from shared memory semantics."""
from .contracts import ContractError

IDENTITY_UNIT = "name"
IDENTITY_COVERAGE = {"world": "visible-world-menu", "character": "visible-character-screen"}


def validate_identity_claim(claim: dict) -> None:
    key = claim["key"]
    if key["property"] == "identity" and (claim["kind"] != "interpretation"
            or key["subject"] not in IDENTITY_COVERAGE or key["unit"] != IDENTITY_UNIT
            or key["coverage_id"] != IDENTITY_COVERAGE[key["subject"]]
            or claim["value"]["quantity"] is not None):
        raise ContractError("Identity is a fallible visible world/menu or character/screen name")
