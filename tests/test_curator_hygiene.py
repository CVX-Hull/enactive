"""Thresholds and stable worklist digests for autonomous hygiene."""
from harness.curator.hygiene import ARTICLE_CUTOFF_BYTES, hygiene_trigger


def _fact(identity, **extra):
    return dict(dict(id=identity, record='fact', scope={'game': 'testgame'}, tags=[], links=[],
                     text='store equipment in cupboards', statement_kind='observation', lifecycle_state='active',
                     citations=[], stale_citations=[]), **extra)


def _article(slug, *, lead):
    return dict(id=f'{slug}@v1', slug=slug, record='article', scope={'game': 'testgame'},
                title=slug, lead=lead, tags=[], links=[], lifecycle_state='active', stale_citations=[],
                body=[dict(text='Storage', facts=['f1'])])


def test_must_clear_stale_citation_triggers_and_changes_digest():
    rows = [_fact('f1', stale_citations=['older']), _fact('f2', text='Boil water')]
    trigger = hygiene_trigger(rows)
    assert trigger['triggered'] and trigger['reasons'] == ['stale_citations']
    assert trigger['counts']['stale_citations'] == 1
    assert trigger == hygiene_trigger(rows[::-1])
    assert len(trigger['digest']) == 64
    assert hygiene_trigger([dict(rows[0], stale_citations=['different']), rows[1]])['digest'] != trigger['digest']
    assert not hygiene_trigger([dict(rows[0], stale_citations=[]), rows[1]])['triggered']


def test_three_duplicate_pairs_trigger():
    rows = [_fact(f'f{i}') for i in range(3)]
    below = hygiene_trigger(rows[:2])
    assert below['counts']['duplicate_pairs'] == 1 and not below['triggered']
    trigger = hygiene_trigger(rows)
    assert trigger['reasons'] == ['duplicate_pairs']
    assert trigger['counts']['duplicate_pairs'] == 3


def test_oversized_article_triggers_when_it_overlaps():
    rows = [_fact('f1'), _article('expanded', lead='x' * ARTICLE_CUTOFF_BYTES)]
    assert not hygiene_trigger(rows)['triggered']
    trigger = hygiene_trigger([*rows, _article('other', lead='short')])
    assert trigger['reasons'] == ['oversized_overlapping_articles']
    assert trigger['counts']['oversized_overlapping_articles'] == 1


def test_eight_total_advisories_trigger():
    tags = [f'tag{i}' for i in range(8)]
    rows = [_fact('f1', tags=tags), _fact('f2', tags=tags, text='Boil water', statement_kind='inference')]
    trigger = hygiene_trigger(rows)
    assert trigger['reasons'] == ['total_advisory'] and trigger['counts']['total_advisory'] == 8
    below = hygiene_trigger([dict(row, tags=tags[:7]) for row in rows])
    assert below['counts']['total_advisory'] == 7 and not below['triggered']
