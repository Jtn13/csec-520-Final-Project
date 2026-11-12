"""Exact dedup -> MinHash near-duplicate clusters -> merge (labels 0/1) -> 50k stratified cap -> data/clean.parquet.

Usage: python -m src.build_clean --raw data/raw/d1 --out data/clean.parquet --report results/clean_report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
from datasketch import MinHash, MinHashLSH

from src.normalize import normalize_full

SEED = 42
CAP = 50_000
JACCARD = 0.8
NUM_PERM = 128
SHINGLE = 3  # word 3-grams


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def minhash(text: str) -> MinHash:
    toks = text.split()
    m = MinHash(num_perm=NUM_PERM, seed=SEED)
    if len(toks) < SHINGLE:
        m.update(" ".join(toks).encode())
        return m
    for i in range(len(toks) - SHINGLE + 1):
        m.update(" ".join(toks[i : i + SHINGLE]).encode())
    return m


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def cluster_minhash(texts: list[str]) -> np.ndarray:
    lsh = MinHashLSH(threshold=JACCARD, num_perm=NUM_PERM)
    mhs = [minhash(t) for t in texts]
    uf = UF(len(texts))
    for i, m in enumerate(mhs):
        for j in lsh.query(m):  # candidates already inserted
            uf.union(i, int(j))
        lsh.insert(str(i), m)
    roots = np.array([uf.find(i) for i in range(len(texts))])
    return roots


def stratified_cluster_cap(df: pd.DataFrame, cap: int, seed: int) -> pd.DataFrame:
    """If len(df) > cap, keep whole clusters so both classes keep their original proportion."""
    if len(df) <= cap:
        return df
    rng = random.Random(seed)
    keep = []
    for lab, g in df.groupby("label"):
        target = round(cap * len(g) / len(df))
        cl = list(g.groupby("cluster_id").size().items())
        rng.shuffle(cl)
        tot = 0
        for cid, n in cl:
            if tot + n <= target:
                keep.append(cid)
                tot += n
    return df[df.cluster_id.isin(set(keep))]


def main(raw, out, report):
    raw = Path(raw)
    rep = {"seed": SEED, "jaccard": JACCARD, "num_perm": NUM_PERM, "shingle_words": SHINGLE, "cap": CAP}
    parts = []
    for split in ("train", "validation", "test"):
        d = pd.read_parquet(raw / f"{split}.parquet")
        d["orig_split"] = split
        d["orig_row"] = np.arange(len(d))
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    rep["rows_all_labels"] = int(len(d))
    rep["rows_by_label_all"] = {int(k): int(v) for k, v in d.label.value_counts().sort_index().items()}
    d = d[d.label.isin([0, 1])].reset_index(drop=True)  # drop URL-only rows (labels 2,3)
    rep["rows_labels_0_1"] = {"total": int(len(d)), **{int(k): int(v) for k, v in d.label.value_counts().sort_index().items()}}

    feats = pd.DataFrame([normalize_full(t) for t in d.content])
    d = pd.concat([d.drop(columns="content"), feats], axis=1)
    rep["status_counts"] = d.status.value_counts().to_dict()
    rep["dropped_empty_or_short_by_label"] = {s: {int(k): int(v) for k, v in g.label.value_counts().items()} for s, g in d[d.status != "ok"].groupby("status")}
    d = d[d.status == "ok"].drop(columns="status").reset_index(drop=True)
    rep["after_drop_short"] = {"total": int(len(d)), **{int(k): int(v) for k, v in d.label.value_counts().sort_index().items()}}

    # ---- exact dedup on SHA-256 of normalized text
    d["sha256"] = d.text.map(sha256)
    nl = d.groupby("sha256").label.nunique()
    conflict = set(nl[nl > 1].index)
    rep["exact_dup_groups_with_conflicting_labels"] = len(conflict)
    rep["rows_dropped_conflicting_label_dups"] = int(d.sha256.isin(conflict).sum())
    d = d[~d.sha256.isin(conflict)]
    n0 = len(d)
    d = d.drop_duplicates("sha256", keep="first").reset_index(drop=True)
    rep["exact_dups_removed"] = int(n0 - len(d))
    rep["after_exact_dedup"] = {"total": int(len(d)), **{int(k): int(v) for k, v in d.label.value_counts().sort_index().items()}}

    # ---- MinHash near-dup clusters (kept, not dropped; used as split groups)
    roots = cluster_minhash(d.text.tolist())
    d["cluster_id"] = pd.factorize(roots)[0]
    cs = d.groupby("cluster_id").agg(n=("label", "size"), nl=("label", "nunique"))
    rep["minhash"] = {
        "clusters": int(len(cs)),
        "singletons": int((cs.n == 1).sum()),
        "multi_row_clusters": int((cs.n > 1).sum()),
        "rows_in_multi_row_clusters": int(cs[cs.n > 1].n.sum()),
        "largest_cluster": int(cs.n.max()),
        "mixed_label_clusters": int((cs.nl > 1).sum()),
        "rows_in_mixed_label_clusters": int(cs[cs.nl > 1].n.sum()),
    }

    # ---- merge (labels 0/1 only already) + 50k stratified cap
    n_pre = len(d)
    d = stratified_cluster_cap(d, CAP, SEED)
    rep["cap_applied"] = bool(len(d) < n_pre)
    d = d.reset_index(drop=True)
    d.insert(0, "id", [f"d1_{i:06d}" for i in range(len(d))])
    d = d[["id", "text", "label", "cluster_id", "n_urls", "caps_ratio", "raw_len", "sha256", "orig_split", "orig_row"]]
    rep["clean_final"] = {"total": int(len(d)), **{int(k): int(v) for k, v in d.label.value_counts().sort_index().items()}}
    rep["floor_10k_ok"] = bool(len(d) >= 10_000)
    rep["token_len_median"] = float(d.text.str.split().map(len).median())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(out, index=False)
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    Path(report).write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/d1")
    ap.add_argument("--out", default="data/clean.parquet")
    ap.add_argument("--report", default="results/clean_report.json")
    a = ap.parse_args()
    main(a.raw, a.out, a.report)
