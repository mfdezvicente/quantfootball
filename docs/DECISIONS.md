# Quant Football — Decision Log

## DEC-001 — Initial competition
**Date:** 2026-09-19  
Quant Football V0 focuses only on LaLiga.

## DEC-002 — Source of truth
**Date:** 2026-09-19  
GitHub is the technical source of truth.

## DEC-003 — Cost constraint
**Date:** 2026-09-19  
Initial development targets approximately €0 monthly data/infrastructure cost.

## DEC-004 — Production code policy
**Date:** 2026-09-19  
Notebooks are for exploration; reusable logic belongs in `src/quantfootball/`.

## DEC-005 — Validation policy
**Date:** 2026-09-19  
All evaluation must preserve time order and prevent future leakage.

## DEC-006 — Prediction integrity
**Date:** 2026-09-19  
Forward predictions will be persisted with timestamp and model version before outcomes are known.

## DEC-007 — Quiniela as first product
**Date:** 2026-09-24
Default maximum budget: EUR 5 per contest. Optimize probability of at least one
14-correct column first; introduce expected return only with reliable selection
and prize data. Compare complete Cartesian systems with unrestricted distinct
columns. Both are conditional on estimated probabilities and independence.

## DEC-008 — Common submission cutoff
**Date:** 2026-09-24
All forecasts for a coupon use one frozen model state. Until result-availability
timestamps exist, exclude the entire submission day from historical training.
Reject unknown teams explicitly. Pleno al 15 modeling and official coupon
ingestion remain required before presenting a complete real betting ticket.

## DEC-009 — Advanced experimental forecaster
**Date:** 2026-09-24
Use a regularized time-decayed Poisson goal model with a second-stage Dixon-Coles
correction, blended with Elo. Select configuration on 2022-24 only; report final
2024-26 results without retuning. Default 1X2 weights are 50/50 with temperature
0.9. Pleno categories use the standalone goal model. Weekly historical evaluation
does not establish official-coupon coverage or profitable returns.

## DEC-010 — Division models and uncertainty
**Date:** 2026-09-25
Fit and select parameters separately for Primera and Segunda. Use week-block
multiplier bootstrap for conditional parameter sensitivity; do not interpret
outcome entropy as estimator variance. Conservative systems optimize a lower
coverage percentile over candidate sets and are explicitly heuristic.

## DEC-011 — ROI accounting and retrospective status
**Date:** 2026-09-25
Published prize tables support realized gross ROI without public pick shares.
Expected-value optimization still needs reliable crowd/prize information. Report
all strategies and excluded contests; never select a strategy using test payouts.
The first seven-coupon diagnostic has negative ROI and cannot establish future
profitability. 2024-26 is now retrospective research data, not a new blind test.
