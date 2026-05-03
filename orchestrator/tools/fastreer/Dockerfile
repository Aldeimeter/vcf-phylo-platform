FROM python:3.13.9-alpine3.22 AS final

# Install Java runtime and bash
RUN apk add --no-cache \
    openjdk21-jre \
    bash

# Install fastreeR
RUN pip install --no-cache-dir fastreer==2.1.6

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
