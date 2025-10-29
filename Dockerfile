FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости для lxml и других пакетов
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        libjpeg-dev \
        libpng-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY templates ./templates
COPY config ./config

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir .

RUN mkdir -p storage/contracts storage/meta generated

ENV PYTHONPATH=/app

CMD ["python", "-m", "contract_bot.main"]

