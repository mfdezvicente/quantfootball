"""Canonical team names for Quant Football."""

from __future__ import annotations

TEAM_ALIASES: dict[str, str] = {
    "Atlético Madrid": "Club Atlético de Madrid",
    "CD Alavés": "Deportivo Alavés",
    "Espanyol Barcelona": "RCD Espanyol de Barcelona",
    "Rayo Vallecano": "Rayo Vallecano de Madrid",
    "RC Celta": "RC Celta de Vigo",
    "Real Betis": "Real Betis Balompié",
    "Real Madrid": "Real Madrid CF",
    "Real Sociedad": "Real Sociedad de Fútbol",
    "Real Valladolid": "Real Valladolid CF",
}


def canonicalize_team(name: str) -> str:
    """Return the canonical Quant Football name for a source team name."""
    cleaned = name.strip()
    return TEAM_ALIASES.get(cleaned, cleaned)
