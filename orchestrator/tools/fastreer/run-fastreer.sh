#!/bin/bash

set -e

echo "Working directory: $(pwd)"
mkdir -p /workspace
cd /workspace


if [ ! -f "/data/merged.vcf.gz" ]; then
  echo "Error: Merged VCF file not found at /data/merged.vcf.gz"
  echo "Please run the merger step first!"
  exit 1
fi

echo "Step 1: Building distance matrix from VCF"

zcat /data/merged.vcf.gz | fastreeR VCF2DIST \
    -i - \
    -o distance_matrix.txt \
    -t "4"

echo "Step 2: Building tree from distance matrix"

fastreeR DIST2TREE \
    -i distance_matrix.txt \
    -o output.nwk \
    -v

echo "Tree construction complete"

echo "Step 3: Copying results to output directory"

TREEFILE=$(ls *.nwk 2>/dev/null | head -n1)
if [ -n "$TREEFILE" ]; then 
  cp "$TREEFILE" /results/output.nwk
  echo "Tree file copied as output.nwk"
fi

echo "fastreeR analysis complete!"
