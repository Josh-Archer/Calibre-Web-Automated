import sys
from pathlib import Path
from types import SimpleNamespace


project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from cps.metadata_helper import _metadata_candidate_matches


def _book(title, *authors):
    return SimpleNamespace(
        title=title,
        authors=[SimpleNamespace(name=author) for author in authors],
    )


def _metadata(title, *authors):
    return SimpleNamespace(title=title, authors=list(authors))


def test_metadata_candidate_matches_close_title_variant():
    book = _book("Mr. Mercedes", "Stephen King")
    candidate = _metadata("Mr. Mercedes (Bill Hodges Trilogy)", "Stephen King")

    assert _metadata_candidate_matches(book, candidate) is True


def test_metadata_candidate_rejects_series_neighbor_match():
    book = _book("Skyward", "Brandon Sanderson")
    candidate = _metadata("Cytonic (The Skyward Series)", "Brandon Sanderson")

    assert _metadata_candidate_matches(book, candidate) is False


def test_metadata_candidate_rejects_author_mismatch():
    book = _book("Snapshot", "Brandon Sanderson")
    candidate = _metadata("Snapshot: Signed", "Somebody Else")

    assert _metadata_candidate_matches(book, candidate) is False
