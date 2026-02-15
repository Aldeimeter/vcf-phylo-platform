import re

with open("output.con.tre", "r") as f:
    content = f.read()

# Extract translation table
translation = {}
translate_match = re.search(r"translate\s+(.*?);", content, re.DOTALL | re.IGNORECASE)
if translate_match:
    trans_block = translate_match.group(1)
    # Parse translation entries (e.g., "1 CRUK0052_BS_GL,")
    for line in trans_block.strip().split("\n"):
        line = line.strip().rstrip(",")
        if line:
            parts = line.split(None, 1)
            if len(parts) == 2:
                num = parts[0]
                name = parts[1].rstrip(",")
                translation[num] = name

# Find the tree line
tree_match = re.search(r"tree\s+\S+\s*=\s*(.+?);", content, re.DOTALL)

if tree_match:
    tree_string = tree_match.group(1).strip()

    # Remove MrBayes annotations
    clean_tree = re.sub(r"\[&[^\]]+\]", "", tree_string)
    clean_tree = re.sub(r"\[&U\]", "", clean_tree)
    clean_tree = re.sub(r"\s+", "", clean_tree)

    # Convert scientific notation branch lengths to decimal notation FIRST
    # This must happen before taxon name replacement to avoid corrupting branch lengths
    def convert_branch_lengths(tree_str):
        def replace_length(match):
            length_str = match.group(1)
            try:
                length = float(length_str)
                # Format with enough precision but use decimal notation
                return ":" + f"{length:.10f}".rstrip("0").rstrip(".")
            except ValueError:
                return match.group(0)

        # Match colon followed by number (including scientific notation)
        return re.sub(r":([0-9.eE+-]+)", replace_length, tree_str)

    clean_tree = convert_branch_lengths(clean_tree)

    # NOW replace numeric IDs with actual taxon names
    # After branch lengths are in decimal format, numeric IDs won't be confused
    for num, name in translation.items():
        # Match taxon ID in tree context: after opening paren/comma, before colon/comma/closing paren
        clean_tree = re.sub(r"([(,])" + num + r"(?=[:,)])", r"\1" + name, clean_tree)

    # Write clean Newick tree with proper termination
    with open("output.nwk", "w") as f:
        # Ensure tree ends with semicolon
        if not clean_tree.endswith(";"):
            clean_tree += ";"
        f.write(clean_tree)
        f.write("\n")

    print("✓ Newick tree generated with sample names")
else:
    print("Warning: Could not extract tree from NEXUS file")
