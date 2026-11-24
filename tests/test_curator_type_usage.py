"""Tag counts and near pairs in the current-store brief."""
from harness.curator import type_usage


def test_counts_include_current_facts_and_articles_and_drop_unused_tags():
    records = [
        dict(record='fact', tags=['fire', 'camp-fire']),
        dict(record='article', tags=['fire', 'stove-fire']),
        dict(record='fact', tags=['archived'], retired={}),
        dict(record='article', tags=['obsolete', 'fire'], superseded_by=['guide@v2']),
    ]
    assert type_usage.counts(records) == {'fire': 2, 'camp-fire': 1, 'stove-fire': 1}
    brief = '\n'.join(type_usage.section(records))
    assert '### Tags' in brief and "'fire': 2" in brief
    assert 'archived' not in brief and 'obsolete' not in brief and 'unused' not in brief


def test_near_pairs_use_only_tag_words_and_apply_the_overlap_threshold():
    assert type_usage.words('fire-wood-fire') == {'fire', 'wood'}
    assert type_usage.nearest(['fire-wood', 'fire-stove', 'wood-stove-lid', 'fire']) == [
        ('fire', 'fire-stove', ('fire',), 2),
        ('fire', 'fire-wood', ('fire',), 2),
        ('fire-stove', 'fire-wood', ('fire',), 3),
    ]


def test_near_pairs_and_tag_list_have_size_limits(monkeypatch):
    tags = [f'fire-{i}' for i in range(100)]
    assert len(type_usage.nearest(tags)) == type_usage.MAX_PAIRS
    monkeypatch.setattr(type_usage, 'LIST_BYTES', 20)
    brief = '\n'.join(type_usage.section([{'tags': tags}]))
    assert 'more tags in current-facts.jsonl' in brief
    assert 'No current tags.' in type_usage.section([])
