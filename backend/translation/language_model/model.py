from __future__ import annotations

import re
from dataclasses import dataclass

import torch
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
)

from .config import (
    DEFAULT_LANGUAGE_TRANSLATION_CONFIG,
    LanguageTranslationConfig,
)


class LanguageTranslationError(RuntimeError):
    """
    Lỗi cơ sở của language translation.
    """


class LanguageModelLoadError(LanguageTranslationError):
    """
    Không thể tải tokenizer hoặc model.
    """


class LanguageTranslationInputError(ValueError):
    """
    Text đầu vào không hợp lệ.
    """


class LanguageTranslationInferenceError(
    LanguageTranslationError
):
    """
    Lỗi xảy ra trong quá trình model dịch.
    """


@dataclass(frozen=True, slots=True)
class LanguageTranslationResult:
    """
    Kết quả dịch một đoạn text.

    Attributes
    ----------
    source_text:
        Text gốc được truyền vào.

    translated_text:
        Bản dịch tiếng Việt từ model.

    processed_text:
        Text sau khi chuẩn hóa khoảng trắng.

    device:
        Thiết bị thực tế đã chạy inference.
    """

    source_text: str
    translated_text: str
    processed_text: str
    device: str


class LanguageTranslator:
    """
    Model dịch máy chuyên dụng Anh → Việt.

    API chính:

        translator = LanguageTranslator()

        result = translator.translate(
            "She decided to give up."
        )

        print(result.translated_text)

    Model được tải một lần khi khởi tạo object và được tái sử dụng
    cho các lần dịch sau.
    """

    WHITESPACE_PATTERN = re.compile(r"\s+")

    def __init__(
        self,
        config: LanguageTranslationConfig | None = None,
    ) -> None:
        self.config = (
            config
            or DEFAULT_LANGUAGE_TRANSLATION_CONFIG
        )

        self._device = self._resolve_device()

        self._tokenizer = None
        self._model = None

        self._load_model()

    # ==========================================================
    # Public properties
    # ==========================================================

    @property
    def device(self) -> str:
        """
        Thiết bị đang chạy model.
        """

        return str(self._device)

    @property
    def model_name(self) -> str:
        return self.config.model_name

    # ==========================================================
    # Main API
    # ==========================================================

    def translate(
        self,
        text: str,
    ) -> LanguageTranslationResult:
        """
        Dịch một đoạn tiếng Anh sang tiếng Việt.

        Parameters
        ----------
        text:
            Text sau OCR correction và text grouping.

        Returns
        -------
        LanguageTranslationResult
            Text gốc, text đã xử lý và bản dịch.
        """

        source_text = self._validate_text(text)

        if not source_text.strip():
            return LanguageTranslationResult(
                source_text=source_text,
                translated_text="",
                processed_text="",
                device=self.device,
            )

        processed_text = self._prepare_text(
            source_text
        )

        model_input = self._add_language_token(
            processed_text
        )

        try:
            encoded = self._tokenizer(
                model_input,
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_input_tokens,
                padding=False,
            )

            encoded = {
                name: tensor.to(self._device)
                for name, tensor in encoded.items()
            }

            with torch.inference_mode():
                generated_ids = self._model.generate(
                    **encoded,
                    max_new_tokens=(
                        self.config.max_new_tokens
                    ),
                    num_beams=self.config.num_beams,
                    length_penalty=(
                        self.config.length_penalty
                    ),
                    early_stopping=(
                        self.config.early_stopping
                    ),
                    do_sample=False,
                )

            translated_text = (
                self._tokenizer.batch_decode(
                    generated_ids,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )[0]
            )

            translated_text = self._clean_output(
                translated_text
            )

        except Exception as exc:
            raise LanguageTranslationInferenceError(
                "The translation model could not translate "
                "the supplied text."
            ) from exc

        return LanguageTranslationResult(
            source_text=source_text,
            translated_text=translated_text,
            processed_text=processed_text,
            device=self.device,
        )

    def translate_text(
        self,
        text: str,
    ) -> str:
        """
        API rút gọn: chỉ trả về chuỗi tiếng Việt.
        """

        return self.translate(
            text
        ).translated_text

    def __call__(
        self,
        text: str,
    ) -> LanguageTranslationResult:
        """
        Cho phép gọi object như một function.

        Example
        -------
        translator = LanguageTranslator()

        result = translator(
            "The plane took off."
        )
        """

        return self.translate(text)

    # ==========================================================
    # Model loading
    # ==========================================================

    def _load_model(self) -> None:
        """
        Tải tokenizer và model một lần.
        """

        try:
            self._tokenizer = (
                AutoTokenizer.from_pretrained(
                    self.config.model_name,
                    local_files_only=(
                        self.config.local_files_only
                    ),
                )
            )

            self._model = (
                AutoModelForSeq2SeqLM.from_pretrained(
                    self.config.model_name,
                    local_files_only=(
                        self.config.local_files_only
                    ),
                )
            )

            self._model.to(self._device)

            if (
                self._device.type == "cuda"
                and self.config.use_float16_on_gpu
            ):
                self._model.half()

            self._model.eval()

        except Exception as exc:
            raise LanguageModelLoadError(
                "Could not load translation model "
                f"{self.config.model_name!r}."
            ) from exc

    def _resolve_device(self) -> torch.device:
        """
        Chọn CPU hoặc CUDA.
        """

        if self.config.device == "cpu":
            return torch.device("cpu")

        if self.config.device == "gpu":
            if not torch.cuda.is_available():
                raise LanguageModelLoadError(
                    "device='gpu' was requested, but CUDA "
                    "is not available."
                )

            return torch.device("cuda")

        # device == "auto"
        if torch.cuda.is_available():
            return torch.device("cuda")

        return torch.device("cpu")

    # ==========================================================
    # Text processing
    # ==========================================================

    def _prepare_text(
        self,
        text: str,
    ) -> str:
        """
        Chuẩn hóa nhẹ đầu vào.

        Không:
            - lowercase;
            - lemma;
            - xóa dấu câu;
            - thay đổi thì;
            - tách từng từ.
        """

        if not self.config.normalize_whitespace:
            return text.strip()

        return self.WHITESPACE_PATTERN.sub(
            " ",
            text,
        ).strip()

    def _add_language_token(
        self,
        text: str,
    ) -> str:
        """
        Thêm token chỉ định tiếng Việt ở đầu câu.

        Input:

            She decided to give up.

        Model input:

            >>vie<< She decided to give up.
        """

        language_token = (
            self.config.target_language_token.strip()
        )

        if not language_token:
            return text

        return f"{language_token} {text}"

    def _clean_output(
        self,
        text: str,
    ) -> str:
        """
        Hậu xử lý tối thiểu cho output của model.
        """

        cleaned = text.strip()

        if self.config.normalize_whitespace:
            cleaned = self.WHITESPACE_PATTERN.sub(
                " ",
                cleaned,
            )

        return cleaned

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_text(
        self,
        text: str,
    ) -> str:
        if not isinstance(text, str):
            raise LanguageTranslationInputError(
                "text must be a string, "
                f"received {type(text).__name__}."
            )

        if "\x00" in text:
            raise LanguageTranslationInputError(
                "text must not contain null characters."
            )

        if (
            len(text)
            > self.config.max_input_characters
        ):
            raise LanguageTranslationInputError(
                "text exceeds the configured maximum of "
                f"{self.config.max_input_characters} characters."
            )

        return text