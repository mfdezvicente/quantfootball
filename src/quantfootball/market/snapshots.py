"""Timestamped market inputs. Betting shares and outcome probabilities stay separate."""

from datetime import UTC, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import numpy as np

from quantfootball.data.competitions import GENDERS, women_team_name
from quantfootball.data.teams import canonicalize_team


def instant(value):
    """Require an explicit timezone; never guess a source's local clock."""
    if not isinstance(value, str):
        raise TypeError("An ISO timestamp with timezone is required.")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("Timestamp must include timezone.")
    return stamp.astimezone(UTC)


def source_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A public HTTPS source URL is required.")
    if parsed.query:
        raise ValueError("Use a source URL without query parameters or API credentials.")
    return value


def devig(odds):
    values = np.asarray(odds, dtype=float)
    if values.shape != (3,) or not np.isfinite(values).all() or (values <= 1).any():
        raise ValueError("Three finite decimal 1X2 odds greater than one are required.")
    inverse = 1 / values
    return (inverse / inverse.sum()).tolist(), float(inverse.sum() - 1)


def key(row):
    code = row["competition_code"]
    if code not in GENDERS:
        raise ValueError("Unsupported competition.")
    if "gender" in row and row["gender"] != GENDERS[code]:
        raise ValueError("Fixture gender does not match competition.")
    if code == "es.w.1" and row.get("gender") != "women":
        raise ValueError("Liga F market/manifest fixtures require gender='women'.")
    normalizer = women_team_name if code == "es.w.1" else canonicalize_team
    return (
        row["competition_code"],
        normalizer(row["home_team"]),
        normalizer(row["away_team"]),
    )


def compare_snapshot(coupon, snapshot, deadline, *, max_age_hours=48):
    """Use the latest eligible quote per bookmaker at a common decision time.

    Historical source timestamps are assertions of the supplied archive, not proof
    that this application possessed them at that time. No market blending is fitted.
    """
    boundary = instant(deadline)
    captured = instant(snapshot["snapshot_at"])
    retrieved = instant(snapshot["retrieved_at"])
    if captured > boundary or retrieved < captured:
        raise ValueError("Snapshot is later than the decision time or retrieval precedes it.")
    if not np.isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("Positive maximum quote age required.")
    source_url(snapshot["source_url"])
    if snapshot["schema_version"] != 1:
        raise ValueError("Unsupported market snapshot schema.")
    rows = {}
    for row in snapshot["fixtures"]:
        kickoff = instant(row["starts_at"])
        fixture_key = (*key(row), kickoff.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat())
        if fixture_key in rows:
            raise ValueError("Repeated fixture on the same local date in market snapshot.")
        rows[fixture_key] = row
    compared, missing = [], []
    for fixture in coupon["fixtures"]:
        position = fixture["position"]
        row = rows.get((*key(fixture), fixture["date"][:10]))
        if row is None:
            missing.append({"position": position, "reason": "No matching market fixture"})
            continue
        kickoff = instant(row["starts_at"])
        # Team identity alone is insufficient for a return fixture or a later season.
        local_day = kickoff.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat()
        if local_day != fixture["date"][:10] or boundary >= kickoff:
            raise ValueError("Fixture date mismatch or decision time is after kickoff.")
        books, rejected = {}, []
        for quote in row.get("quotes", []):
            observed = instant(quote["observed_at"])
            book = quote["bookmaker"]
            if not isinstance(book, str) or not book.strip():
                raise ValueError("Bookmaker identity required.")
            if observed > captured or observed >= kickoff:
                rejected.append({"bookmaker": book, "reason": "Quote later than snapshot/kickoff"})
                continue
            if (boundary - observed).total_seconds() > max_age_hours * 3600:
                rejected.append({"bookmaker": book, "reason": "Stale quote"})
                continue
            probabilities, margin = devig(quote["odds_1x2"])
            prior = books.get(book)
            if prior and observed == prior["time"] and quote["odds_1x2"] != prior["odds"]:
                raise ValueError("Conflicting quotes at the same bookmaker timestamp.")
            if prior is None or observed > prior["time"]:
                books[book] = {
                    "time": observed,
                    "p": probabilities,
                    "margin": margin,
                    "odds": quote["odds_1x2"],
                }
        if not books:
            missing.append(
                {
                    "position": position,
                    "reason": "No eligible pre-decision quotes",
                    "rejected": rejected,
                }
            )
            continue
        market = np.mean([book["p"] for book in books.values()], axis=0)
        model = np.asarray([fixture[p] for p in ("p_home", "p_draw", "p_away")])
        if not np.isfinite(model).all() or (model <= 0).any() or not np.isclose(model.sum(), 1):
            raise ValueError("Invalid model probabilities.")
        crowd = row.get("crowd")
        if crowd:
            stamp = instant(crowd["observed_at"])
            shares = np.asarray(crowd["shares_1x2"], dtype=float)
            if (
                stamp > captured
                or (boundary - stamp).total_seconds() > max_age_hours * 3600
                or shares.shape != (3,)
                or not np.isfinite(shares).all()
                or (shares < 0).any()
                or not np.isclose(shares.sum(), 1)
            ):
                raise ValueError("Invalid, future or stale crowd shares.")
            source_url(crowd["source_url"])
        compared.append(
            {
                "position": position,
                "competition_code": fixture["competition_code"],
                "date": local_day,
                "starts_at": kickoff.isoformat(),
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "model_1x2": model.tolist(),
                "market_1x2": market.tolist(),
                "difference_1x2": (model - market).tolist(),
                "bookmakers": sorted(books),
                "bookmaker_count": len(books),
                "average_overround": float(np.mean([b["margin"] for b in books.values()])),
                "latest_quote_at": max(b["time"] for b in books.values()).isoformat(),
                "crowd_shares_1x2": shares.tolist() if crowd else None,
                "rejected_quotes": rejected,
            }
        )
    return {
        "is_example": bool(snapshot.get("is_example", False)),
        "decision_at": boundary.isoformat(),
        "source_url": snapshot["source_url"],
        "snapshot_at": captured.isoformat(),
        "retrieved_at": retrieved.isoformat(),
        "available_to_this_app_before_decision": retrieved <= boundary,
        "matched_fixtures": len(compared),
        "missing": missing,
        "fixtures": compared,
        "method": "Normalize inverse odds within bookmaker, then average bookmakers equally",
        "limitations": [
            "Margin removal is an approximation; consensus is not ground truth",
            "Market has not been blended into the model or used to select a strategy",
            "Crowd marginal shares do not identify joint column popularity or expected prizes",
        ],
        "positive_expected_roi_demonstrated": False,
    }
