FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Apply Debian security updates on top of the pinned base image.
# The upstream uv image is rebuilt on a slower cadence than the Debian
# security tracker, so we refresh libssl3/libgnutls30/libcap2/openssl/etc.
# to close HIGH/CRITICAL CVEs at build time (verified by Trivy in CI).
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for layer cache
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY . .

# Run as non-root for defense-in-depth (Azure Container Apps compatible).
# Port 8400 is > 1024, no privileged bind required.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app \
    && chown -R app:app /app
USER app

EXPOSE 8400

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8400/health')"

CMD [".venv/bin/python", "main.py"]