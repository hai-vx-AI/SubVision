from __future__ import annotations

import argparse
import json
import re
import unicodedata

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..tokenizer import DictionaryTokenizer


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[4]
)

DEFAULT_SOURCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "anhviet109K.txt"
)

DEFAULT_OUTPUT_PATH = (
    Path(__file__)
    .resolve()
    .parent
    / "data"
    / "en_vi_literal.json"
)

# ============================================================
# LITERAL CONTRACT
# ============================================================
#
# Runtime Literal chỉ được nhận:
#
# {
#     "words": {
#         "run": "chạy"
#     },
#     "phrases": {
#         "machine learning": "học máy"
#     }
# }
#
# MỖI KEY:
#     -> đúng một string
#
# Không:
#     -> list meanings
#     -> POS
#     -> IPA
#     -> examples
#     -> rich dictionary structure
#
# ============================================================


# ============================================================
# OPTIONAL MANUAL OVERRIDES
# ============================================================
#
# Literal translation không thể tự giải quyết hoàn hảo polysemy.
#
# Ví dụ:
#
#     set
#         noun -> bộ
#         verb -> đặt
#         math -> tập hợp
#
# Converter phải chọn một canonical literal meaning.
#
# Những trường hợp rất quan trọng có thể được khóa tại đây.
#
# Đây là BUILD-TIME POLICY.
# translation.py KHÔNG được có logic này.
# ============================================================


WORD_OVERRIDES: dict[str, str] = {
    "thing": "vật",
    "run": "chạy",
    "set": "đặt",
    "take": "lấy",
    "get": "được",
    "make": "làm",
    "same": "giống nhau",
    "value": "giá trị",
    "machine": "máy",
    "dog": "chó",
}


PHRASE_OVERRIDES: dict[str, str] = {
}




# ============================================================
# RAW MODELS
# ============================================================


@dataclass(slots=True)
class RawSection:
    title: str

    definitions: list[str] = field(
        default_factory=list
    )

    examples: list[str] = field(
        default_factory=list
    )


@dataclass(slots=True)
class RawEntry:
    headword: str

    pronunciation: str | None

    sections: list[RawSection] = field(
        default_factory=list
    )

    # Idiom/expression dạng:
    #
    # !to take off
    # +cất cánh
    #
    expressions: list[
        tuple[str, str]
    ] = field(
        default_factory=list
    )


# ============================================================
# WORD CANDIDATE
# ============================================================


@dataclass(frozen=True, slots=True)
class WordCandidate:
    headword: str

    translation: str

    section_title: str

    definition_index: int

    entry_definition_count: int

    has_pronunciation: bool


# ============================================================
# REGEX
# ============================================================


HEADER_PATTERN = re.compile(
    r"^@"
    r"(?P<headword>.*?)"
    r"(?:\s+/(?P<pronunciation>[^/]*)/)?"
    r"\s*$"
)


# Dùng để phát hiện một số definition thực chất chứa
# English phrase / technical phrase chứ không phải concise gloss.
ENGLISH_NOISE_PATTERN = re.compile(
    r"\b("
    r"to|of|the|into|from|with|for|"
    r"equation|point|game|variable|"
    r"insurance|series"
    r")\b",
    flags=re.IGNORECASE,
)


# Gỡ annotation đầu definition:
#
#     (thương nghiệp) giá trị
#     (kỹ thuật) máy
#
LEADING_NOTE_PATTERN = re.compile(
    r"^(?:"
    r"\([^)]*\)"
    r"\s*"
    r")+"
)


# ============================================================
# BASIC CLEANING
# ============================================================


def clean_text(
    value: str,
) -> str:
    value = unicodedata.normalize(
        "NFKC",
        value,
    )

    value = " ".join(
        value.strip().split()
    )

    return value


def clean_definition(
    value: str,
) -> str:
    value = clean_text(value)

    value = LEADING_NOTE_PATTERN.sub(
        "",
        value,
    )

    return value.strip(
        " \t,;:-"
    )


