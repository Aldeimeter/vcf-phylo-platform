import copy
import json
import math
import os

import dendropy


SIMILARITY_THRESHOLD = 0.1


def deroot_if_needed(tree):
    if len(tree.seed_node.child_nodes()) == 2:
        tree.deroot()


def load_trees():
    trees_path = {
        "iqtree": "/data/iqtree/output.nwk",
        "mrbayes": "/data/mrbayes/output.nwk",
        "fastreer": "/data/fastreer/output.nwk",
    }

    trees = {}

    for name, path in trees_path.items():
        if os.path.exists(path):
            try:
                tree = dendropy.Tree.get(path=path, schema="newick")
                deroot_if_needed(tree)
                trees[name] = tree
                print(f"Loaded {name} tree from {path}")
            except Exception as e:
                print(f"Error loading {name} tree: {e}")

    return trees


def normalize_branch_lengths(tree):
    t = copy.deepcopy(tree)
    total = sum(e.length for e in t.postorder_edge_iter() if e.length is not None)
    if total > 0:
        for edge in t.postorder_edge_iter():
            if edge.length is not None:
                edge.length /= total
    return t


def pearson_on_matched_splits(tree1, tree2):
    tree1.encode_bipartitions()
    tree2.encode_bipartitions()

    splits1 = {
        e.bipartition.split_bitmask: e.length
        for e in tree1.postorder_edge_iter()
        if e.bipartition is not None and e.length is not None
    }
    splits2 = {
        e.bipartition.split_bitmask: e.length
        for e in tree2.postorder_edge_iter()
        if e.bipartition is not None and e.length is not None
    }

    common = set(splits1.keys()) & set(splits2.keys())
    if len(common) < 2:
        return None

    x = [splits1[b] for b in common]
    y = [splits2[b] for b in common]

    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    den = math.sqrt(
        sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y)
    )

    if den == 0:
        return None
    return num / den


def compare_topology(tree1, tree2):
    tree2.migrate_taxon_namespace(tree1.taxon_namespace)

    raw_rf = dendropy.calculate.treecompare.symmetric_difference(tree1, tree2)
    num_taxa = len(tree1.taxon_namespace)
    max_rf = 2 * (num_taxa - 3) if num_taxa >= 3 else 0
    normalized_rf = raw_rf / max_rf if max_rf > 0 else 0

    return {
        "raw_rf": raw_rf,
        "normalized_rf": normalized_rf,
        "similar": normalized_rf <= SIMILARITY_THRESHOLD,
    }


def compare_length(name1, name2, tree1, tree2, similar):
    if not similar:
        return None

    involves_fastreer = "fastreer" in (name1, name2)

    if not involves_fastreer:
        wrf = dendropy.calculate.treecompare.weighted_robinson_foulds_distance(
            tree1, tree2
        )
        return {"comparison_type": "direct", "wrf": wrf}

    t1_norm = normalize_branch_lengths(tree1)
    t2_norm = normalize_branch_lengths(tree2)
    t2_norm.migrate_taxon_namespace(t1_norm.taxon_namespace)

    wrf = dendropy.calculate.treecompare.weighted_robinson_foulds_distance(
        t1_norm, t2_norm
    )
    pearson_r = pearson_on_matched_splits(t1_norm, t2_norm)

    result = {
        "comparison_type": "normalized",
        "normalization": "total_tree_length",
        "wrf": wrf,
    }
    if pearson_r is not None:
        result["pearson_r"] = pearson_r
    return result


def compare_trees(trees):
    results = {}
    tree_names = list(trees.keys())

    for i in range(len(tree_names)):
        for j in range(i + 1, len(tree_names)):
            name1, name2 = tree_names[i], tree_names[j]
            t1, t2 = trees[name1], trees[name2]
            key = f"{name1}_vs_{name2}"

            print(f"Comparing {name1} vs {name2}")

            try:
                topo = compare_topology(t1, t2)
            except Exception as e:
                print(f"Error comparing topology {name1} vs {name2}: {e}")
                results[key] = {"topology": {"error": str(e)}, "branch_lengths": None}
                continue

            lengths = None
            try:
                lengths = compare_length(name1, name2, t1, t2, topo["similar"])
            except Exception as e:
                print(f"Error comparing branch lengths {name1} vs {name2}: {e}")
                lengths = {"error": str(e)}

            results[key] = {"topology": topo, "branch_lengths": lengths}

    output_path = "/results/results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Comparison results saved to {output_path}")


if __name__ == "__main__":
    trees = load_trees()
    compare_trees(trees)
