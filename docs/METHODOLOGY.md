# Quant Football — Methodology Principles

1. **Temporal integrity:** predictions at time t use only information available by t.
2. **Baselines first:** advanced models must beat simple benchmarks.
3. **Probability quality:** prioritize Brier score, log loss and calibration over raw accuracy.
4. **Walk-forward evaluation:** evaluation should mimic live forecasting.
5. **Market benchmark:** remove bookmaker margin before using odds as fair probabilities.
6. **Reproducibility:** metrics must map to data version, model version and code commit.
7. **Uncertainty:** point estimates should not be presented as certainty.