# ============================================================
# SOURCE NORMALIZATION
# ============================================================
#
# QUY TẮC:
#     DictionaryTokenizer là source of truth cho mọi key lookup.
#
# create_json.py KHÔNG tự định nghĩa:
#     - case normalization;
#     - apostrophe normalization;
#     - hyphen normalization;
#     - lemmatization;
#     - tokenization rule.
#
# Build-time và runtime phải dùng cùng một tokenizer contract.
# ============================================================


def normalize_word_key(
    value: str,
    tokenizer: DictionaryTokenizer,
) -> str | None:
    """
    Chuẩn hóa một word key bằng DictionaryTokenizer.

    Trả None nếu source không phải đúng một word token.
    """

    source = clean_text(value)

    if not source:
        return None

    tokens = tokenizer.tokenize(source)

    if len(tokens) != 1:
        return None

    token = tokens[0]

    if not token.is_word:
        return None

    # Không chấp nhận source có ký tự ngoài token.
    if token.start != 0 or token.end != len(source):
        return None

    return token.normalized


def normalize_phrase_key(
    value: str,
    tokenizer: DictionaryTokenizer,
) -> tuple[str, tuple[str, ...]]:
    """
    Chuẩn hóa phrase bằng đúng DictionaryTokenizer dùng ở runtime.

    Output:
        (normalized_phrase_key, normalized_tokens)
    """

    source = clean_text(value)

    if not source:
        return "", ()

    normalized_tokens = tokenizer.normalize_phrase(
        source
    )

    if not normalized_tokens:
        return "", ()

    return (
        " ".join(normalized_tokens),
        normalized_tokens,
    )


# ============================================================
# RAW PARSER
# ============================================================


def parse_raw_dictionary(
    path: Path,
) -> list[RawEntry]:
    """
    Parse format dạng:

        @run /rʌn/
        * danh từ
        - sự chạy
        = at a run+ đang chạy
        !in the long run
        +về lâu dài

    Duplicate @headword được giữ nguyên.
    """

    entries: list[RawEntry] = []

    current_entry: RawEntry | None = None
    current_section: RawSection | None = None

    pending_expression: str | None = None

    with path.open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as file:

        for raw_line in file:

            line = raw_line.strip()

            if not line:
                continue

            # ------------------------------------------------
            # @ HEADWORD
            # ------------------------------------------------

            if line.startswith("@"):

                match = HEADER_PATTERN.match(
                    line
                )

                if match is None:
                    continue

                headword = clean_text(
                    match.group("headword")
                )

                if not headword:
                    continue

                pronunciation = (
                    match.group(
                        "pronunciation"
                    )
                )

                if pronunciation is not None:
                    pronunciation = clean_text(
                        pronunciation
                    )

                current_entry = RawEntry(
                    headword=headword,
                    pronunciation=(
                        pronunciation
                        or None
                    ),
                )

                entries.append(
                    current_entry
                )

                current_section = None
                pending_expression = None

                continue

            if current_entry is None:
                continue

            # ------------------------------------------------
            # * SECTION
            # ------------------------------------------------

            if line.startswith("*"):

                title = clean_text(
                    line[1:]
                )

                current_section = RawSection(
                    title=(
                        title
                        or "<NO SECTION>"
                    )
                )

                current_entry.sections.append(
                    current_section
                )

                pending_expression = None

                continue

            # ------------------------------------------------
            # - DEFINITION
            # ------------------------------------------------

            if line.startswith("-"):

                if current_section is None:
                    current_section = RawSection(
                        title="<NO SECTION>"
                    )

                    current_entry.sections.append(
                        current_section
                    )

                definition = clean_definition(
                    line[1:]
                )

                if definition:
                    current_section.definitions.append(
                        definition
                    )

                pending_expression = None

                continue

            # ------------------------------------------------
            # = EXAMPLE
            # ------------------------------------------------

            if line.startswith("="):

                if current_section is None:
                    current_section = RawSection(
                        title="<NO SECTION>"
                    )

                    current_entry.sections.append(
                        current_section
                    )

                example = clean_text(
                    line[1:]
                )

                if example:
                    current_section.examples.append(
                        example
                    )

                pending_expression = None

                continue

            # ------------------------------------------------
            # ! EXPRESSION
            #
            # Có thể:
            #
            # !in the long run
            # +về lâu dài
            #
            # hoặc:
            #
            # !in the long run+về lâu dài
            # ------------------------------------------------

            if line.startswith("!"):

                expression_line = clean_text(
                    line[1:]
                )

                if "+" in expression_line:

                    source, translation = (
                        expression_line.split(
                            "+",
                            maxsplit=1,
                        )
                    )

                    source = clean_text(source)
                    translation = clean_text(
                        translation
                    )

                    if source and translation:
                        current_entry.expressions.append(
                            (
                                source,
                                translation,
                            )
                        )

                    pending_expression = None

                else:
                    pending_expression = (
                        expression_line
                        or None
                    )

                continue

            # ------------------------------------------------
            # + TRANSLATION OF EXPRESSION
            # ------------------------------------------------

            if (
                line.startswith("+")
                and pending_expression
            ):

                translation = clean_text(
                    line[1:]
                )

                if translation:
                    current_entry.expressions.append(
                        (
                            pending_expression,
                            translation,
                        )
                    )

                pending_expression = None

                continue

    return entries


