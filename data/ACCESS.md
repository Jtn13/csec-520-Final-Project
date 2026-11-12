# Data access evidence (2026-11-11)
# TODO
Raw files stay outside Git (`data/raw/` is git-ignored). Hashes below pin the exact bytes used.

## D1 - cybersectony/PhishingEmailDetectionv2.0  (primary)
- Source: #TODO
- Download/access date: #TODO.
- Schema (printed from parquet): `content: string`, `label: int64` (the dataset card says `labels`; actual column is `label`).
- Row counts: train 120,000 / validation 20,000 / test 60,000 = 200,000. Labels: 0=11,322, 1=11,322, 2=88,678, 3=88,678 (matches card: 22,644 emails, 177,356 URL-only). Null `content`: 0.
- Files / SHA-256:
  - train.parquet      e7348e0d2daaa4ac3aef88c14762db698ce66facdc35c7961474970aab4f38b5
  - validation.parquet 44b311616f0636de0151a882185b362444ae25b3c162b5c245d4a0809253075a
  - test.parquet       ddbedae0c45d52b0c950c9831a8a6b6db13de27ea1cd3e5e3c09f32e692214dc
- Used: labels 0(benign) and 1(malicious) only.

## Stress-test corpus (held-out)
# TODO

## Derived artifacts (reproducible, seed 42)
- clean.parquet 
- splits.csv (FROZEN)
