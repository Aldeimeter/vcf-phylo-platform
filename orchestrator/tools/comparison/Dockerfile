FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY scripts/pyproject.toml scripts/uv.lock ./

RUN uv sync --frozen --no-dev

COPY scripts/main.py ./

CMD ["uv", "run", "python", "main.py"]

