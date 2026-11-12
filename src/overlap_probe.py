"""Probe: overlap (exact + MinHash>=0.8) between each candidate stress corpus and D1 clean."""
import sys, pandas as pd
from datasketch import MinHashLSH
from src.normalize import normalize_full
from src.build_clean import minhash, sha256, NUM_PERM, JACCARD

d1 = pd.read_parquet("data/clean.parquet", columns=["text", "sha256", "label"])
lsh = MinHashLSH(threshold=JACCARD, num_perm=NUM_PERM)
for i, t in enumerate(d1.text): lsh.insert(str(i), minhash(t))
h1 = set(d1.sha256)
for name, fn, n in [("Nazario", "Nazario.csv", None), ("Nigerian_Fraud", "Nigerian_Fraud.csv", None), ("SpamAssasin", "SpamAssasin.csv", None), ("CEAS_08", "CEAS_08.csv", 3000)]:
    s = pd.read_csv(f"data/raw/stress/{fn}")
    if n: s = s.sample(n, random_state=0)
    s["raw"] = (s.subject.fillna("") + "\n" + s.body.fillna("")) if "subject" in s else s.body
    f = pd.DataFrame([normalize_full(x) for x in s.raw]); f["label"] = s.label.values
    f = f[f.status == "ok"]
    ex = f.text.map(sha256).isin(h1)
    near = [bool(lsh.query(minhash(t))) for t in f.text]
    f["ex"], f["near"] = ex.values, near
    print(name, "ok rows", len(f), "| exact-in-D1", int(f.ex.sum()), "| near(>=.8)-in-D1", int(f.near.sum()), "| by label near:", f.groupby("label").near.sum().to_dict(), "| n by label:", f.label.value_counts().to_dict(), flush=True)
