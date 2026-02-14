#!/bin/sh
# Internal script that runs inside Docker container to merge VCF files with caching support

set -e

# Check verbosity setting (default to false if not set)
VERBOSE=${VERBOSE:-false}
SAVE_INTERMEDIATES=${SAVE_INTERMEDIATES:-false}

echo "Working directory: $(pwd)"
mkdir -p /workspace
cd /workspace

# Cache directory
VCF_CACHE="/cache/vcf"

# Generate cache key based on input files
DATA_HASH=$(ls -l /data/*.vcf | md5sum | cut -d' ' -f1)
VCF_CACHE_FILE="${VCF_CACHE}/merged_${DATA_HASH}.vcf.gz"
VCF_INDEX_FILE="${VCF_CACHE_FILE}.csi"

echo "Cache key: $DATA_HASH"
echo ""

# Check if cached merged VCF exists
if [ -f "$VCF_CACHE_FILE" ] && [ -f "$VCF_INDEX_FILE" ]; then
    echo "Step 1: Using cached merged VCF file..."
    cp "$VCF_CACHE_FILE" merged.vcf.gz
    cp "$VCF_INDEX_FILE" merged.vcf.gz.csi
    echo "✓ Loaded from cache"
else
    echo "Step 1: Compressing and indexing VCF files..."
    for vcf in /data/*.vcf; do
        filename=$(basename "$vcf")
        echo "  Processing $filename..."
        if [ "$VERBOSE" = "true" ]; then
            bgzip -c "$vcf" > "${filename}.gz"
            bcftools index "${filename}.gz"
        else
            bgzip -c "$vcf" > "${filename}.gz" 2>&1 | grep -v "^$" || true
            bcftools index "${filename}.gz" 2>&1 | grep -v "^$" || true
        fi
    done
    echo "✓ VCF files compressed and indexed"

    echo ""
    echo "Step 2: Merging VCF files..."
    if [ "$VERBOSE" = "true" ]; then
        bcftools merge *.vcf.gz -Oz -o merged.vcf.gz
        bcftools index merged.vcf.gz
    else
        bcftools merge *.vcf.gz -Oz -o merged.vcf.gz 2>&1 | grep -v "^$" || true
        bcftools index merged.vcf.gz 2>&1 | grep -v "^$" || true
    fi
    echo "✓ VCF files merged"

    # Save to cache
    echo ""
    echo "Saving merged VCF to cache..."
    cp merged.vcf.gz "$VCF_CACHE_FILE"
    cp merged.vcf.gz.csi "$VCF_INDEX_FILE"
    echo "✓ Cached for future use"
fi

echo ""
echo "Step 3: Handling output..."

# VCF is always saved to cache for pipeline use
# Only copy to results if --save-intermediates is set
if [ "$SAVE_INTERMEDIATES" = "true" ]; then
    echo "Copying merged VCF to results directory..."
    cp merged.vcf.gz /results/
    cp merged.vcf.gz.csi /results/
    echo "✓ Results copied to /results"
else
    echo "Merged VCF saved to cache only (use --save-intermediates to save to results)"
    echo "Cache location: $VCF_CACHE_FILE"
    # Create a marker file so pipelines know where to find the VCF
    echo "$VCF_CACHE_FILE" > /results/.vcf_cache_location
fi

echo ""
echo "Merge complete!"
echo ""
