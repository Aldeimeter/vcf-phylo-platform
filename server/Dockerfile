  # Multi-stage build for phylogenetic comparison API
  FROM ghcr.io/astral-sh/uv:python3.13-alpine AS builder

  # Set working directory
  WORKDIR /app

  # Copy dependency files
  COPY pyproject.toml uv.lock ./

  # Install dependencies into a virtual environment
  ENV UV_PROJECT_ENVIRONMENT=/opt/venv
  RUN uv sync --frozen --no-dev

  # Final stage
  FROM python:3.13-alpine

  # System deps required by WeasyPrint (Cairo, Pango, fonts)
  RUN apk add --no-cache \
      pango \
      cairo \
      fontconfig \
      ttf-freefont

  # Copy virtual environment from builder
  COPY --from=builder /opt/venv /opt/venv

  # Add venv to PATH
  ENV PATH="/opt/venv/bin:$PATH"

  # Set working directory
  WORKDIR /app

  # Copy application code
  COPY app/ ./app/

  # Expose port
  EXPOSE 8000

  # Run FastAPI - note the module path
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
