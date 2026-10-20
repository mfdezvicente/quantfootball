"""Historical coupon matching and gross prize accounting, separate from forecasts."""

import re
from decimal import Decimal

import pandas as pd

from quantfootball.data.teams import canonicalize_team

# Explicit source aliases; reserve teams and female teams must never collapse to men.
SELAE_ALIASES = {
    "Zaragoza": "Real Zaragoza",
    "Andorra": "FC Andorra",
    "Ceuta": "AD Ceuta FC",
    "Racing": "Racing Santander",
    "R. Valladolid": "Real Valladolid CF",
    "Racing de Santander": "Racing Santander",
    "Betis": "Real Betis Balompié",
    "At. Madrid": "Club Atlético de Madrid",
    "Celta": "RC Celta de Vigo",
    "Espanyol": "RCD Espanyol de Barcelona",
    "Alavés": "Deportivo Alavés",
    "Leganés": "CD Leganés",
    "Girona": "Girona FC",
    "Valencia": "Valencia CF",
    "Getafe": "Getafe CF",
    "Villarreal": "Villarreal CF",
    "Sevilla": "Sevilla FC",
    "Mallorca": "RCD Mallorca",
    "Osasuna": "CA Osasuna",
    "Valladolid": "Real Valladolid CF",
    "Barcelona": "FC Barcelona",
    "Las Palmas": "UD Las Palmas",
    "Almería": "UD Almería",
    "Córdoba": "Córdoba CF",
    "Levante": "Levante UD",
    "Huesca": "SD Huesca",
    "Elche": "Elche CF",
    "Mirandés": "CD Mirandés",
    "Burgos": "Burgos CF",
    "Málaga": "Málaga CF",
    "Tenerife": "CD Tenerife",
    "R. Zaragoza": "Real Zaragoza",
    "Granada": "Granada CF",
    "Cartagena": "FC Cartagena",
    "Deportivo": "Deportivo La Coruña",
    "Castellón": "CD Castellón",
    "Eibar": "SD Eibar",
    "Cádiz": "Cádiz CF",
    "Sporting": "Sporting Gijón",
    "R. Oviedo": "Real Oviedo",
}


def parse_official_extract(text, coupon_date):
    """Parse saved public SELAE statistical tables; missing payouts stay unknown."""
    values = re.findall(r"^(?:L\d+|QF):\s+\* ([^\n\r]+)", text, re.MULTILINE)
    start = next(
        (i for i in range(len(values)) if values[i : i + 14] == [str(j) for j in range(1, 15)]),
        None,
    )
    if start is None or len(values) < start + 75:
        raise ValueError("Official fourteen-fixture table and Pleno are incomplete.")
    table = values[start : start + 75]
    fixtures = []
    for i in range(14):
        home, away, score, sign = table[14 + i], table[28 + i], table[42 + i], table[56 + i]
        if sign not in ("1", "X", "2") or not re.fullmatch(r"\d+-\d+", score):
            raise ValueError("Unsupported awarded/abandoned fixture or malformed official result.")
        h, a = map(int, score.split("-"))
        if sign != ("1" if h > a else "2" if h < a else "X"):
            raise ValueError("Official score and sign disagree.")
        fixtures.append(
            {"position": i + 1, "home_raw": home, "away_raw": away, "score": score, "sign": sign}
        )
    if table[70] != "15":
        raise ValueError("Missing Pleno position.")
    prizes = {}
    pattern = r"^(?:L\d+@P\d+|QF): (Pleno al 15|1[0-4] Aciertos) ([\d.]+) ([\d.,]+|BOTE)\s*$"
    for category, winners, payout in re.findall(pattern, text, re.MULTILINE):
        key = "15" if category.startswith("Pleno") else category[:2]
        value = {
            "winners": int(winners.replace(".", "")),
            "unit_eur": None if payout == "BOTE" else payout.replace(".", "").replace(",", "."),
        }
        if key in prizes and prizes[key] != value:
            raise ValueError(f"Conflicting official payouts for category {key}.")
        prizes[key] = value
    return {
        "date": coupon_date,
        "fixtures": fixtures,
        "pleno": {
            "home_raw": table[71],
            "away_raw": table[72],
            "score": table[73],
            "actual": table[74].replace(" ", ""),
        },
        "prizes": prizes,
    }


def match_coupon(coupon, history):
    date = pd.Timestamp(coupon["date"])
    window = history[
        (history.date >= date - pd.Timedelta(days=4))
        & (history.date <= date + pd.Timedelta(days=2))
    ]
    rows = []
    for fixture in [*coupon["fixtures"], coupon["pleno"]]:

        def name(raw):
            return canonicalize_team(SELAE_ALIASES.get(raw, raw))

        home, away = name(fixture["home_raw"]), name(fixture["away_raw"])
        hits = window[(window.home_team == home) & (window.away_team == away)]
        if len(hits) != 1:
            raise ValueError(f"Outside covered leagues or ambiguous: {home} / {away}")
        row = hits.iloc[0]
        if f"{row.home_goals}-{row.away_goals}" != fixture["score"]:
            raise ValueError(f"Source score disagreement: {home} / {away}")
        rows.append(
            {
                "position": len(rows) + 1,
                "date": row.date,
                "home_team": home,
                "away_team": away,
                "competition_code": row.competition_code,
                "gender": "men",
                "match_id": row.match_id,
            }
        )
    frame = pd.DataFrame(rows)
    if len(set(frame.home_team) | set(frame.away_team)) != 30:
        raise ValueError("Official coupon repeats a team.")
    return frame.iloc[:14].copy(), frame.iloc[14].to_dict()


def settle_columns(
    columns, actual, prizes, *, pleno_prediction=None, pleno_actual=None, price="0.75"
):
    if len(actual) != 14 or any(s not in ("1", "X", "2") for s in actual):
        raise ValueError("Fourteen official signs are required.")
    if len({tuple(c["signs"]) for c in columns}) != len(columns):
        raise ValueError("Duplicate columns are not allowed.")
    if set(prizes) != {str(i) for i in range(10, 16)}:
        raise ValueError("All six official prize categories are required.")
    returned, counts = Decimal(0), []
    for col in columns:
        if len(col["signs"]) != 14 or any(s not in ("1", "X", "2") for s in col["signs"]):
            raise ValueError("Invalid betting column.")
        hits = sum(a == b for a, b in zip(col["signs"], actual))
        counts.append(hits)
        categories = [str(hits)] if hits >= 10 else []
        if hits == 14 and pleno_prediction is not None and pleno_prediction == pleno_actual:
            categories.append("15")
        for category in categories:
            unit = prizes[category]["unit_eur"]
            if unit is None:
                raise ValueError(
                    f"No published winner payout for {category}; cannot infer a counterfactual jackpot."
                )
            payout = Decimal(str(unit))
            if not payout.is_finite() or payout < 0:
                raise ValueError("Invalid official prize amount.")
            returned += payout
    cost = Decimal(price) * len(columns)
    if cost <= 0:
        raise ValueError("Positive cost required.")
    return {
        "cost_eur": float(cost),
        "gross_return_eur": float(returned),
        "net_eur": float(returned - cost),
        "roi": float((returned - cost) / cost),
        "column_hits": counts,
        "max_hits": max(counts),
        "accounting": "Published gross unit prizes; excludes tax and counterfactual prize-pool dilution",
    }
