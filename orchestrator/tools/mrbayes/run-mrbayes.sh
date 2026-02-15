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


echo "Step 1: Converting VCF to PHYLIP format..."

vcf2phylip -i /data/merged.vcf.gz

PHYLIP_FILE=$(ls *.min*.phy 2>/dev/null | head -n1)
if [ -z "$PHYLIP_FILE" ]; then
    PHYLIP_FILE=$(ls *.phy 2>/dev/null | head -n1)
fi


if [ -z "$PHYLIP_FILE" ]; then
    echo "Error: No PHYLIP file generated"
    exit 1
fi

echo "Step 2: Converting PHYLIP to MrBayes-compatible NEXUS format..."

python3 /app/utils/phy2nexus.py $PHYLIP_FILE


echo "Step 3: Creating command file"

# Determine number of generations based on environment variable or use default
NGEN=${MRBAYES_NGEN:-100000}
SAMPLEFREQ=${MRBAYES_SAMPLEFREQ:-100}
PRINTFREQ=${MRBAYES_PRINTFREQ:-1000}
NCHAINS=${MRBAYES_NCHAINS:-4}
NRUNS=${MRBAYES_NRUNS:-2}
SEED=${MRBAYES_SEED:-12345}
SWAPSEED=${MRBAYES_SWAPSEED:-54321}

cat > mrbayes_commands.nex << EOF
#NEXUS
begin mrbayes;
    set autoclose=yes nowarn=yes;
    set seed=$SEED;
    set swapseed=$SWAPSEED;
    execute alignment.nex;

    lset nst=6 rates=gamma;

    mcmcp ngen=$NGEN samplefreq=$SAMPLEFREQ printfreq=$PRINTFREQ;
    mcmcp nchains=$NCHAINS nruns=$NRUNS;
    mcmcp filename=output;
    mcmcp burninfrac=0.25;

    mcmc;
    sumt;

    quit;
end;
EOF


echo "Step 4: Running MrBayes Bayesian analysis..."
echo "This may take a while depending on dataset size and number of generations..."

mb mrbayes_commands.nex

echo "Step 5: Converting consensus tree to Newick format..."

python3 /app/utils/nexus2nwk.py


echo "Step 6: Copying results to output directory..."

TREEFILE=$(ls *.nwk 2>/dev/null | head -n1)
if [ -n "$TREEFILE" ]; then 
  cp "$TREEFILE" /results/output.nwk
  echo "Tree file copied as output.nwk"
fi


echo "MrBayes analysis complete!"
