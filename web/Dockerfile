# Multi-stage build for Shiny web frontend
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

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Add venv to PATH
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY app.py ./
COPY www/ ./www/

# Expose port
EXPOSE 8080

# Run Shiny app
CMD ["python", "-m", "shiny", "run", "app.py", "--host", "0.0.0.0", "--port", "8080"]
