"""Cluster-based, class-stratified 70/15/15 split with a fixed seed -> data/splits.csv (frozen IDs).

Greedy: shuffle clusters (seed), place larger clusters first, each into the split with the largest
remaining deficit for that cluster's class (clusters are label-pure; verified in build_clean report).
"""
import hashlib, json, random
import pandas as pd

SEED = 42
TARGET = {"train": 0.70, "val": 0.15, "test": 0.15}
d = pd.read_parquet("data/clean.parquet", columns=["id", "label", "cluster_id", "sha256"])
cl = d.groupby("cluster_id").agg(label=("label", "first"), nl=("label", "nunique"), n=("id", "size")).reset_index()
assert (cl.nl == 1).all(), "mixed-label cluster"
rng = random.Random(SEED)
order = cl.to_dict("records"); rng.shuffle(order); order.sort(key=lambda r: -r["n"])  # stable: ties keep shuffled order
tot = d.label.value_counts().to_dict()
got = {(s, c): 0 for s in TARGET for c in (0, 1)}
assign = {}
for r in order:
    c = r["label"]
    # deficit = target count - current count for this class; pick split with largest relative deficit
    best = max(TARGET, key=lambda s: (TARGET[s] * tot[c] - got[(s, c)]) / (TARGET[s] * tot[c]))
    assign[r["cluster_id"]] = best; got[(best, c)] += r["n"]
d["split"] = d.cluster_id.map(assign)
d[["id", "cluster_id", "label", "split"]].sort_values("id").to_csv("data/splits.csv", index=False)
# ---- leakage checks
assert d.groupby("cluster_id").split.nunique().max() == 1, "cluster spans splits"
assert d.groupby("sha256").split.nunique().max() == 1, "exact dup spans splits"
summ = d.groupby(["split", "label"]).size().unstack().assign(total=lambda x: x.sum(1))
summ["frac"] = (summ.total / summ.total.sum()).round(4); summ["phish_share"] = (summ[1] / summ.total).round(4)
print(summ)
h = hashlib.sha256(open("data/splits.csv", "rb").read()).hexdigest()
json.dump({"seed": SEED, "sha256_splits_csv": h, "rows": len(d), "counts": summ.reset_index().to_dict("records"),
           "leakage_checks": {"cluster_in_multiple_splits": 0, "exact_hash_in_multiple_splits": 0}}, open("results/splits_report.json", "w"), indent=2, default=int)
print("splits.csv sha256", h)
