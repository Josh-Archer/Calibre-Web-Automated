import os

from cps.tasks.mail import TaskEmail


def _task_email():
    return TaskEmail(
        subject="subject",
        filepath="Author/Book",
        attachment="Book.epub",
        settings={},
        recipient="reader@example.com",
        task_message="task",
        text="body",
        id=1,
    )


def test_resolve_attachment_path_returns_exact_match(tmp_path):
    book_dir = tmp_path / "Author" / "Book"
    book_dir.mkdir(parents=True)
    expected = book_dir / "Book.epub"
    expected.write_bytes(b"epub")

    resolved = _task_email()._resolve_attachment_path(
        str(tmp_path),
        "Author/Book",
        "Book.epub",
    )

    assert resolved == str(expected)


def test_resolve_attachment_path_falls_back_to_single_format_match(tmp_path):
    book_dir = tmp_path / "Author" / "Book"
    book_dir.mkdir(parents=True)
    actual = book_dir / "Barker, R J [Wounded Kingdom 03] King of Assassins - send to eReader.epub"
    actual.write_bytes(b"epub")

    resolved = _task_email()._resolve_attachment_path(
        str(tmp_path),
        "Author/Book",
        "Barker, R J [Wounded Kingdom 03] King of Assassins.epub",
    )

    assert resolved == str(actual)


def test_resolve_attachment_path_keeps_missing_path_when_multiple_candidates_exist(tmp_path):
    book_dir = tmp_path / "Author" / "Book"
    book_dir.mkdir(parents=True)
    (book_dir / "One.epub").write_bytes(b"1")
    (book_dir / "Two.epub").write_bytes(b"2")

    filename = "Missing.epub"
    resolved = _task_email()._resolve_attachment_path(
        str(tmp_path),
        "Author/Book",
        filename,
    )

    assert resolved == os.path.join(str(tmp_path), "Author/Book", filename)
