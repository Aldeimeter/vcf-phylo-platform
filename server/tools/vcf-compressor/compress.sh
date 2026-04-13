#!/bin/sh
set -e

for vcf in /data/*.vcf; do
  if [ -f "$vcf" ]; then
    echo "Compressing $(basename "$vcf")..."
    bgzip "$vcf"
    echo "Done: $(basename "$vcf").gz"
  fi
done

echo "Compression complete"
