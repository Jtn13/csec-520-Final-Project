"""Load the frozen clean data + split IDs. Single entry point so every model sees identical splits."""
import hashlib
import pandas as pd

CLEAN, SPLITS = "data/clean.parquet", "data/splits.csv"
FROZEN_SPLITS_SHA256 = "bc079ef5d4e0325649ee5e75c4a5a83e4397771ce7d58659ebacdde2c0c62eea"


def load_splits(verify=True) -> dict[str, pd.DataFrame]:
    if verify:
        h = hashlib.sha256(open(SPLITS, "rb").read()).hexdigest()
        assert h == FROZEN_SPLITS_SHA256, f"splits.csv changed (sha256 {h}); splits are frozen"
    d = pd.read_parquet(CLEAN)
    s = pd.read_csv(SPLITS)[["id", "split"]]
    d = d.merge(s, on="id", validate="1:1")
    return {k: g.reset_index(drop=True) for k, g in d.groupby("split")}  # keys: train / val / test
