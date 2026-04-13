# Comparison Metric Ideas

## Topology

- **Quartet distance** — counts how many sets of 4 taxa have different topology between trees. More fine-grained than RF, which counts bipartitions. Available in dendropy.
- **Path difference** — compares the number of edges on the path between every pair of taxa (ignores branch lengths). Captures topology without needing branch lengths at all.

## Branch lengths

- **Mantel test** — statistical extension of Pearson: permutes the distance matrix to get a p-value for whether the correlation is significant. Useful for reporting statistical significance rather than just a number.
- **Cophenetic correlation (Spearman)** — same as current Pearson but using rank correlation, making it more robust to outlier branches (one very long branch won't skew it).

## Combined topology + branch lengths

- **Geodesic distance (BHV)** — measures the shortest path between two trees in "tree space" (Billera-Holmes-Vogtmann space), accounting for both topology and branch lengths simultaneously. Theoretically elegant but computationally expensive and not in dendropy — requires a separate library (`treescape` or `phylodist`).
- **Weighted RF (wRF)** — like RF but weights each bipartition by its branch length difference. A middle ground between pure topology RF and full KF. Not in dendropy built-in but ~10 lines to implement on top of existing code.

## Most practical next addition

**Spearman instead of / alongside Pearson** — trivial to add (just rank the vectors before correlating), more robust, and useful to report in a thesis because it's a well-known robustness check. If Pearson and Spearman agree, the result is not driven by outlier branches.
