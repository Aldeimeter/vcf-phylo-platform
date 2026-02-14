FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update && apt-get install -y \
      docker.io \
      && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .

RUN uv sync --no-dev

COPY . .
RUN chmod +x ./start.sh

ENTRYPOINT ["/app/start.sh"]
