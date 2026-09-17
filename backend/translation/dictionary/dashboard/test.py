"""
Dashboard production test.

Dùng trực tiếp:
- raw dictionary thật;
- en_vi_dashboard.json thật do create_json.py tạo;
- DashboardExtractor thật.

Chạy:
    python -m backend.translation.dictionary.dashboard.test
"""

from __future__ import annotations

import json

from ..tokenizer import DictionaryTokenizer
from . import DashboardExtractor
from .create_json import (
    DEFAULT_OUTPUT_PATH,
    DEFAULT_SOURCE_PATH,
    build_dashboard_dictionary,
    parse_raw_dictionary,
)
from .phrase_trie import DashboardPhraseTrie


TEST_TEXT = (
    "Machine learning is a useful method for computer systems. "
    "The machine learns from data and information."
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_dictionary() -> dict:
    with DEFAULT_OUTPUT_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def find_nested_phrase(phrases: dict) -> tuple[str, str]:
    for long_key in sorted(
        phrases,
        key=lambda key: len(key.split()),
        reverse=True,
    ):
        parts = long_key.split()

        for size in range(len(parts) - 1, 1, -1):
            short_key = " ".join(parts[:size])

            if short_key in phrases:
                return short_key, long_key

    raise AssertionError("No nested production phrase found.")


def print_result(text: str, entries) -> None:
    print()
    print("=" * 70)
    print("DASHBOARD BLACK-BOX EXAMPLE")
    print("=" * 70)
    print("INPUT:")
    print(text)
    print()
    print(f"OUTPUT: {len(entries)} entries")
    print("-" * 70)

    for index, entry in enumerate(entries, 1):
        print(f"[{index}] {entry.term}")
        print(f"    type     : {entry.entry_type}")
        print(
            "    IPA      : "
            + (" | ".join(entry.ipas) if entry.ipas else "<none>")
        )
        print("    meanings :")

        for meaning in entry.meanings:
            print(f"      - {meaning}")

        print()

    print("=" * 70)


def run_tests() -> None:
    # ---------------------------------------------------------
    # 1. REAL BLACK-BOX USAGE
    # ---------------------------------------------------------
    dashboard = DashboardExtractor()

    result = dashboard.extract([TEST_TEXT])

    check(result, "Natural test sentence returned no Dashboard entries.")
    print_result(TEST_TEXT, result)

    # Public output invariants.
    terms = [entry.term.casefold() for entry in result]

    check(
        terms == sorted(terms),
        "Output is not sorted A -> Z.",
    )
    check(
        len(terms) == len(set((entry.entry_type, entry.term.casefold())
                              for entry in result)),
        "Output contains duplicate entries.",
    )
    check(
        all(entry.meanings for entry in result),
        "Every returned entry must contain at least one meaning.",
    )
    check(
        dashboard.extract([TEST_TEXT]) == result,
        "Same input must produce exactly the same output.",
    )

    # ---------------------------------------------------------
    # 2. CREATE_JSON -> PRODUCTION JSON
    # ---------------------------------------------------------
    production = load_dictionary()

    tokenizer = DictionaryTokenizer()
    raw_entries = parse_raw_dictionary(DEFAULT_SOURCE_PATH)

    check(raw_entries, "Raw parser returned no dictionary entries.")

    rebuilt = build_dashboard_dictionary(
        raw_entries,
        tokenizer,
    )

    check(
        rebuilt == production,
        "Production JSON differs from current create_json output.",
    )

    # ---------------------------------------------------------
    # 3. PHRASE TRIE LONGEST-MATCH
    # ---------------------------------------------------------
    phrases = production["phrases"]
    short_key, long_key = find_nested_phrase(phrases)

    phrase_text = phrases[long_key]["term"]
    tokens = tokenizer.tokenize(phrase_text)

    phrase_result = dashboard.extract([phrase_text])
    returned_phrases = {
        entry.term
        for entry in phrase_result
        if entry.entry_type == "phrase"
    }

    check(
        phrases[long_key]["term"] in returned_phrases,
        "Dashboard did not return the longest phrase.",
    )
    check(
        phrases[short_key]["term"] not in returned_phrases,
        "Shorter nested phrase leaked from the consumed span.",
    )

    # Phrase must not cross OCR-correction text boundaries.
    parts = long_key.split()
    split_result = dashboard.extract(
        [parts[0], " ".join(parts[1:])]
    )

    check(
        phrases[long_key]["term"]
        not in {entry.term for entry in split_result},
        "Phrase matched across two independent input texts.",
    )

    print()
    print("Dashboard FULL production test: PASS")
    print(f"raw_entries={len(raw_entries)}")
    print(f"words={len(production['words'])}")
    print(f"phrases={len(phrases)}")
    print(f"longest_match_test={long_key!r}")


if __name__ == "__main__":
    run_tests()
