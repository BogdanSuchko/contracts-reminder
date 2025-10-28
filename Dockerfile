# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt-dev \
        libffi-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
COPY src ./src
COPY config ./config
COPY templates ./templates
COPY scripts ./scripts

RUN pip install --upgrade pip \
    && pip install --no-cache-dir \
        "aiogram>=3.4.1,<4.0.0" \
        "apscheduler>=3.10" \
        "docxtpl>=0.16" \
        "fastapi>=0.110" \
        "openpyxl>=3.1" \
        "pandas>=2.2" \
        "pydantic>=2.7" \
        "python-dotenv>=1.0" \
        "requests>=2.31" \
        "xlrd>=2.0" \
        "uvicorn>=0.30"

RUN mkdir -p storage/contracts storage/meta generated

CMD ["python", "-m", "contract_bot.main"]
