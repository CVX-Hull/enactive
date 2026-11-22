"""Player and recall reserves use the adapter-validated maximum endpoint rates."""
from decimal import Decimal

import pytest

from tools.campaign_package import unpriced_request_usd


@pytest.mark.parametrize("context, output, expected", [(1000, 100, "0.0047"), (2000, 200, "0.0094")],
    ids=["player", "recall"])
def test_unpriced_request_bound_uses_per_category_maximum_rates(context, output, expected):
    route = dict(
        endpoint_costs={
            "primary": dict(input=2, output=7, cacheRead=0.1, cacheWrite=0),
            "secondary": dict(input=1, output=3, cacheRead=0, cacheWrite=4),
        },
        model=dict(contextWindow=context, maxTokens=output,
            cost=dict(input=2, output=7, cacheRead=0.1, cacheWrite=4)),
    )
    bound = unpriced_request_usd(route)
    assert bound == Decimal(expected)
    for costs in route["endpoint_costs"].values():
        assert bound > unpriced_request_usd(dict(model=dict(route["model"], cost=costs)))
