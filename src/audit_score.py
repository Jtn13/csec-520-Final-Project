"""Score the audit per docs/label_audit_protocol.md."""
import json, numpy as np, pandas as pd
from statsmodels.stats.proportion import proportion_confint

key = pd.read_csv("audit/audit_sample_key.csv")
lab = pd.read_csv("audit/auditor_labels.csv", dtype=str)
m = key.merge(lab, on="audit_idx", validate="1:1")
assert len(m) == 200 and m.auditor_label.isin(["0", "1", "U"]).all()
clean = pd.read_parquet("data/clean.parquet")
w = clean.label.value_counts(normalize=True).to_dict()
out = {"n": len(m), "unclear": int((m.auditor_label == "U").sum()), "class_weights": {int(k): round(v, 4) for k, v in w.items()}}
rates, rates_u = {}, {}
for c in (0, 1):
    g = m[m.label == c]; d = g[g.auditor_label != "U"]
    err = int((d.auditor_label.astype(int) != c).sum()); n = len(d)
    lo, hi = proportion_confint(err, n, method="wilson")
    rates[c] = err / n
    errU = int(((g.auditor_label.astype(str) != str(c))).sum())
    rates_u[c] = errU / len(g)
    out[f"class{c}"] = {"n_definite": n, "n_unclear": len(g) - n, "errors": err, "rate": round(err / n, 4), "wilson95": [round(lo, 4), round(hi, 4)], "errors_if_unclear_counts": errU}
dd = m[m.auditor_label != "U"]; errs = int((dd.auditor_label.astype(int) != dd.label).sum())
lo, hi = proportion_confint(errs, len(dd), method="wilson")
E = sum(w[c] * rates[c] for c in (0, 1)); EU = sum(w[c] * rates_u[c] for c in (0, 1))
out.update(pooled_unweighted={"errors": errs, "n": len(dd), "rate": round(errs / len(dd), 4), "wilson95": [round(lo, 4), round(hi, 4)]},
           weighted_overall_E=round(E, 4), sensitivity_E_unclear_as_error=round(EU, 4))
fail = E > 0.15 or rates[0] > 0.15 or rates[1] > 0.15
out["decision"] = "FAIL" if fail else ("PASS (borderline)" if hi > 0.15 else "PASS")
rep = json.load(open("results/clean_report.json"))
out["clean_size"] = rep["clean_final"]["total"]; out["floor_10k_ok"] = rep["floor_10k_ok"]
out["error_rows"] = m[(m.auditor_label != "U") & (m.auditor_label != m.label.astype(str))][["audit_idx", "id", "label", "auditor_label"]].to_dict("records")
json.dump(out, open("results/label_audit_result.json", "w"), indent=2); print(json.dumps(out, indent=2))
