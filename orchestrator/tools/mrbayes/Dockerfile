FROM alpine:3.22 AS vcf2phylip-installation

RUN apk add --no-cache git

WORKDIR /tmp

RUN git clone --depth=1 --branch v2.8 https://github.com/edgardomortiz/vcf2phylip.git

# Stage: Build MrBayes
FROM alpine:3.22 AS mrbayes-build

RUN apk add --no-cache \
    git \
    autoconf \
    automake \
    build-base \
    readline-dev

WORKDIR /tmp

RUN git clone --depth=1 --branch v3.2.7 https://github.com/NBISweden/MrBayes.git

WORKDIR /tmp/MrBayes

RUN ./configure --prefix=/tmp/mrbayes-install && \
    make && \
    make install

# Final stage: Combine all tools
FROM python:3.13.9-alpine3.22 AS final

# Install runtime dependencies
RUN apk add --no-cache \
    readline \
    bash

# Copy tools from build stages
COPY --from=vcf2phylip-installation /tmp/vcf2phylip/vcf2phylip.py /usr/local/bin/vcf2phylip
COPY --from=mrbayes-build /tmp/mrbayes-install/bin/mb /usr/local/bin/mb

# Verify MrBayes installation
RUN mb --version || echo "MrBayes installed"

WORKDIR /app
COPY ./run-mrbayes.sh .
COPY ./utils ./utils

CMD ["sh"]
