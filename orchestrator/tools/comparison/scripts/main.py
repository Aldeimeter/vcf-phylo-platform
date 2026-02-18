import dendropy
import os
import json


def rf_dist(tree1, tree2):
    tree2.migrate_taxon_namespace(tree1.taxon_namespace)

    rf_distance = dendropy.calculate.treecompare.symmetric_difference(tree1, tree2)
    num_taxa = len(tree1.taxon_namespace)
    max_rf = 2 * (num_taxa - 3) if num_taxa >= 3 else 0

    return {
        "raw_rf": rf_distance,
        "normalized_rf": rf_distance / max_rf if max_rf > 0 else 0,
    }


def wrf_dist(tree1, tree2):
    tree2.migrate_taxon_namespace(tree1.taxon_namespace)

    wrf_distance = dendropy.calculate.treecompare.weighted_robinson_foulds_distance(
        tree1, tree2
    )

    return {"wrf": wrf_distance}


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
                trees[name] = dendropy.Tree.get(path=path, schema="newick")
                print(f"Loaded {name} tree from {path}")
            except Exception as e:
                print(f"Error loading {name} tree: {e}")

    return trees


def compare_topology(trees):
    print("Comparing topologies")

    if len(trees) < 2:
        print(
            f"Error: Need at least 2 trees for comparison. Found: {list(trees.keys())}"
        )
        return

    results = {}

    tree_names = list(trees.keys())

    for i in range(len(tree_names)):
        for j in range(i + 1, len(tree_names)):
            tree1_name, tree2_name = tree_names[i], tree_names[j]
            tree1, tree2 = trees[tree1_name], trees[tree2_name]

            print(f"Comparing {tree1_name} vs {tree2_name}")

            try:
                rf_result = rf_dist(tree1, tree2)

                comparison_key = f"{tree1_name}_vs_{tree2_name}"
                results[comparison_key] = {"rf": rf_result}
            except Exception as e:
                print(f"Error comparing {tree1_name} vs {tree2_name}: {e}")
                results[f"{tree1_name}_vs_{tree2_name}"] = {"error": str(e)}
    return results


def compare_length(trees):
    print("Comparing branch lengths for compatible units")

    results = {}
    tree_names = list(trees.keys())

    for i in range(len(tree_names)):
        for j in range(i + 1, len(tree_names)):
            tree1_name, tree2_name = tree_names[i], tree_names[j]
            tree1, tree2 = trees[tree1_name], trees[tree2_name]

            comparison_key = f"{tree1_name}_vs_{tree2_name}"

            # Check if comparison uses compatible units
            compatible = {tree1_name, tree2_name}.issubset({"iqtree", "mrbayes"})

            if compatible:
                try:
                    wrf_result = wrf_dist(tree1, tree2)
                    results[comparison_key] = {
                        **wrf_result,
                        "comparison_type": "compatible_units",
                    }
                except Exception as e:
                    results[comparison_key] = {
                        "error": str(e),
                        "comparison_type": "compatible_units",
                    }
            else:
                # For incompatible units (involving fastreer)
                results[comparison_key] = {
                    "comparison_type": "topology_only",
                    "note": "Branch lengths incompatible - skipping length-sensitive metrics",
                }

    return results


def compare_trees(trees):
    results_topology = compare_topology(trees)
    results_length = compare_length(trees)
    results = results_topology
    for key in results_topology.keys():
        results[key] = {**results_topology[key], **results_length[key]}
    output_path = "/results/results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Comparison results saved to {output_path}")


if __name__ == "__main__":
    trees = load_trees()
    compare_trees(trees)
