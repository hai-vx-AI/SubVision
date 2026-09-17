from __future__ import annotations

import json

from .translation import (
    LiteralTranslationInputError,
    LiteralTranslator,
)


def _production_data(translator: LiteralTranslator) -> tuple[dict[str, str], dict[str, str]]:
    with translator.dictionary_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data["words"], data["phrases"]


def _simple_words(words: dict[str, str], count: int = 2) -> list[tuple[str, str]]:
    result = [
        (word, translation)
        for word, translation in words.items()
        if word.isascii() and word.isalpha() and len(word) > 1
    ]
    assert len(result) >= count, "Production dictionary has too few simple words."
    return result[:count]


def _simple_phrase(phrases: dict[str, str]) -> tuple[str, str]:
    for phrase, translation in phrases.items():
        parts = phrase.split()
        if len(parts) >= 2 and all(part.isascii() and part.isalpha() for part in parts):
            return phrase, translation
    raise AssertionError("Production dictionary has no simple multi-word phrase.")


def _nested_phrases(phrases: dict[str, str]) -> tuple[str, str]:
    simple = {
        phrase: translation
        for phrase, translation in phrases.items()
        if len(phrase.split()) >= 2
        and all(part.isascii() and part.isalpha() for part in phrase.split())
    }

    for long_phrase in sorted(simple, key=lambda value: len(value.split()), reverse=True):
        parts = long_phrase.split()
        for end in range(len(parts) - 1, 1, -1):
            short_phrase = " ".join(parts[:end])
            if short_phrase in simple:
                return short_phrase, long_phrase

    raise AssertionError(
        "Production dictionary has no nested phrases; cannot prove longest-match behavior."
    )


def _must_reject(translator: LiteralTranslator, value: object) -> None:
    try:
        translator.translate(value)  # type: ignore[arg-type]
    except LiteralTranslationInputError:
        return
    raise AssertionError(f"Expected LiteralTranslationInputError for {type(value).__name__}.")


def run_tests() -> None:
    # Real production resource. No fixture, no temporary dictionary.
    translator = LiteralTranslator()
    words, phrases = _production_data(translator)

    assert translator.word_count > 0
    assert translator.phrase_count > 0

    # Public contract: exactly one str.
    for invalid in (["hello"], ("hello",), {"text": "hello"}, 123, None):
        _must_reject(translator, invalid)
    _must_reject(translator, "bad\x00text")

    empty = translator.translate("")
    assert empty.source_text == ""
    assert empty.translated_text == ""

    # Word normalization, repeated words, punctuation and spacing preservation.
    (word1, vi1), (word2, vi2) = _simple_words(words)
    unknown = "Qzxvblorpnotindictionary"
    source = f" \t{word1.upper()},  \n{unknown};\t{word2}! {word1} "
    expected = f" \t{vi1},  \n{unknown};\t{vi2}! {vi1} "
    assert translator.translate_text(source) == expected

    # Number/email/date/time stay untouched.
    source = f"{word1}, user@example.com 2026-08-14 10:30"
    expected = f"{vi1}, user@example.com 2026-08-14 10:30"
    assert translator.translate_text(source) == expected

    # Phrase must beat word fallback and be consumed once.
    phrase, phrase_vi = _simple_phrase(phrases)
    assert translator.translate_text(phrase) == phrase_vi

    # Longest phrase must win.
    short_phrase, long_phrase = _nested_phrases(phrases)
    assert translator.translate_text(long_phrase) == phrases[long_phrase]

    # Punctuation blocks the longer phrase, but a valid shorter prefix must still match.
    short_parts = short_phrase.split()
    long_parts = long_phrase.split()
    remainder = " ".join(long_parts[len(short_parts):])
    punctuated = f"{short_phrase}, {remainder}"
    punctuated_result = translator.translate_text(punctuated)
    assert punctuated_result.startswith(phrases[short_phrase] + ",")
    assert "," in punctuated_result

    # Same input + same resource => deterministic output.
    hard_case = f"{phrase}! {word1} {unknown} user@example.com 42"
    first = translator.translate_text(hard_case)
    for _ in range(5):
        assert translator.translate_text(hard_case) == first

    print("LiteralTranslator production test: PASS")
    print(f"words={translator.word_count:,} phrases={translator.phrase_count:,}")


if __name__ == "__main__":
    run_tests()
