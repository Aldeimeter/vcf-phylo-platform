#!/bin/bash

set -e

echo "Working directory: $(pwd)"
mkdir -p /workspace
cd /workspace

echo "Step 1: Compressing and indexing VCF files..."

for vcf in /data/*.vcf; do
  if [ -f "$vcf" ]; then
    filename=$(basename "$vcf")
    echo " Processing $filename..."
    bgzip -c "$vcf" > "${filename}.gz"
    if ! bcftools index "${filename}.gz" 2>/dev/null; then
      echo "  Unsorted, re-sorting $filename..."
      bcftools sort "$vcf" -Oz -o "${filename}.gz"
      bcftools index "${filename}.gz"
    fi
  fi
done

for vcfgz in /data/*.vcf.gz; do
  if [ -f "$vcfgz" ]; then
    filename=$(basename "$vcfgz")
    echo " Processing $filename (already compressed)..."
    cp "$vcfgz" "${filename}"
    if ! bcftools index "${filename}" 2>/dev/null; then
      echo "  Unsorted, re-sorting $filename..."
      bcftools sort "${filename}" -Oz -o "${filename}.sorted.gz"
      mv "${filename}.sorted.gz" "${filename}"
      bcftools index "${filename}"
    fi
  fi
done

echo "VCF files compressed and indexed"

echo ""

echo "Step 2: Merging VCF files..."
bcftools merge *.vcf.gz -Oz -o merged.vcf.gz
bcftools index merged.vcf.gz
echo "VCF files merged"

echo ""

echo "Step 3: Saving results..."
cp merged.vcf.gz /results/
cp merged.vcf.gz.csi /results/
echo "Results saved to /results"

echo ""
echo "Merge complete!"

