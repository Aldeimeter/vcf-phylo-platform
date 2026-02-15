import sys

if len(sys.argv) != 2:
    print("Usage: python3 convert_phylip_to_nexus.py <phylip_file>")
    sys.exit(1)

phylip_file = sys.argv[1]

with open(phylip_file, "r") as f:
    lines = f.readlines()

header = lines[0].strip().split()
ntax = int(header[0])
nchar = int(header[1])

taxa = []
sequences = []
for i in range(1, ntax + 1):
    parts = lines[i].strip().split(None, 1)
    taxa.append(parts[0])
    if len(parts) > 1:
        sequences.append(parts[1].replace(" ", "").replace("\n", ""))
    else:
        sequences.append("")

with open("alignment.nex", "w") as f:
    f.write("#NEXUS\n\n")
    f.write("begin data;\n")
    f.write(f"    dimensions ntax={ntax} nchar={nchar};\n")
    f.write("    format datatype=dna missing=N gap=- interleave=yes;\n")
    f.write("    matrix\n")

    block_size = 60
    for start in range(0, nchar, block_size):
        end = min(start + block_size, nchar)
        for i in range(ntax):
            taxon_name = taxa[i].ljust(20)
            seq_block = sequences[i][start:end] if start < len(sequences[i]) else ""
            f.write(f"    {taxon_name} {seq_block}\n")
        f.write("\n")

    f.write("    ;\n")
    f.write("end;\n")

print("NEXUS file created successfully")
