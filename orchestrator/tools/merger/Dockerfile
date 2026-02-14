FROM alpine:3.22 AS tar-installer

RUN apk add --no-cache tar wget

WORKDIR /tmp

FROM tar-installer AS htslib-installation

RUN apk add --no-cache bzip2-dev curl-dev g++ gcc make musl-dev xz-dev zlib-dev

RUN wget https://github.com/samtools/htslib/releases/download/1.22/htslib-1.22.tar.bz2 && \
    tar xjf htslib-1.22.tar.bz2

WORKDIR /tmp/htslib-1.22

RUN mkdir /tmp/htslib
RUN ./configure --prefix=/tmp/htslib/ && make && make install

# Then modify the bcftools section to depend on htslib
FROM htslib-installation AS bcftools-installation

WORKDIR /tmp

# Build bcftools (same as before)
RUN wget https://github.com/samtools/bcftools/releases/download/1.22/bcftools-1.22.tar.bz2 && \
    tar xjf bcftools-1.22.tar.bz2

WORKDIR /tmp/bcftools-1.22
RUN mkdir /tmp/bcftools
RUN ./configure --prefix=/tmp/bcftools/ --with-htslib=/tmp/htslib && make && make install

FROM alpine:3.22 AS final

# Install runtime dependencies for bgzip and bcftools
RUN apk add --no-cache \
    libcurl \
    libbz2 \
    xz-libs \
    zlib

# Copy both htslib and bcftools binaries
COPY --from=htslib-installation /tmp/htslib/bin/* /usr/local/bin/
COPY --from=htslib-installation /tmp/htslib/lib/* /usr/local/lib/
COPY --from=bcftools-installation /tmp/bcftools/bin/* /usr/local/bin/

WORKDIR /app
COPY ./merge-vcf-simple.sh ./merge-vcf.sh
RUN chmod +x ./merge-vcf.sh


CMD ["sh"]
