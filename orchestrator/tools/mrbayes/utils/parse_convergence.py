import glob
import json
import math
import sys


def read_p_file(filepath, burnin_frac=0.25):
    samples = []
    header = None
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("["):
                continue
            parts = line.split("\t")
            if header is None:
                header = parts
                continue
            try:
                samples.append([float(x) for x in parts])
            except ValueError:
                continue

    if not samples or header is None:
        return {}

    burnin = int(len(samples) * burnin_frac)
    samples = samples[burnin:]

    result = {}
    for i, name in enumerate(header):
        if name == "Gen":
            continue
        result[name] = [row[i] for row in samples]
    return result


def compute_psrf(chains):
    m = len(chains)
    n = min(len(c) for c in chains)
    if n < 2 or m < 2:
        return None

    chains = [c[:n] for c in chains]
    chain_means = [sum(c) / n for c in chains]
    overall_mean = sum(chain_means) / m

    B = n / (m - 1) * sum((mu - overall_mean) ** 2 for mu in chain_means)
    within_vars = [
        sum((x - mu) ** 2 for x in c) / (n - 1)
        for c, mu in zip(chains, chain_means)
    ]
    W = sum(within_vars) / m

    if W == 0:
        return None

    var_hat = (n - 1) / n * W + B / n
    return round(math.sqrt(var_hat / W), 4)


def main():
    p_files = sorted(glob.glob("output.run*.p"))
    if len(p_files) < 2:
        print(f"Need at least 2 .p files, found: {p_files}")
        sys.exit(1)

    chains_data = [read_p_file(f) for f in p_files]
    params = list(chains_data[0].keys())

    THRESHOLD = 1.01
    results = {}
    all_converged = True

    for param in params:
        chains = [cd[param] for cd in chains_data if param in cd]
        if len(chains) < 2:
            continue
        psrf = compute_psrf(chains)
        if psrf is not None:
            converged = psrf <= THRESHOLD
            if not converged:
                all_converged = False
            results[param] = {"psrf": psrf, "converged": converged}

    output = {
        "converged": all_converged,
        "threshold": THRESHOLD,
        "n_runs": len(p_files),
        "parameters": results,
    }

    with open("/results/convergence.json", "w") as f:
        json.dump(output, f, indent=2)

    status = "CONVERGED" if all_converged else "NOT CONVERGED"
    print(f"Convergence check: {status} (PSRF threshold <= {THRESHOLD})")
    for param, data in results.items():
        mark = "✓" if data["converged"] else "✗"
        print(f"  {param}: PSRF={data['psrf']} {mark}")


if __name__ == "__main__":
    main()
