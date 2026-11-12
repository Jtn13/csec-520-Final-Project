# Label-audit protocol (written BEFORE the sample is drawn)

**Purpose.** D1 labels are inherited from the dataset authors and the phishing class is known to contain spam/advertising.
The proposal's fallback trigger is: *audit error > 15%  =>  switch to fallback datasets.*

**Population.** `data/clean.parquet` (deduped, labels 0/1 only, after short-row drop). 

**Claim scope (what "correct" means).** Class 1 = *malicious or unsolicited mail*: phishing, scams/advance-fee fraud, malware lures,
and unsolicited bulk/commercial/adult spam. Class 0 = ordinary legitimate correspondence: personal, workplace,
mailing-list/newsletter content, news digests. A label is an **error** only if the auditor confidently assigns the other class.

**Sample.** n = 200, stratified by dataset label (100 class-0, 100 class-1), simple random draw without replacement,
**at most one email per MinHash cluster**, fixed seed 42. The auditor sees only the normalized text (first 600 chars)
and a random id; the dataset label is hidden until all labels are recorded.

**Auditor labels.** `1` (malicious/unsolicited), `0` (legitimate), `U` (unclear: truncated, garbled, or cannot decide).

**Estimates.**
- Class error rate e0 = (#audit says 1 among dataset-0) / (#definite in class 0); e1 likewise.
- **Overall error rate** E = w0*e0 + w1*e1, with w = class shares of the clean population (prevalence-weighted).
- Wilson 95% CI reported for e0, e1 and the unweighted pooled rate. 
- Sensitivity rate E_U treats every `U` as an error.

**Decision rule (fixed in advance).**
1. **FAIL** (stop, switch to fallback datasets) if E > 15%, or either class error rate e0/e1 > 15%.
2. Else **PASS**. If the upper Wilson bound of the pooled rate is > 15% the result is reported as *PASS (borderline)* and flagged for a second human auditor.
3. Independent gate: clean size >= 10,000 emails (checked from `results/clean_report.json`).

**Power note.** With n=200 a true 15% error rate is flagged with ~45% probability by the point-estimate rule, a true 10% rate with ~1%, and a true 20% rate with
~96%; a ±5pt CI half-width is the practical resolution. The sample sheet (blind) is saved so teammates can re-label it.

