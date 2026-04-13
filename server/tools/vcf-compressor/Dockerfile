FROM alpine:3.22 AS htslib-builder

RUN apk add --no-cache bzip2-dev curl-dev g++ gcc make musl-dev xz-dev zlib-dev wget

WORKDIR /tmp
RUN wget https://github.com/samtools/htslib/releases/download/1.22/htslib-1.22.tar.bz2 && \
    tar xjf htslib-1.22.tar.bz2

WORKDIR /tmp/htslib-1.22
RUN mkdir /tmp/htslib && ./configure --prefix=/tmp/htslib && make && make install

FROM alpine:3.22

RUN apk add --no-cache \
    libcurl \
    libbz2 \
    xz-libs \
    zlib

COPY --from=htslib-builder /tmp/htslib/bin/bgzip /usr/local/bin/bgzip
COPY --from=htslib-builder /tmp/htslib/lib/ /usr/local/lib/

COPY compress.sh /app/compress.sh
RUN chmod +x /app/compress.sh

CMD ["sh"]
