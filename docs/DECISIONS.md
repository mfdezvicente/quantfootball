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
