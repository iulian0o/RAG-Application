from app.evaluate_retrieval import covers_range


def test_one_chunk_covers_evidence():
    assert covers_range(10, 20, [(0, 30)])


def test_adjacent_chunks_cover_evidence():
    assert covers_range(10, 30, [(0, 20), (20, 40)])


def test_gap_does_not_count_as_complete_evidence():
    assert not covers_range(10, 30, [(0, 19), (20, 40)])


def test_partial_overlap_is_not_complete_evidence():
    assert not covers_range(10, 30, [(15, 40)])


def test_no_retrieved_chunks_means_no_coverage():
    assert not covers_range(10, 30, [])