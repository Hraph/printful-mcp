# syntax=docker/dockerfile:1

# ---------- Build stage: build the wheel and install deps into a venv ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install .

# ---------- Runtime stage: minimal image, non-root user ----------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="printful-mcp" \
      org.opencontainers.image.description="MCP server for the Printful API" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

USER app
WORKDIR /app

EXPOSE 8000

# The streamable-HTTP endpoint answers GET /mcp with 4xx without a session,
# so we only check that the port accepts TCP connections.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,socket; socket.create_connection(('127.0.0.1', int(os.environ.get('MCP_PORT', '8000'))), timeout=3)" \
        || exit 1

ENTRYPOINT ["python", "-m", "printful_mcp"]
