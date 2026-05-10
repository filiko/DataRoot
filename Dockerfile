FROM python:3.11-slim

ARG GITKB_VERSION=0.1.55

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV DATAROOT_SERVER_KB_BACKEND=gitkb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://raw.githubusercontent.com/gitkb/gitkb-releases/main/install.sh \
      | VERSION="${GITKB_VERSION}" INSTALL_DIR="/usr/local/bin" bash \
    && git config --system user.name "DataRoot" \
    && git config --system user.email "dataroot@example.local"

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY ExampleData ./ExampleData
COPY docs ./docs
COPY tests ./tests

CMD ["sh", "-c", "python -m uvicorn dataroot.server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
