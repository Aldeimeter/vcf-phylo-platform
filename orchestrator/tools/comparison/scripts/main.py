import copy
import json
import math
import os

import dendropy


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
                print(f"Failed to load {name} tree from {path}: {e} — skipping this tool in comparison")

    return trees


def topology_similarity(tree1, tree2):
    """
    Returns topology similarity in % using normalized Robinson-Foulds distance.
    100% = identical topology, 0% = maximally different.
    """
    tree2.migrate_taxon_namespace(tree1.taxon_namespace)

    raw_rf = dendropy.calculate.treecompare.symmetric_difference(tree1, tree2)
    num_taxa = len(tree1.taxon_namespace)
    max_rf = 2 * (num_taxa - 3) if num_taxa >= 3 else 0
    normalized_rf = raw_rf / max_rf if max_rf > 0 else 0
    similarity = (1.0 - normalized_rf) * 100.0

    return {
        "similarity_pct": round(similarity, 2),
        "raw_rf": raw_rf,
        "normalized_rf": round(normalized_rf, 4),
    }


def patristic_distances(tree):
    """
    Returns a dict of {(taxon_label_a, taxon_label_b): distance} for all pairs.
    Uses PDM (patristic distance matrix) from dendropy.
    """
    pdm = tree.phylogenetic_distance_matrix()
    distances = {}
    taxa = list(tree.taxon_namespace)
    for i in range(len(taxa)):
        for j in range(i + 1, len(taxa)):
            key = tuple(sorted([taxa[i].label, taxa[j].label]))
            distances[key] = pdm(taxa[i], taxa[j])
    return distances


def pearson(x, y):
    n = len(x)
    if n < 2:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    den = math.sqrt(
        sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y)
    )
    if den == 0:
        return None
    return num / den


def spearman(x, y):
    def ranks(lst):
        order = sorted(range(len(lst)), key=lambda i: lst[i])
        r = [0.0] * len(lst)
        for rank, idx in enumerate(order):
            r[idx] = rank + 1.0
        return r
    return pearson(ranks(x), ranks(y))


def branch_length_similarity(tree1, tree2):
    """
    Returns Pearson and Spearman correlations of normalized patristic distance
    matrices. Normalization by total sum makes both metrics scale-independent
    (handles FastReer's cosine dissimilarity vs IQ-TREE/MrBayes substitution units).
    Pearson measures linear proportionality; Spearman measures monotonic agreement
    and is more robust to skewed branch length distributions.
    100% = perfect agreement, 0% = no correlation.
    """
    d1 = patristic_distances(tree1)
    d2 = patristic_distances(tree2)

    common_pairs = set(d1.keys()) & set(d2.keys())
    if len(common_pairs) < 2:
        na = {"similarity_pct": None, "reason": "insufficient_common_taxa"}
        return {"pearson": na, "spearman": na}

    v1 = [d1[k] for k in common_pairs]
    v2 = [d2[k] for k in common_pairs]

    # Normalize by total sum so scale differences don't affect the result
    sum1 = sum(v1)
    sum2 = sum(v2)
    if sum1 > 0:
        v1 = [x / sum1 for x in v1]
    if sum2 > 0:
        v2 = [x / sum2 for x in v2]

    pairs_used = len(common_pairs)

    def to_result(r):
        if r is None:
            return {"similarity_pct": None, "reason": "zero_variance", "pairs_used": pairs_used}
        return {
            "similarity_pct": round(r * 100.0, 2),
            "r": round(r, 4),
            "pairs_used": pairs_used,
        }

    return {
        "pearson": to_result(pearson(v1, v2)),
        "spearman": to_result(spearman(v1, v2)),
    }


def weighted_rf(tree1, tree2):
    """
    Weighted Robinson-Foulds distance on normalized branch lengths.
    Shared splits contribute |w1 - w2|; unshared splits contribute their full
    normalized length. After normalization each tree sums to 1, so max wRF = 2.
    Similarity = (1 - wRF/2) * 100%.
    """
    t1 = copy.deepcopy(tree1)
    t2 = copy.deepcopy(tree2)
    t2.migrate_taxon_namespace(t1.taxon_namespace)

    for t in [t1, t2]:
        total = sum(e.length for e in t.edges() if e.length is not None)
        if total > 0:
            for e in t.edges():
                if e.length is not None:
                    e.length /= total

    t1.encode_bipartitions()
    t2.encode_bipartitions()

    def splits_dict(tree):
        d = {}
        for edge in tree.edges():
            if edge.head_node is not None and edge.tail_node is not None:
                d[edge.bipartition.split_bitmask] = edge.length if edge.length is not None else 0.0
        return d

    s1 = splits_dict(t1)
    s2 = splits_dict(t2)

    wrf = sum(abs(s1.get(sp, 0.0) - s2.get(sp, 0.0)) for sp in set(s1) | set(s2))
    similarity = max(0.0, 1.0 - wrf / 2.0) * 100.0

    return {
        "similarity_pct": round(similarity, 2),
        "wrf_distance": round(wrf, 4),
    }


def compare_trees(trees):
    results = {}
    tree_names = list(trees.keys())

    for i in range(len(tree_names)):
        for j in range(i + 1, len(tree_names)):
            name1, name2 = tree_names[i], tree_names[j]
            t1, t2 = trees[name1], trees[name2]
            key = f"{name1}_vs_{name2}"

            print(f"Comparing {name1} vs {name2}")

            topo = None
            try:
                topo = topology_similarity(t1, t2)
            except Exception as e:
                print(f"Topology comparison error ({key}): {e}")
                topo = {"error": f"Topology comparison failed for {key}: {e}"}

            lengths = None
            try:
                lengths = branch_length_similarity(t1, t2)
            except Exception as e:
                print(f"Branch length comparison error ({key}): {e}")
                lengths = {"error": f"Branch length comparison failed for {key}: {e}"}

            wrf = None
            try:
                wrf = weighted_rf(t1, t2)
            except Exception as e:
                print(f"Weighted RF error ({key}): {e}")
                wrf = {"error": str(e)}

            results[key] = {
                "topology": topo,
                "branch_lengths": lengths,
                "weighted_rf": wrf,
            }

            if topo and "similarity_pct" in topo:
                t_pct = topo["similarity_pct"]
                p_pct = (lengths.get("pearson") or {}).get("similarity_pct") if lengths else None
                s_pct = (lengths.get("spearman") or {}).get("similarity_pct") if lengths else None
                w_pct = wrf.get("similarity_pct") if wrf else None
                print(
                    f"  topology: {t_pct}%"
                    f"  pearson: {p_pct if p_pct is not None else 'N/A'}%"
                    f"  spearman: {s_pct if s_pct is not None else 'N/A'}%"
                    f"  wRF: {w_pct if w_pct is not None else 'N/A'}%"
                )

    output_path = "/results/results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Comparison results saved to {output_path}")


if __name__ == "__main__":
    trees = load_trees()
    compare_trees(trees)
