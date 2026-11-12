# Data access evidence (2026-11-11)

Raw files stay outside Git (`data/raw/` is git-ignored). Hashes below pin the exact bytes used.

## D1 - cybersectony/PhishingEmailDetectionv2.0  (primary)
- Source
- Download/access date: 
- Schema (printed from parquet): `content: string`, `label: int64` (the dataset card says `labels`; actual column is `label`).
- Row counts: train 120,000 / validation 20,000 / test 60,000 = 200,000. Labels: 0=11,322, 1=11,322, 2=88,678, 3=88,678 (matches card: 22,644 emails, 177,356 URL-only). Null `content`: 0.
- Files / SHA-256:
  - train.parquet      e7348e0d2daaa4ac3aef88c14762db698ce66facdc35c7961474970aab4f38b5
  - validation.parquet 44b311616f0636de0151a882185b362444ae25b3c162b5c245d4a0809253075a
  - test.parquet       ddbedae0c45d52b0c950c9831a8a6b6db13de27ea1cd3e5e3c09f32e692214dc
- Used: labels 0 and 1 only.

## D2 - zefang-liu/phishing-email-dataset  (NOT acquired - only if needed)
Instruction: use only if necessary. D1 passed the audit and size floor, so it was not downloaded.

## Stress-test corpus (held-out)
**Original source:** "Phishing Email Curated Datasets", A. I. Champa (with M. F. Rabbi, M. F. Zibran), Zenodo record 8339691, DOI 10.5281/zenodo.8339691, v1, published 2023-09-13 (last modified 2024-09-25), **licence CC BY 4.0** (record page). 11 CSV files, 449.3 MB. Cite the two Champa et al. 2024 papers named on the record. The record page gives no per-file row counts or provenance, so the per-file stats below are measured by us.
**Known data quirks:** `date` column is unreliable (Nazario 405/1,565 parseable; CEAS/Nigerian/SpamAssassin contain years 1980-2100, 0102) so no temporal claims; `subject` null in a few rows (Nazario 4, CEAS 28, Nigerian 39, SpamAssassin 16); schema `sender,receiver,date,subject,body,urls,label`; 0 exact-duplicate bodies within any file.
**Per-file stats (full files; full machine-readable copy in `results/stress_candidates_probe.json`):**
| file | md5 matches Zenodo | raw rows | raw labels | usable after normalize/drop-short | median body chars | near/exact overlap with D1 clean | used? |
|---|---|---|---|---|---|---|---|
| Nazario.csv | 
| CEAS_08.csv |
| Nigerian_Fraud.csv | 
| SpamAssasin.csv | 
**Used in the stress set** (`results/stress_report.json`): after normalize, drop-short, D1-overlap filter (0 removed) and within-stress exact dedup: 18,580 rows = 1,524 phishing + 17,056 legit; Part A 9,290 (762 phish / 8,528 legit); Part B scaled 8,614 (86 phish / 8,528 legit, 1.0%).

## Derived artefacts (reproducible, seed 42)
- clean.parquet 
- splits.csv (FROZEN)
- stress_A.parquet 
- stress_B_scaled.parquet 
- stress_clean.parquet 
