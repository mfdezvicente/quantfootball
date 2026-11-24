"""Compare six-column 1X2 portfolios at identical cost on frozen probabilities."""

import argparse
import json
from datetime import UTC, datetime
from functools import lru_cache
from itertools import combinations, product
from pathlib import Path
from statistics import mean

import numpy as np

from quantfootball.quiniela.coverage import (
    SIGNS,
    best_columns,
    threshold_system_frontier,
    validate_probabilities,
)
from quantfootball.quiniela.registry import digest, write_new
from quantfootball.quiniela.risk import portfolio_risk
from quantfootball.quiniela.settlement import settle_columns

COLUMN_COUNT = 6
PROBS = ("p_home", "p_draw", "p_away")
THRESHOLDS = (10, 11, 14)
POOL_TOP = 128


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def hamming_offsets(matches, radius):
    rows = [np.zeros(matches, dtype=np.int8)]
    for count in range(1, radius + 1):
        for positions in combinations(range(matches), count):
            for shifts in product((1, 2), repeat=count):
                row = np.zeros(matches, dtype=np.int8)
                row[list(positions)] = shifts
                rows.append(row)
    return np.stack(rows)


def hamming_codes(picks, radius):
    """Encode each distinct outcome within radius of each column in base 3."""
    matches = picks.shape[1]
    powers = 3 ** np.arange(matches - 1, -1, -1, dtype=np.int32)
    offsets = hamming_offsets(matches, radius)
    codes = np.broadcast_to((picks @ powers)[:, None], (len(picks), len(offsets))).copy()
    for pos, power in enumerate(powers):
        for shift in (1, 2):
            digit = picks[:, pos]
            codes[:, offsets[:, pos] == shift] += (((digit + shift) % 3 - digit) * power)[:, None]
    return codes


def diversified_columns(rows, count, threshold, reference_columns=()):
    """Exact marginal coverage within a finite candidate pool and greedy search."""
    point = np.asarray(validate_probabilities(rows))
    matches = len(point)
    if not 1 <= count <= min(13, 3**matches) or not max(1, matches - 4) <= threshold <= matches:
        raise ValueError("Between 1 and 13 columns and at most four misses are supported.")
    top = best_columns(rows, POOL_TOP)["columns"]
    top_picks = np.asarray(
        [[SIGNS.index(sign) for sign in c["signs"]] for c in [*top, *reference_columns]],
        dtype=np.int32,
    )
    near_mode = (point.argmax(axis=1) + hamming_offsets(matches, min(2, matches))) % 3
    pool = np.unique(np.vstack([top_picks, near_mode]).astype(np.int32), axis=0)
    ball = hamming_codes(pool, matches - threshold)
    weights = np.ones(1)
    for row in point:
        weights = (weights[:, None] * row).ravel()

    chosen, increments = [], []
    for _ in range(count):
        gains = weights[ball].sum(axis=1)
        gains[chosen] = -1
        index = int(gains.argmax())
        chosen.append(index)
        increments.append(float(gains[index]))
        weights[ball[index]] = 0
    columns = [
        {"signs": [SIGNS[j] for j in picks],
         "probability": float(point[np.arange(matches), picks].prod())}
        for picks in pool[chosen]
    ]
    return {"columns": columns, "probability": sum(increments), "candidates": len(pool),
            "marginal_probabilities": increments}


def plan_portfolios(coupon):
    fixtures = coupon["fixtures"]
    if [f["position"] for f in fixtures] != list(range(1, 15)):
        raise ValueError("A frozen ordered fourteen-fixture coupon is required.")
    if coupon["model"]["training_last_date"][:10] >= coupon["cutoff"][:10]:
        raise ValueError("Frozen training must precede the declared cutoff.")
    rows = [[f[k] for k in PROBS] for f in fixtures]
    pack = coupon["budgets"]["5.00"]["strategies"]
    portfolios = {"individual_14": {"columns": pack["individual_columns"]["columns"]}}
    for threshold in THRESHOLDS:
        system = next(
            s for s in threshold_system_frontier(rows, COLUMN_COUNT, threshold)
            if s["column_count"] == COLUMN_COUNT
        )
        portfolios[f"complete_{threshold}"] = {
            "columns": system["columns"], "selections": system["selections"],
        }
        if threshold != 14:
            diverse = diversified_columns(rows, COLUMN_COUNT, threshold, system["columns"])
            portfolios[f"diversified_{threshold}"] = {
                "columns": diverse["columns"], "search_candidates": diverse["candidates"],
                "search_probability": diverse["probability"], "search_threshold": threshold,
            }
    for plan in portfolios.values():
        if len(plan["columns"]) != COLUMN_COUNT:
            raise ValueError("All candidate portfolios must contain exactly six columns.")
        risk = portfolio_risk(rows, plan["columns"])
        if "search_threshold" in plan and not np.isclose(
            risk["at_least"][str(plan["search_threshold"])], plan["search_probability"],
            atol=1e-12, rtol=0,
        ):
            raise ArithmeticError("Search mass disagrees with independent exact risk calculation.")
        plan["cost_eur"] = 4.50
        plan["p_at_least"] = risk["at_least"]
        plan["differing_positions"] = risk["differing_positions"]
        plan["x_covered_positions"] = sum(
            any(c["signs"][pos] == "X" for c in plan["columns"]) for pos in range(14)
        )
    return portfolios


