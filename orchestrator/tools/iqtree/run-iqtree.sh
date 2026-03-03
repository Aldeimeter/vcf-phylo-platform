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

echo "Using merged VCF: /data/merged.vcf.gz"

echo "Step 1: Converting VCF to phylip format..."
vcf2phylip -i /data/merged.vcf.gz
echo "Conversion complete"

echo "Step 2: Building phylogenetic tree with IQ-TREE..."
PHYLIP_FILE=$(ls *.phy | head -n1)

if [ -z "$PHYLIP_FILE" ]; then
  echo "Error: No .phy file generated"
  exit 1
fi

echo "Using phylip file: $PHYLIP_FILE"

SEED=${IQTREE_SEED:-12345}
iqtree3 -s "$PHYLIP_FILE" -st DNA -m GTR+G -B 1000 -T AUTO -seed $SEED
echo "Tree construction complete"

echo "Step 3: Copying results to output directory"
TREEFILE=$(ls *.treefile 2>/dev/null | head -n1)
if [ -n "$TREEFILE" ]; then 
  cp "$TREEFILE" /results/output.nwk
  echo "Tree file copied as output.nwk"
fi

echo "IQ-TREE analysis complete!"