# ============================================================
# DEFINITION COUNT
# ============================================================


def count_definitions(
    entry: RawEntry,
) -> int:
    return sum(
        len(section.definitions)
        for section in entry.sections
    )


# ============================================================
# WORD GLOSS SPLITTING
# ============================================================


GENERIC_GLOSS_PENALTY = {
    "cái",
    "đồ",
    "thứ",
    "điều",
    "sự",
    "việc",
    "món",
    "để",
}


def split_word_glosses(
    definition: str,
) -> list[str]:
    """
    Một raw definition có thể là:

        "làm, chế tạo"
        "máy; cơ cấu; thiết bị"
        "được; tính"

    Literal cần một canonical translation.

    Split chỉ diễn ra trong create_json.py.
    Runtime tuyệt đối không được làm việc này.
    """

    definition = clean_definition(
        definition
    )

    if not definition:
        return []

    # // thường phân tách sense khác hẳn.
    definition = definition.replace(
        "//",
        ";",
    )

    parts = re.split(
        r"\s*[,;]\s*",
        definition,
    )

    result: list[str] = []

    for part in parts:

        part = clean_definition(part)

        if not part:
            continue

        if part not in result:
            result.append(part)

    return result


# ============================================================
# CANDIDATE VALIDATION
# ============================================================


def is_usable_word_gloss(
    value: str,
) -> bool:

    if not value:
        return False

    # Không dùng example syntax.
    if "+" in value:
        return False

    # Literal word translation không nên là một đoạn dài.
    if len(value) > 45:
        return False

    words = value.split()

    if len(words) > 7:
        return False

    # Một số technical entry chứa English source phrase
    # chung với Vietnamese translation:
    #
    # "s. of equations hệ phương trình"
    #
    if ENGLISH_NOISE_PATTERN.search(
        value
    ):
        return False

    # Abbreviation kiểu:
    #
    # "s. of ..."
    # "v. of ..."
    #
    if re.search(
        r"\b[a-zA-Z]\.",
        value,
    ):
        return False

    return True


# ============================================================
# WORD SCORING
# ============================================================


