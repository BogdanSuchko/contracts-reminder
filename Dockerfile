# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

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
COPY README.md ./README.md
COPY scripts ./scripts

RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

RUN mkdir -p storage/contracts storage/meta generated

CMD ["python", "-m", "contract_bot.main"]
