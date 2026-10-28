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


def adoption_identity_refusal(claim: dict, *, subject: str, scope: dict, name: str,
                              claims: dict[str, dict], frontiers: list[list[str]],
                              retired: set[str]) -> str | None:
    """Applicability only; callers separately authenticate history and evidence."""
    if claim["value"] != {"quantity": None, "state": name}:
        return (f"Normal adoption {subject} identity value must equal the admitted name {name!r}; "
            f"selected Claim state preview: {repr(claim['value']['state'])[:160]}. "
            "Interpret the retained evidence and explicitly correct the Claim before adopting.")
    if (claim["kind"] != "interpretation" or claim["scope"] != scope
            or claim["key"] != dict(subject=subject, property="identity", unit=IDENTITY_UNIT,
                coverage_id=IDENTITY_COVERAGE[subject])
            or claim["status"] not in ("current", "last_seen")):
        return "Select a current visible identity Claim with the exact expected key and scope"
    if (not claim["sources"] or not claim["supports"]
            or any(group["claims"] or not group["sources"]
                or not set(group["sources"]) <= set(claim["sources"]) for group in claim["supports"])
            or set(claim["sources"]) != {source for group in claim["supports"] for source in group["sources"]}):
        return "Identity needs direct retained source support without unsupported annotations"
    frontier_ids = {identity for frontier in frontiers for identity in frontier}
    if claim["id"] in retired or claim["id"] not in frontier_ids:
        return "Select a current identity frontier Claim; this Claim was replaced"
    frontier = next(frontier for frontier in frontiers if claim["id"] in frontier)
    if any(claims[identity]["value"] != claim["value"]
            or claims[identity]["observed_time"] != claim["observed_time"]
            for identity in frontier if identity not in retired):
        return "Explicitly correct conflicting or incomparable identity frontier Claims"
    if any(other["id"] != claim["id"] and other["id"] in frontier_ids - retired
            and other["scope"] == scope
            and all(other["key"][key] == claim["key"][key] for key in ("subject", "property", "unit"))
            and (other["value"] != claim["value"] or other["status"] in ("disputed", "retired", "unknown"))
            for other in claims.values()):
        return "Explicitly correct conflicting durable identity Claims"
    return None
