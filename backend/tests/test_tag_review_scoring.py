"""The review counts locations once and exposes close-neighbor dedupe loss."""
from scripts.score_tag_review import score
from scripts.probe_tag_duplicates import deduplicate


def point(name, tag, x, y, confidence=1.0):
    return dict(id=name, tag=tag, cx=x, cy=y, score=confidence)


def test_two_reads_of_one_tag_cannot_hide_a_miss():
    truth = [point('a', 'WC', 10, 10), point('b', 'WC', 10, 50)]
    observed = [point('x', 'WC', 10, 10), point('y', 'WC', 11, 11)]
    result = score(truth, observed, 8)
    assert (result['correct'], result['false_or_duplicate'], result['missed']) == (1, 1, 1)
    assert result['missed_ids'] == ['b']


def test_same_location_wrong_class_does_not_match():
    result = score([point('a', 'WC', 10, 10)], [point('b', 'LAV', 10, 10)], 8)
    assert (result['correct'], result['false_or_duplicate'], result['missed']) == (0, 1, 1)


def test_empty_inventory_is_not_perfect_recall():
    result = score([], [], 8)
    assert result['precision'] is None and result['recall'] is None


def test_native_urinal_spacing_exposes_unsafe_general_dedupe():
    # Manually reviewed printed U centers on trace-02; these are distinct tags.
    truth = [point(str(i), 'urinal', 183, y) for i, y in enumerate((227, 257, 282, 306))]
    kept, removed = deduplicate(truth)
    assert len(kept) == 3
    assert len(removed) == 1
    # This pins rejection of the candidate as a general rule, not desired behavior.
