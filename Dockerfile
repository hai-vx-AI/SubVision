FROM python:3.12-slim

# ------------------------------------------------------------
# Environment
# ------------------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1


# ------------------------------------------------------------
# Working directory inside container
# ------------------------------------------------------------

WORKDIR /app


# ------------------------------------------------------------
# System dependencies
#
# libgl1 / libglib2.0-0 are commonly needed by OpenCV.
# We can refine this later after inspecting requirements.txt.
# ------------------------------------------------------------

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*


# ------------------------------------------------------------
# Python dependencies
#
# Copy requirements first so Docker can cache this layer.
# ------------------------------------------------------------

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt


# ------------------------------------------------------------
# Copy project
# ------------------------------------------------------------

COPY . .


# ------------------------------------------------------------
# API port
# ------------------------------------------------------------

EXPOSE 8000


# ------------------------------------------------------------
# Start SubVision API
# ------------------------------------------------------------

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]