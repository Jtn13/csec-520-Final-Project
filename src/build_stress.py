"""Held-out stress corpus in the SAME schema as clean.parquet.

Positives: Nazario phishing-campaign emails (label 1).  Negatives: CEAS-08 legitimate emails (label 0).
Source files are from the GitHub mirror rokibulroni/Phishing-Email-Dataset (Champa et al. curated corpora).
Steps: same normalization -> drop empty/short -> drop any row exactly/near-duplicate (Jaccard>=0.8) of D1 clean
-> exact dedup -> MinHash clusters -> cluster-grouped 50/50 split stratified by class (seed 42)
-> Part A = as-is; Part B = phishing subsampled to PREVALENCE (all Part-B legit kept).
"""
import json, random
import numpy as np, pandas as pd
from datasketch import MinHashLSH
from src.normalize import normalize_full
from src.build_clean import minhash, sha256, cluster_minhash, NUM_PERM, JACCARD, SEED

PREVALENCE = 0.01
rep = {"seed": SEED, "prevalence_part_B": PREVALENCE}

def load(fn, label, tag):
    s = pd.read_csv(f"data/raw/stress/{fn}")
    s = s[s.label == label] if "label" in s else s
    raw = s.subject.fillna("").astype(str) + "\n" + s.body.fillna("").astype(str)
    f = pd.DataFrame([normalize_full(x) for x in raw])
    f["label"] = label; f["source"] = tag; f["orig_row"] = s.index.values
    return f

d = pd.concat([load("Nazario.csv", 1, "nazario"), load("CEAS_08.csv", 0, "ceas08")], ignore_index=True)
rep["raw_rows"] = d.source.value_counts().to_dict()
rep["dropped_empty_or_short"] = d[d.status != "ok"].source.value_counts().to_dict()
d = d[d.status == "ok"].drop(columns="status").reset_index(drop=True)
d["sha256"] = d.text.map(sha256)

# leakage vs D1 (exact + near)
d1 = pd.read_parquet("data/clean.parquet", columns=["text", "sha256"])
lsh = MinHashLSH(threshold=JACCARD, num_perm=NUM_PERM)
for i, t in enumerate(d1.text): lsh.insert(str(i), minhash(t))
ex = d.sha256.isin(set(d1.sha256))
near = pd.Series([bool(lsh.query(minhash(t))) for t in d.text], index=d.index)
leak = ex | near
rep["dropped_overlap_with_D1"] = {"exact": d[ex].source.value_counts().to_dict(), "near_or_exact": d[leak].source.value_counts().to_dict()}
d = d[~leak]
n0 = len(d); d = d.drop_duplicates("sha256").reset_index(drop=True); rep["exact_dups_removed_within_stress"] = int(n0 - len(d))
d["cluster_id"] = pd.factorize(cluster_minhash(d.text.tolist()))[0]
nl = d.groupby("cluster_id").label.nunique(); mixed = set(nl[nl > 1].index)
rep["mixed_label_clusters_dropped_rows"] = int(d.cluster_id.isin(mixed).sum()); d = d[~d.cluster_id.isin(mixed)].reset_index(drop=True)
d.insert(0, "id", [f"st_{i:06d}" for i in range(len(d))])
rep["usable_rows"] = {"total": int(len(d)), **{int(k): int(v) for k, v in d.label.value_counts().items()}}

# cluster-grouped 50/50 stratified split (greedy by deficit)
rng = random.Random(SEED)
cl = d.groupby("cluster_id").agg(label=("label", "first"), n=("id", "size")).reset_index().to_dict("records"); rng.shuffle(cl); cl.sort(key=lambda r: -r["n"])
tot = d.label.value_counts().to_dict(); got = {(p, c): 0 for p in "AB" for c in (0, 1)}; asg = {}
for r in cl:
    c = r["label"]; p = max("AB", key=lambda p: (0.5 * tot[c] - got[(p, c)]))
    asg[r["cluster_id"]] = p; got[(p, c)] += r["n"]
d["part"] = d.cluster_id.map(asg)
assert d.groupby("cluster_id").part.nunique().max() == 1

# Part B scaled-down prevalence
B = d[d.part == "B"]; nleg = int((B.label == 0).sum()); want = int(round(PREVALENCE / (1 - PREVALENCE) * nleg))
bp = B[B.label == 1]; keep_ids = set(bp.sample(n=min(want, len(bp)), random_state=SEED).id)
d["b_scaled_keep"] = ((d.part == "B") & ((d.label == 0) | d.id.isin(keep_ids)))
d.loc[d.part == "A", "b_scaled_keep"] = False
cols = ["id", "text", "label", "cluster_id", "n_urls", "caps_ratio", "raw_len", "sha256", "source", "part", "b_scaled_keep"]
d = d[cols]
d.to_parquet("data/stress_clean.parquet", index=False)
A = d[d.part == "A"]; Bs = d[d.b_scaled_keep]
A.drop(columns="b_scaled_keep").to_parquet("data/stress_A.parquet", index=False); Bs.drop(columns="b_scaled_keep").to_parquet("data/stress_B_scaled.parquet", index=False)
d[["id", "label", "cluster_id", "part", "b_scaled_keep"]].to_csv("data/stress_split.csv", index=False)
rep["partA"] = {"n": len(A), "phish": int(A.label.sum()), "legit": int((A.label == 0).sum()), "prevalence": round(float(A.label.mean()), 4)}
rep["partB_full_before_scaling"] = {"n": len(B), "phish": int(B.label.sum()), "legit": nleg}
rep["partB_scaled"] = {"n": len(Bs), "phish": int(Bs.label.sum()), "legit": int((Bs.label == 0).sum()), "prevalence": round(float(Bs.label.mean()), 5)}
json.dump(rep, open("results/stress_report.json", "w"), indent=2, default=int); print(json.dumps(rep, indent=2, default=int))
