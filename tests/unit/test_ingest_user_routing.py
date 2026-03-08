import sys
import types
from pathlib import Path

if "fcntl" not in sys.modules:
    sys.modules["fcntl"] = types.SimpleNamespace(
        flock=lambda *args, **kwargs: None,
        LOCK_EX=1,
        LOCK_NB=2,
        LOCK_UN=8,
    )
if "kindle_epub_fixer" not in sys.modules:
    sys.modules["kindle_epub_fixer"] = types.SimpleNamespace(EPUBFixer=object)
if "audiobook" not in sys.modules:
    sys.modules["audiobook"] = types.SimpleNamespace()


project_root = Path(__file__).resolve().parents[2]
scripts_path = project_root / "scripts"
if str(scripts_path) not in sys.path:
    sys.path.insert(0, str(scripts_path))

from ingest_processor import NewBookProcessor  # noqa: E402


def _make_processor(route_map="{}"):
    processor = NewBookProcessor.__new__(NewBookProcessor)
    processor.ingest_folder = "/cwa-book-ingest"
    processor.cwa_settings = {
        "user_routed_ingest_user_map": route_map,
        "user_routed_ingest_shelf_name": "Auto Imports",
    }
    return processor


def test_resolve_target_route_key_from_path_uses_first_subfolder():
    processor = _make_processor()

    route_key = processor._resolve_target_route_key_from_path("/cwa-book-ingest/erin/book.epub")

    assert route_key == "erin"


def test_parse_user_routed_ingest_user_map_supports_single_and_multi_user_aliases():
    processor = _make_processor('{"mine":"josh","shared":["erin","josh","erin"]}')

    parsed = processor._parse_user_routed_ingest_user_map()

    assert parsed == {
        "mine": ["josh"],
        "shared": ["erin", "josh"],
    }


def test_resolve_target_usernames_prefers_alias_map_over_raw_folder_name():
    processor = _make_processor('{"mine":"josh","shared":["erin","josh"]}')
    processor.user_routed_ingest_user_map = processor._parse_user_routed_ingest_user_map()

    assert processor._resolve_target_usernames("mine") == ["josh"]
    assert processor._resolve_target_usernames("shared") == ["erin", "josh"]
    assert processor._resolve_target_usernames("erin") == ["erin"]


def test_build_target_visibility_tags_uses_normalized_usernames():
    processor = _make_processor()

    tags = processor._build_target_visibility_tags(["Josh@ArcherFamily.io", "erin@archerfamily.io", "josh@archerfamily.io"])

    assert tags == [
        "cwa-user:josh@archerfamily.io",
        "cwa-user:erin@archerfamily.io",
    ]


def test_merge_tags_preserves_existing_and_appends_visibility_tags_without_duplicates():
    processor = _make_processor()

    merged = processor._merge_tags("fantasy, cwa-user:josh@archerfamily.io", [
        "cwa-user:erin@archerfamily.io",
        "cwa-user:josh@archerfamily.io",
    ])

    assert merged == "fantasy,cwa-user:josh@archerfamily.io,cwa-user:erin@archerfamily.io"
