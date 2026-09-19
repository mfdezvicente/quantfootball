import pandas as pd

from quantfootball.data.openfootball import normalize_payload, validate_matches


def _payload() -> dict:
    return {
        "name": "Spain Primera División 2025/26",
        "matches": [
            {
                "round": "Matchday 1",
                "date": "2025-08-15",
                "time": "19:00",
                "team1": "Girona FC",
                "team2": "Rayo Vallecano de Madrid",
                "score": {"ft": [1, 3], "ht": [0, 3]},
            },
            {
                "round": "Matchday 1",
                "date": "2025-08-18",
                "time": "21:00",
                "team1": "Elche CF",
                "team2": "Real Betis Balompié",
                "score": {"ft": [1, 1], "ht": [0, 1]},
            },
        ],
    }


def test_normalize_payload_builds_canonical_columns() -> None:
    frame = normalize_payload(_payload(), "2025-26")

    assert len(frame) == 2
    assert frame.loc[0, "matchday"] == 1
    assert frame.loc[0, "result"] == "A"
    assert frame.loc[1, "result"] == "D"
    assert frame["is_completed"].all()
    assert pd.api.types.is_datetime64_any_dtype(frame["date"])


def test_match_ids_are_deterministic() -> None:
    first = normalize_payload(_payload(), "2025-26")
    second = normalize_payload(_payload(), "2025-26")

    assert first["match_id"].tolist() == second["match_id"].tolist()


def test_validate_matches_accepts_valid_frame() -> None:
    frame = normalize_payload(_payload(), "2025-26")
    validate_matches(frame)
