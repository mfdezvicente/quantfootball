# Quant Football — Model Registry

| Model ID | Name | Status | Purpose |
|---|---|---|---|
| QF-MATCH-000 | Naive Baseline | Implemented | Minimum benchmark |
| QF-MATCH-001 | Elo-Davidson | Evaluated on 2024-26 | Dynamic team-strength 1X2 benchmark |
| QF-MATCH-002 | Regularized time-decayed Poisson | Implemented and evaluated | Goal baseline (DC correction disabled) |
| QF-MATCH-003 | Two-stage Dixon-Coles | Implemented and evaluated | Low-score correction and Pleno goal categories |
| QF-MATCH-004 | Elo + Dixon-Coles with temperature scaling | Validation-selected; evaluated on 750 held-out matches | Default experimental Quiniela forecaster |
| QF-MATCH-005 | Division-specific ensemble with week-block bootstrap | 1,684 retrospective diagnostic matches; profitability unproven | Mixed Primera/Segunda forecast and uncertainty |
| QF-MATCH-006 | Common-scale transfer Elo mixture | Experimental; validation picks 25% weight in Segunda; diagnostic interval crosses zero | Preserve team strength on promotion/relegation |
| QF-MATCH-007 | Regularized form-feature mixture | Experimental; 52 predictors, 25% logistic mixture; small log-loss improvements with intervals crossing zero | Form, venue, strength and league-match history |
| QF-MATCH-008 | Expanded form-feature mixture | Experimental; 116 features; validation chooses 25% boosting in Primera, retains QF-MATCH-007 in Segunda | Goal variability, scoring patterns, trends and recent league activity |
| QF-MATCH-009 | Regularized small neural networks | All stable fits converged; not selected by chronological validation | Nonlinear challenger, kept as a reproducible comparison |
| QF-MATCH-010 | Women's separate Dixon-Coles | Selected on 2022–24; 480 later diagnostic matches; no official mixed-coupon profitability evidence | Liga F goals and 1X2, without sharing male team strengths |
| QF-MATCH-011 | Monthly dynamic attack/defence with bounded joint low-score correction | 1,287 converged weekly fits; selected as 25% Liga F mixture; male incumbents retained | Time-varying penalized goal states; pair-scaled correction, not original constant-rho DC |
| QF-MATCH-012 | Temporal regularized multiclass calibration | Temperature selected for Liga F; identity for men; calibration alone does not improve later diagnostics | Post-pool probability calibration fitted only on earlier forecast labels |

Current results and small official-coupon return sample: [SPAIN_MODEL.md](SPAIN_MODEL.md).
Expanded Sunday archive and transfer experiment: [RESEARCH_EXPANSION.md](RESEARCH_EXPANSION.md).
Form features and exact portfolio hit distributions: [FORM_AND_RISK.md](FORM_AND_RISK.md).
Latest data, model comparisons and exact threshold allocation: [RESEARCH_20261002.md](RESEARCH_20261002.md).
The earlier 2024-26 data have already been inspected and cannot be treated as a new untouched holdout.
Dynamic research, calibration and prospective protocol: [DYNAMIC_MODEL.md](DYNAMIC_MODEL.md).

Results, methodology and limitations: [ADVANCED_MODEL.md](ADVANCED_MODEL.md).

Production models must record training window, features, hyperparameters, timestamp, validation design, Brier score, log loss, calibration, code commit and status.
