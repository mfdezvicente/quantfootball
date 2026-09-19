# Quant Football — Model Registry

| Model ID | Name | Status | Purpose |
|---|---|---|---|
| QF-MATCH-000 | Naive Baseline | Implemented | Minimum benchmark |
| QF-MATCH-001 | Elo-Davidson | Evaluated v0.1 | Dynamic team-strength 1X2 benchmark |
| QF-MATCH-002 | Independent Poisson | Planned | Goal/score-distribution baseline |
| QF-MATCH-003 | Dixon-Coles | Planned | Low-score adjusted football model |

Production models must record training window, features, hyperparameters, timestamp, validation design, Brier score, log loss, calibration, code commit and status.


## QF-MATCH-001 — Elo-Davidson v0.1 evaluation

Initial out-of-sample check on LaLiga 2025/26 (380 matches), trained through 2025-05-31:

| Model | Log loss | Brier | Accuracy |
|---|---:|---:|---:|
| QF-MATCH-000 Naive | 1.0488 | 0.6317 | 48.95% |
| QF-MATCH-001 Elo-Davidson v0.1 | 0.9876 | 0.5853 | 50.79% |

Relative to the naive benchmark:
- Log loss: -5.84%
- Brier score: -7.35%
- Accuracy: +1.84 percentage points (+3.76% relative)

Interpretation: Elo v0.1 improves all three metrics on this holdout, but this single-season result is not yet sufficient for model selection. Hyperparameter tuning must use earlier temporal validation windows, not the 2025/26 holdout.

Known data caveat: OpenFootball is missing 10 final-round results from 2024/25 in the current source snapshot.