def score_word_candidate(
    candidate: WordCandidate,
) -> tuple[int, int, int]:
    """
    Điểm càng thấp càng tốt.

    Đây là BUILD-TIME heuristic.

    translation.py KHÔNG biết scoring tồn tại.
    """

    value = candidate.translation

    score = 0

    word_count = len(
        value.split()
    )

    # --------------------------------------------------------
    # Concise meaning được ưu tiên.
    # --------------------------------------------------------

    score += word_count * 10

    score += min(
        len(value),
        30,
    )

    # --------------------------------------------------------
    # Generic noun/classifier bị hạ ưu tiên.
    #
    # Ví dụ thing:
    #
    # cái, đồ, vật, thứ...
    #
    # để "vật" có cơ hội thắng "cái".
    # --------------------------------------------------------

    if value.casefold() in (
        GENERIC_GLOSS_PENALTY
    ):
        score += 40

    # --------------------------------------------------------
    # Nominalized Vietnamese thường kém phù hợp
    # cho literal base word.
    # --------------------------------------------------------

    if value.startswith(
        (
            "sự ",
            "việc ",
        )
    ):
        score += 20

    # --------------------------------------------------------
    # Entry chỉ có đúng một definition thường là
    # concise dictionary mapping.
    #
    # Ví dụ raw:
    #
    # @run
    # - chạy
    #
    # @get
    # - được; tính
    #
    # @make
    # - làm, sản xuất; ...
    #
    # --------------------------------------------------------

    if (
        candidate.entry_definition_count
        == 1
    ):
        score -= 50

    # --------------------------------------------------------
    # Definition đầu section được ưu tiên nhẹ.
    # --------------------------------------------------------

    score += (
        candidate.definition_index
        * 3
    )

    # Tie-break deterministic.
    return (
        score,
        len(value),
        candidate.definition_index,
    )


# ============================================================
# COLLECT WORD CANDIDATES
# ============================================================


def collect_word_candidates(
    entries: list[RawEntry],
    tokenizer: DictionaryTokenizer,
) -> dict[
    str,
    list[WordCandidate],
]:

    candidates: dict[
        str,
        list[WordCandidate],
    ] = defaultdict(list)

    for entry in entries:

        key = normalize_word_key(
            entry.headword,
            tokenizer,
        )

        if key is None:
            continue

        definition_count = (
            count_definitions(entry)
        )

        for section in entry.sections:

            for definition_index, definition in enumerate(
                section.definitions
            ):

                for gloss in split_word_glosses(
                    definition
                ):

                    if not is_usable_word_gloss(
                        gloss
                    ):
                        continue

                    candidates[key].append(
                        WordCandidate(
                            headword=key,
                            translation=gloss,
                            section_title=(
                                section.title
                            ),
                            definition_index=(
                                definition_index
                            ),
                            entry_definition_count=(
                                definition_count
                            ),
                            has_pronunciation=(
                                entry.pronunciation
                                is not None
                            ),
                        )
                    )

    return candidates


# ============================================================
# BUILD WORD DICTIONARY
# ============================================================


def build_words(
    entries: list[RawEntry],
    tokenizer: DictionaryTokenizer,
    word_overrides: dict[str, str],
) -> dict[str, str]:

    candidates = collect_word_candidates(
        entries,
        tokenizer,
    )

    result: dict[str, str] = {}

    for word, word_candidates in (
        candidates.items()
    ):

        override = word_overrides.get(
            word
        )

        if override is not None:

            result[word] = clean_text(
                override
            )

            continue

        best = min(
            word_candidates,
            key=score_word_candidate,
        )

        result[word] = (
            best.translation
        )

    return result


# ============================================================
# PHRASE HELPERS
# ============================================================


def is_valid_phrase(
    normalized_tokens: tuple[str, ...],
) -> bool:
    """
    Phrase validity dựa trên chính token sequence do
    DictionaryTokenizer tạo ra.
    """

    count = len(normalized_tokens)

    if count < 2:
        return False

    if count > 7:
        return False

    return True


def clean_phrase_translation(
    value: str,
) -> str:

    value = clean_text(value)

    # Literal resource luôn giữ đúng một translation string.
    return value.strip()


# ============================================================
# NORMALIZED OVERRIDES
# ============================================================


