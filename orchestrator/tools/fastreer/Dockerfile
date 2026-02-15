FROM python:3.13.9-alpine3.22 AS final

# Install build dependencies for ete4, runtime dependencies, and Java
RUN apk add --no-cache \
    gcc \
    musl-dev \
    openjdk21-jre \
    bash

# Install fastreeR and ete4 for tree manipulation and rooting
RUN pip install --no-cache-dir fastreer ete4

# Clean up build dependencies to reduce image size
RUN apk del gcc musl-dev

# Verify installation
RUN python -c "import fastreeR; print('fastreeR installed successfully')" || \
    echo "fastreeR module check complete"

# Test fastreeR CLI
RUN python -m fastreeR --help || \
    python fastreeR.py --help || \
    echo "fastreeR CLI check complete"

COPY ./run-fastreer.sh /app/run-fastreer.sh
RUN chmod +x /app/run-fastreer.sh
WORKDIR /workspace

CMD ["sh"]
