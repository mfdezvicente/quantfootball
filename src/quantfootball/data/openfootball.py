"""OpenFootball ingestion for Quant Football."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from quantfootball.data.teams import canonicalize_team

BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"
DEFAULT_SEASONS = tuple(f"{year}-{str(year + 1)[-2:]}" for year in range(2015, 2026))
COMPETITION_CODE = "es.1"
COMPETITION_NAME = "LaLiga"


def source_url(season: str) -> str:
    """Return the raw OpenFootball URL for a LaLiga season."""
    return f"{BASE_URL}/{season}/{COMPETITION_CODE}.json"


def download_season(
    season: str,
    raw_root: Path,
    *,
    timeout: float = 30.0,
    force: bool = False,
) -> Path:
    """Download one season to the local raw-data cache."""
    destination = raw_root / "openfootball" / season / f"{COMPETITION_CODE}.json"
    if destination.exists() and not force:
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(source_url(season), timeout=timeout)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def _matchday(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None


def _coerce_pair(value: Any) -> tuple[int | None, int | None]:
    """Convert a two-item score representation into integer goals."""
    if not isinstance(value, list) or len(value) != 2:
        return None, None
    if value[0] is None or value[1] is None:
        return None, None
    if any(
        isinstance(g, bool)
        or not isinstance(g, (int, float))
        or not math.isfinite(g)
        or g < 0
        or g != int(g)
        for g in value
    ):
        raise ValueError("Goals must be finite nonnegative integers.")
    return int(value[0]), int(value[1])


def _score_pair(score: Any, key: str) -> tuple[int | None, int | None]:
    """Read a score pair from either supported OpenFootball score schema.

    OpenFootball normally stores scores as:
        {"ft": [home, away], "ht": [home, away]}

    Some fixtures are stored directly as:
        [home, away]

    In the list-only form we can recover only the full-time score.
    """
    if isinstance(score, dict):
        return _coerce_pair(score.get(key))

    if isinstance(score, list):
        if key == "ft":
            return _coerce_pair(score)
        return None, None

    return None, None


def _match_id(season: str, date: str, home_team: str, away_team: str) -> str:
    raw = f"{season}|{date}|{home_team}|{away_team}".encode()
    return hashlib.blake2b(raw, digest_size=10).hexdigest()


def normalize_payload(
    payload: dict[str, Any], season: str, competition_code: str = "es.1"
) -> pd.DataFrame:
    """Normalize one OpenFootball season into the Quant Football match schema."""
    rows: list[dict[str, Any]] = []

    for match in payload.get("matches", []):
        home_team_raw = str(match.get("team1", "")).strip()
        away_team_raw = str(match.get("team2", "")).strip()
        home_team = canonicalize_team(home_team_raw)
        away_team = canonicalize_team(away_team_raw)
        date = match.get("date")
        score = match.get("score")

        home_goals, away_goals = _score_pair(score, "ft")
        home_goals_ht, away_goals_ht = _score_pair(score, "ht")
        is_completed = home_goals is not None and away_goals is not None

        if is_completed:
            if home_goals > away_goals:
                result = "H"
            elif home_goals < away_goals:
                result = "A"
            else:
                result = "D"
        else:
            result = None

        rows.append(
            {
                "match_id": _match_id(season, str(date), home_team, away_team),
                "competition": {"es.1": "LaLiga", "es.2": "Segunda"}[competition_code],
                "competition_code": competition_code,
                "country": "ESP",
                "season": season,
                "matchday": _matchday(match.get("round")),
                "date": date,
                "kickoff_time": match.get("time"),
                "home_team": home_team,
                "away_team": away_team,
                "home_team_raw": home_team_raw,
                "away_team_raw": away_team_raw,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "home_goals_ht": home_goals_ht,
                "away_goals_ht": away_goals_ht,
                "result": result,
                "is_completed": is_completed,
                "source": "openfootball",
                "source_url": f"{BASE_URL}/{season}/{competition_code}.json",
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    for column in [
        "matchday",
        "home_goals",
        "away_goals",
        "home_goals_ht",
        "away_goals_ht",
    ]:
        frame[column] = frame[column].astype("Int64")

    return frame.sort_values(["date", "kickoff_time", "home_team"]).reset_index(drop=True)


def load_season(path: Path, season: str) -> pd.DataFrame:
    """Load and normalize a cached OpenFootball JSON file."""
    import json

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return normalize_payload(payload, season)


def validate_matches(frame: pd.DataFrame) -> None:
    """Raise ValueError when core data-integrity checks fail."""
    required = {
        "match_id",
        "season",
        "date",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        "result",
        "is_completed",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if frame.empty:
        raise ValueError("Dataset is empty.")

    core = ["match_id", "season", "date", "home_team", "away_team"]
    if frame[core].isna().any().any():
        raise ValueError("Core match fields contain missing values.")
    if frame[["home_team", "away_team"]].apply(lambda c: c.str.strip().eq("")).any().any():
        raise ValueError("Empty team names detected.")

    if (frame["home_team"] == frame["away_team"]).any():
        raise ValueError("A match contains the same home and away team.")

    completed = frame["is_completed"]
    if frame.loc[completed, ["home_goals", "away_goals", "result"]].isna().any().any():
        raise ValueError("Completed matches contain missing result fields.")

    goals = frame.loc[completed, ["home_goals", "away_goals"]]
    if (goals < 0).any().any():
        raise ValueError("Negative goals detected.")
    if (goals % 1 != 0).any().any():
        raise ValueError("Goals must be integers.")
    expected = goals.apply(
        lambda row: "H" if row.iloc[0] > row.iloc[1] else "A" if row.iloc[0] < row.iloc[1] else "D",
        axis=1,
    )
    if not frame.loc[completed, "result"].eq(expected).all():
        raise ValueError("Result labels disagree with full-time goals.")

    duplicate_key = ["season", "date", "home_team", "away_team"]
    if frame.duplicated(duplicate_key).any():
        raise ValueError("Duplicate fixtures detected.")


def build_laliga_dataset(
    seasons: tuple[str, ...] = DEFAULT_SEASONS,
    *,
    raw_root: Path = Path("data/raw"),
    output_path: Path = Path("data/processed/matches.parquet"),
    force_download: bool = False,
) -> pd.DataFrame:
    """Download, normalize, validate and persist the historical LaLiga dataset."""
    frames: list[pd.DataFrame] = []

    for season in seasons:
        path = download_season(season, raw_root, force=force_download)
        frames.append(load_season(path, season))

    matches = pd.concat(frames, ignore_index=True)
    matches = matches.loc[matches["is_completed"]].copy()
    matches = matches.sort_values(["date", "kickoff_time", "home_team"]).reset_index(drop=True)

    validate_matches(matches)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    matches.to_parquet(output_path, index=False)
    return matches
