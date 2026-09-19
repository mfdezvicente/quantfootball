# Quant Football

**Quant Football** is a forward-looking quantitative football platform focused on turning football data into expectations, valuations and market intelligence.

> **Core question:** What happens next?

## Initial scope

Quant Football V0 starts with a rigorous LaLiga match forecasting engine:

1. Reproducible historical data pipeline.
2. Baseline models: naive, Elo, Poisson and Dixon-Coles.
3. Proper temporal validation and calibration.
4. Immutable prediction tracking.
5. Later: market comparison, player intelligence, Fantasy and valuation.

## Principles

- No temporal leakage.
- Baselines before complexity.
- Probabilities must be calibrated and evaluated.
- Notebooks are for exploration; production logic belongs in `src/`.
- Public predictions are stored before outcomes are known.
- Features are added only when they answer a real user question.

Current milestone: **QF-M0 — Foundations**.
