from __future__ import annotations

from typing import Annotated

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from backend.pipeline import (
    BackendPipeline,
    BackendPipelineExecutionError,
    BackendPipelineInputError,
    PipelineConfig,
)


app = FastAPI(
    title="SubVision Backend API",
    version="1.0.0",
    description="HTTP inference API for the SubVision backend pipeline.",
)


# Create one pipeline instance and reuse it across requests.
# This avoids rebuilding/reloading backend components for every request.
pipeline = BackendPipeline()


@app.get("/")
def root():
    return {
        "service": "SubVision Backend",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.post("/process")
async def process_image(
    file: Annotated[UploadFile, File(...)],

    ocr_mode: Annotated[str, Form()] = "fast",

    translation_mode: Annotated[str | None, Form()] = "dictionary",

    enable_dashboard: Annotated[bool, Form()] = False,

    enable_ocr_correction: Annotated[bool, Form()] = True,
):
    """
    Receive an image, run the SubVision backend pipeline,
    and return the result as JSON.
    """

    # ---------------------------------------------------------
    # 1. Read uploaded image
    # ---------------------------------------------------------

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    # ---------------------------------------------------------
    # 2. Decode image
    #
    # cv2.imdecode() produces:
    #
    # numpy.ndarray
    # uint8
    # BGR
    #
    # which matches BackendPipeline's image contract.
    # ---------------------------------------------------------

    buffer = np.frombuffer(image_bytes, dtype=np.uint8)

    image = cv2.imdecode(
        buffer,
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to decode uploaded image.",
        )

    # ---------------------------------------------------------
    # 3. Build pipeline config
    # ---------------------------------------------------------

    # HTTP forms cannot naturally represent Python None.
    # Allow clients to send:
    #
    # translation_mode=none
    #
    # to disable translation.

    if translation_mode is not None:
        translation_mode = translation_mode.strip().lower()

        if translation_mode in {"none", "null", ""}:
            translation_mode = None

    try:
        config = PipelineConfig(
            ocr_mode=ocr_mode,
            translation_mode=translation_mode,
            enable_dashboard=enable_dashboard,
            enable_ocr_correction=enable_ocr_correction,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    # ---------------------------------------------------------
    # 4. Run backend pipeline
    # ---------------------------------------------------------

    try:
        result = pipeline.run(
            image=image,
            config=config,
        )

    except BackendPipelineInputError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except BackendPipelineExecutionError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    # ---------------------------------------------------------
    # 5. Convert PipelineResult -> JSON-safe dictionary
    # ---------------------------------------------------------

    response = {
        "config": {
            "ocr_mode": result.config.ocr_mode,
            "translation_mode": result.config.translation_mode,
            "enable_dashboard": result.config.enable_dashboard,
            "enable_ocr_correction": result.config.enable_ocr_correction,
        },

        "elapsed_seconds": result.elapsed_seconds,

        "empty": result.empty,

        "ocr_items": [
            {
                "text": item.text,
                "confidence": item.confidence,
                "bbox": {
                    "x1": item.bbox.x1,
                    "y1": item.bbox.y1,
                    "x2": item.bbox.x2,
                    "y2": item.bbox.y2,
                    "width": item.bbox.width,
                    "height": item.bbox.height,
                },
            }
            for item in result.ocr_items
        ],

        "translation_result": None,

        "dashboard_result": None,
    }

    # ---------------------------------------------------------
    # Translation result
    # ---------------------------------------------------------

    if result.translation_result is not None:
        response["translation_result"] = {
            "items": [
                {
                    "unit_type": item.unit_type,

                    "bbox": {
                        "x1": item.bbox.x1,
                        "y1": item.bbox.y1,
                        "x2": item.bbox.x2,
                        "y2": item.bbox.y2,
                        "width": item.bbox.width,
                        "height": item.bbox.height,
                    },

                    "raw_text": item.raw_text,
                    "corrected_text": item.corrected_text,
                    "translated_text": item.translated_text,
                    "confidence": item.confidence,
                }
                for item in result.translation_result.items
            ]
        }

    # ---------------------------------------------------------
    # Dashboard result
    # ---------------------------------------------------------

    if result.dashboard_result is not None:
        response["dashboard_result"] = {
            "entries": [
                {
                    "term": entry.term,
                    "meanings": list(entry.meanings),
                    "ipas": list(entry.ipas),
                    "entry_type": entry.entry_type,
                }
                for entry in result.dashboard_result.entries
            ]
        }

    return response