def compare(coupon, actual, prizes, pleno, *, frozen_settlement=None):
    portfolios = plan_portfolios(coupon)
    for name, plan in portfolios.items():
        hits = [
            sum(predicted == real for predicted, real in zip(c["signs"], actual, strict=True))
            for c in plan["columns"]
        ]
        plan["column_hits"], plan["max_hits"] = hits, max(hits)
        plan["x_results_covered"] = sum(
            sign == "X" and any(c["signs"][pos] == "X" for c in plan["columns"])
            for pos, sign in enumerate(actual)
        )
        try:
            settlement = settle_columns(
                plan["columns"], actual, prizes,
                pleno_prediction=coupon["pleno"]["prediction"], pleno_actual=pleno,
            )
        except ValueError as error:
            if not str(error).startswith("No published winner payout"):
                raise
            plan["settlement"] = None
            plan["unpriced_reason"] = str(error)
        else:
            if name == "individual_14" and frozen_settlement is not None:
                for field in ("column_hits", "cost_eur", "gross_return_eur", "net_eur"):
                    if settlement[field] != frozen_settlement[field]:
                        raise ValueError(f"Archived settlement does not reproduce {field}.")
            plan["settlement"] = settlement
    return portfolios


def summarize(coupons):
    methods = list(coupons[0]["portfolios"])
    priceable = [c for c in coupons if all(p["settlement"] is not None
                                          for p in c["portfolios"].values())]
    summary = {}
    for name in methods:
        plans = [c["portfolios"][name] for c in coupons]
        settled = [c["portfolios"][name]["settlement"] for c in priceable]
        cost = round(sum(s["cost_eur"] for s in settled), 2)
        gross = round(sum(s["gross_return_eur"] for s in settled), 2)
        summary[name] = {
            "mean_max_hits": mean(p["max_hits"] for p in plans),
            "mean_p_at_least": {
                str(h): mean(p["p_at_least"][str(h)] for p in plans) for h in THRESHOLDS
            },
            "reached_at_least": {
                str(h): sum(p["max_hits"] >= h for p in plans) for h in THRESHOLDS
            },
            "mean_differing_positions": mean(p["differing_positions"] for p in plans),
            "mean_x_covered_positions": mean(p["x_covered_positions"] for p in plans),
            "total_realized_x_covered": sum(p["x_results_covered"] for p in plans),
            "unpriced_own_portfolios": sum(p["settlement"] is None for p in plans),
            "matched_cost_eur": cost, "matched_gross_eur": gross,
            "matched_net_eur": round(gross - cost, 2), "matched_roi": gross / cost - 1 if cost else None,
        }
    return {
        "coupons": len(coupons), "common_priceable_coupons": len(priceable),
        "unpriced_dates": [c["id"] for c in coupons if c not in priceable],
        "methods": summary,
    }


def recent_comparisons():
    reports = Path("outputs/reports")
    j18 = reports / "j18_evaluation_20261110/report.json"
    j18_forecast = Path("outputs/predictions/coverage_pool50/comparator/2026_j18/forecast.json")
    j20 = reports / "j20_retrospective_20261110/report.json"
    j20_forecast = j20.parent / "forecast/forecast.json"
    official = read(j18)["official_results"]
    result = read(j20)
    inputs = [
        ("J18", j18_forecast, official["awarded_signs"], official["prizes"],
         official["pleno"]["score"], read(j18)["primary_paper_coverage"]["comparator"]),
        ("J20", j20_forecast, result["official_signs"], result["unit_prizes"],
         result["official_pleno"], result["primary_settlement"]),
    ]
    comparisons = []
    for name, forecast, signs, prizes, pleno, reference in inputs:
        coupon = read(forecast)["coupons"][0]
        plans = compare(coupon, signs, prizes, pleno, frozen_settlement=reference)
        comparisons.append({"id": name, "official_signs": signs, "portfolios": plans})
    hashes = {str(p): digest(p) for p in (j18, j18_forecast, j20, j20_forecast)}
    return comparisons, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("outputs/reports/allocations_v1/report.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output to preserve previous research.")
    archive = read(args.archive)
    comparisons = []
    for coupon in archive["coupons"]:
        official = coupon["official"]
        actual = [f["sign"] for f in official["fixtures"]]
        original = coupon["settlement"]["individual_columns"]
        plans = compare(coupon, actual, official["prizes"], coupon["pleno"]["actual"],
                        frozen_settlement=original)
        comparisons.append({"id": coupon["date"], "official_signs": actual, "portfolios": plans})
        if len(comparisons) % 10 == 0:
            print("Historical coupons", len(comparisons), flush=True)
    if len({c["id"] for c in comparisons}) != len(comparisons):
        raise ValueError("Historical archive contains duplicate coupon dates.")
    recent, sources = recent_comparisons()
    summary = summarize(comparisons)
    write_new(args.output, {
        "schema_version": 1, "created_at": datetime.now(UTC).isoformat(),
        "mode": "retrospective", "column_count": COLUMN_COUNT, "cost_eur": 4.50,
        "source_sha256": {**sources, str(args.archive): digest(args.archive)},
        "search": {
            "candidate_pool": f"{POOL_TOP} most probable columns, all one- and two-sign changes "
                              "of the mode, and the complete-system columns for the objective",
            "method": "Greedy selection by exact additional model probability of reaching target",
            "risk": "Exact joint coverage conditional on independent fixture outcomes",
            "optimizer_heuristic": True,
        },
        "historical_summary": summary, "historical_coupons": comparisons, "recent_coupons": recent,
        "limitations": [
            "Historical coupons have been used in earlier research. J18 and J20 are descriptive.",
            "The same original pre-match probabilities and Pleno are used across portfolios.",
            "Settlement uses published unit prizes and awarded signs, including official draws.",
            "Matched simulated returns exclude any coupon with an unresolved hypothetical prize.",
            "No counterfactual prize dilution, tax or pre-close expected ROI.",
        ],
    })
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
