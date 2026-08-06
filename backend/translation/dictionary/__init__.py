from .config import (
    DEFAULT_DICTIONARY_TRANSLATION_CONFIG,
    DictionaryTranslationConfig,
)
from .phrase_trie import (
    PhraseEntry,
    PhraseMatch,
    PhraseTrie,
    PhraseTrieError,
    PhraseTrieInputError,
)
from .tokenizer import (
    DictionaryToken,
    DictionaryTokenizer,
    DictionaryTokenizerError,
    DictionaryTokenizerInputError,
)
from .translator import (
    DictionaryTranslationItem,
    DictionaryTranslationResult,
    DictionaryTranslator,
    DictionaryTranslatorError,
    DictionaryTranslatorInputError,
)
from .vocabulary import (
    DictionaryVocabulary,
    DictionaryVocabularyError,
    DictionaryVocabularyInputError,
    DictionaryVocabularyLoadError,
    WordEntry,
)


__all__ = [
    # Main API
    "DictionaryTranslator",
    "DictionaryTranslationConfig",
    "DEFAULT_DICTIONARY_TRANSLATION_CONFIG",

    # Translation results
    "DictionaryTranslationResult",
    "DictionaryTranslationItem",

    # Tokenizer
    "DictionaryTokenizer",
    "DictionaryToken",

    # Word vocabulary
    "DictionaryVocabulary",
    "WordEntry",

    # Phrase Trie
    "PhraseTrie",
    "PhraseEntry",
    "PhraseMatch",

    # Translator errors
    "DictionaryTranslatorError",
    "DictionaryTranslatorInputError",

    # Tokenizer errors
    "DictionaryTokenizerError",
    "DictionaryTokenizerInputError",

    # Vocabulary errors
    "DictionaryVocabularyError",
    "DictionaryVocabularyInputError",
    "DictionaryVocabularyLoadError",

    # Phrase Trie errors
    "PhraseTrieError",
    "PhraseTrieInputError",
]