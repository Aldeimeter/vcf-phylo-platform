FROM alpine:3.22 AS tar-installer

RUN apk add --no-cache tar wget

WORKDIR /tmp

FROM tar-installer AS iqtree3-installation

RUN wget https://github.com/iqtree/iqtree3/releases/download/v3.0.1/iqtree-3.0.1-Linux-intel.tar.gz && \
  tar xzf iqtree-3.0.1-Linux-intel.tar.gz

FROM alpine:3.22 AS vcf2phylip-installation

RUN apk add --no-cache git

WORKDIR /tmp

RUN git clone https://github.com/edgardomortiz/vcf2phylip.git

FROM python:3.13.9-alpine3.22 AS final

COPY --from=iqtree3-installation /tmp/iqtree-3.0.1-Linux-intel/bin/iqtree3 /usr/local/bin/iqtree3
COPY --from=vcf2phylip-installation /tmp/vcf2phylip/vcf2phylip.py /usr/local/bin/vcf2phylip

COPY run-iqtree.sh /app/run-iqtree.sh
RUN chmod +x /app/run-iqtree.sh

WORKDIR /data

CMD ["sh"]
