# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

import sys
from pathlib import Path
from types import MethodType

# Add project root and scripts dir to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

from kindle_epub_fixer import EPUBFixer


def test_fix_book_language_treats_eee_as_invalid():
    fixer = EPUBFixer.__new__(EPUBFixer)
    fixer.files = {
        "META-INF/container.xml": (
            '<?xml version="1.0"?>'
            '<container><rootfiles><rootfile media-type="application/oebps-package+xml" '
            'full-path="content.opf"/></rootfiles></container>'
        ),
        "content.opf": (
            '<package xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<metadata><dc:language>EEE</dc:language></metadata>"
            "</package>"
        ),
    }
    fixer.fixed_problems = []
    fixer.aggressive_mode = False
    fixer.manually_triggered = False
    fixer._detect_language_from_metadata = MethodType(lambda self, _: None, fixer)

    fixer.fix_book_language(default_language="en", epub_path="/tmp/book.epub")

    assert "<dc:language>en</dc:language>" in fixer.files["content.opf"]
    assert any("Invalid language tag 'EEE'" in msg for msg in fixer.fixed_problems)
