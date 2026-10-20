"""Canonical team names for Quant Football."""

from __future__ import annotations

TEAM_ALIASES: dict[str, str] = {
    "Atlético de Madrid": "Club Atlético de Madrid",
    "Celta": "RC Celta de Vigo",
    "Albacete BP": "Albacete",
    "Albacete Balompié": "Albacete",
    "Cultural y Deportiva Leonesa": "Cultural Leonesa",
    "R. Racing Club": "Racing Santander",
    "Real Racing Club de Santander": "Racing Santander",
    "R. Sociedad B": "Real Sociedad B",
    "RC Deportivo": "Deportivo La Coruña",
    "RC Deportivo La Coruña": "Deportivo La Coruña",
    "Real Sporting": "Sporting Gijón",
    "Real Sporting de Gijón": "Sporting Gijón",
    "R. Oviedo": "Real Oviedo",
    "CD Eldense": "Eldense",
    "Racing Club Ferrol": "Racing Ferrol",
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
