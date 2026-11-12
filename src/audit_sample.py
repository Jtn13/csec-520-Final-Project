"""Draw the blind label-audit sample defined in docs/label_audit_protocol.md."""
import numpy as np, pandas as pd

SEED, PER_CLASS = 42, 100
d = pd.read_parquet("data/clean.parquet")
rng = np.random.default_rng(SEED)
picked = []
for lab in (0, 1):
    g = d[d.label == lab]
    g = g.loc[rng.permutation(g.index)].drop_duplicates("cluster_id")  # <=1 per cluster, random rep
    picked.append(g.head(PER_CLASS))
s = pd.concat(picked)
s = s.loc[rng.permutation(s.index)].reset_index(drop=True)
s["audit_idx"] = [f"A{i:03d}" for i in range(len(s))]
s[["audit_idx", "id", "label", "text"]].to_csv("audit/audit_sample_key.csv", index=False)           # has dataset label
s[["audit_idx", "text"]].assign(text=s.text.str[:600]).to_csv("audit/audit_sample_blind.csv", index=False)  # auditor view
print(len(s), s.label.value_counts().to_dict())