def build_normalized_overrides(
    tokenizer: DictionaryTokenizer,
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Override keys cũng phải tuân theo cùng normalization contract.
    """

    word_overrides: dict[str, str] = {}

    for source, translation in WORD_OVERRIDES.items():
        key = normalize_word_key(
            source,
            tokenizer,
        )

        if key is None:
            raise ValueError(
                f"Invalid WORD_OVERRIDES key: {source!r}."
            )

        word_overrides[key] = clean_text(translation)

    phrase_overrides: dict[str, str] = {}

    for source, translation in PHRASE_OVERRIDES.items():
        key, tokens = normalize_phrase_key(
            source,
            tokenizer,
        )

        if not is_valid_phrase(tokens):
            raise ValueError(
                f"Invalid PHRASE_OVERRIDES key: {source!r}."
            )

        phrase_overrides[key] = clean_text(translation)

    return word_overrides, phrase_overrides


# ============================================================
# PHRASE CANDIDATES
# ============================================================


@dataclass(frozen=True, slots=True)
class PhraseCandidate:
    source: str
    translation: str

    # expression tốt hơn example
    priority: int


def collect_phrase_candidates(
    entries: list[RawEntry],
    tokenizer: DictionaryTokenizer,
) -> dict[
    str,
    list[PhraseCandidate],
]:

    candidates: dict[
        str,
        list[PhraseCandidate],
    ] = defaultdict(list)

    for entry in entries:

        # ----------------------------------------------------
        # 1. Multi-word dictionary headword
        # ----------------------------------------------------

        (
            headword,
            headword_tokens,
        ) = normalize_phrase_key(
            entry.headword,
            tokenizer,
        )

        if is_valid_phrase(headword_tokens):

            definitions: list[str] = []

            for section in entry.sections:
                definitions.extend(
                    section.definitions
                )

            if definitions:

                translation = (
                    clean_phrase_translation(
                        definitions[0]
                    )
                )

                if translation:
                    candidates[
                        headword
                    ].append(
                        PhraseCandidate(
                            source=headword,
                            translation=translation,
                            priority=0,
                        )
                    )

        # ----------------------------------------------------
        # 2. Explicit expressions:
        #
        # !in the long run
        # +về lâu dài
        # ----------------------------------------------------

        for (
            source,
            translation,
        ) in entry.expressions:

            (
                source,
                source_tokens,
            ) = normalize_phrase_key(
                source,
                tokenizer,
            )

            translation = (
                clean_phrase_translation(
                    translation
                )
            )

            if (
                source
                and translation
                and is_valid_phrase(source_tokens)
            ):
                candidates[
                    source
                ].append(
                    PhraseCandidate(
                        source=source,
                        translation=translation,
                        priority=0,
                    )
                )

        # ----------------------------------------------------
        # 3. Examples:
        #
        # = to run a machine+ cho máy chạy
        # ----------------------------------------------------

        for section in entry.sections:

            for example in section.examples:

                if "+" not in example:
                    continue

                source, translation = (
                    example.split(
                        "+",
                        maxsplit=1,
                    )
                )

                (
                    source,
                    source_tokens,
                ) = normalize_phrase_key(
                    source,
                    tokenizer,
                )

                translation = (
                    clean_phrase_translation(
                        translation
                    )
                )

                if (
                    not source
                    or not translation
                    or not is_valid_phrase(
                        source_tokens
                    )
                ):
                    continue

                candidates[
                    source
                ].append(
                    PhraseCandidate(
                        source=source,
                        translation=translation,
                        priority=10,
                    )
                )

    return candidates


# ============================================================
# PHRASE SCORING
# ============================================================


def score_phrase_candidate(
    candidate: PhraseCandidate,
) -> tuple[int, int]:

    return (
        candidate.priority,
        len(candidate.translation),
    )


# ============================================================
# BUILD PHRASES
# ============================================================


def build_phrases(
    entries: list[RawEntry],
    tokenizer: DictionaryTokenizer,
    phrase_overrides: dict[str, str],
) -> dict[str, str]:

    candidates = collect_phrase_candidates(
        entries,
        tokenizer,
    )

    result: dict[str, str] = {}

    for phrase, phrase_candidates in (
        candidates.items()
    ):

        override = phrase_overrides.get(
            phrase
        )

        if override is not None:

            result[phrase] = clean_text(
                override
            )

            continue

        best = min(
            phrase_candidates,
            key=score_phrase_candidate,
        )

        result[phrase] = (
            best.translation
        )

    return result


# ============================================================
# VALIDATE FINAL RESOURCE
# ============================================================


def validate_literal_dictionary(
    data: dict,
) -> None:
    """
    Fail fast.

    create_json.py không được tạo resource mà runtime
    phải đoán cách sửa.
    """

    if not isinstance(data, dict):
        raise TypeError(
            "Literal dictionary root must be a dict."
        )

    if set(data) != {
        "words",
        "phrases",
    }:
        raise ValueError(
            "Literal dictionary root must contain "
            "exactly: 'words' and 'phrases'."
        )

    for group_name in (
        "words",
        "phrases",
    ):

        group = data[group_name]

        if not isinstance(group, dict):
            raise TypeError(
                f"{group_name} must be a dict."
            )

        for key, value in group.items():

            if not isinstance(key, str):
                raise TypeError(
                    f"{group_name} key must be str."
                )

            if not key.strip():
                raise ValueError(
                    f"{group_name} contains empty key."
                )

            # =================================================
            # QUAN TRỌNG NHẤT
            #
            # Không chấp nhận:
            #
            # "run": ["chạy", "vận hành"]
            #
            # Literal contract:
            #
            # "run": "chạy"
            # =================================================

            if not isinstance(value, str):
                raise TypeError(
                    f"{group_name}[{key!r}] "
                    "must contain exactly one string, "
                    f"received "
                    f"{type(value).__name__}."
                )

            if not value.strip():
                raise ValueError(
                    f"{group_name}[{key!r}] "
                    "contains an empty translation."
                )


# ============================================================
# WRITE JSON
# ============================================================


def write_literal_dictionary(
    output_path: Path,
    *,
    words: dict[str, str],
    phrases: dict[str, str],
) -> None:

    # Deterministic output.
    words = dict(
        sorted(
            words.items()
        )
    )

    phrases = dict(
        sorted(
            phrases.items()
        )
    )

    data = {
        "words": words,
        "phrases": phrases,
    }

    validate_literal_dictionary(
        data
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )

        file.write("\n")


# ============================================================
# BUILD
# ============================================================


def build(
    source_path: Path,
    output_path: Path,
) -> None:

    if not source_path.is_file():
        raise FileNotFoundError(
            f"Raw dictionary not found: "
            f"{source_path}"
        )

    print(
        "Reading:",
        source_path,
    )

    entries = parse_raw_dictionary(
        source_path
    )

    if not entries:
        raise RuntimeError(
            "No dictionary entries were parsed."
        )

    print(
        "Raw entries:",
        len(entries),
    )

    tokenizer = DictionaryTokenizer()

    (
        word_overrides,
        phrase_overrides,
    ) = build_normalized_overrides(
        tokenizer
    )

    words = build_words(
        entries,
        tokenizer,
        word_overrides,
    )

    phrases = build_phrases(
        entries,
        tokenizer,
        phrase_overrides,
    )

    print(
        "Literal words:",
        len(words),
    )

    print(
        "Literal phrases:",
        len(phrases),
    )

    write_literal_dictionary(
        output_path,
        words=words,
        phrases=phrases,
    )

    print(
        "Written:",
        output_path,
    )

    print()
    print(
        "Literal dictionary build: PASS"
    )


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Build isolated Literal English-Vietnamese "
            "dictionary JSON from anhviet109K.txt."
        )
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_PATH,
        help=(
            "Path to raw anhviet109K.txt"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=(
            "Path to generated "
            "en_vi_literal.json"
        ),
    )

    return parser.parse_args()


def main() -> None:

    args = parse_args()

    build(
        source_path=(
            args.source.expanduser().resolve()
        ),
        output_path=(
            args.output.expanduser().resolve()
        ),
    )


if __name__ == "__main__":
    main()