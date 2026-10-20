"""Explicit competition and gender boundaries for mixed Quiniela forecasts."""

GENDERS = {"es.1": "men", "es.2": "men", "es.w.1": "women"}

WOMEN_ALIASES = {
    "barcelona": "FC Barcelona",
    "real madrid": "Real Madrid CF",
    "at. madrid": "Atlético de Madrid",
    "at.madrid": "Atlético de Madrid",
    "club atlético de madrid": "Atlético de Madrid",
    "atlético madrid": "Atlético de Madrid",
    "r. sociedad": "Real Sociedad",
    "real sociedad de fútbol": "Real Sociedad",
    "athletic": "Athletic Club",
    "levante": "Levante UD",
    "eibar": "SD Eibar",
    "espanyol": "RCD Espanyol de Barcelona",
    "alavés": "Deportivo Alavés",
    "granada": "Granada CF",
    "sevilla": "Sevilla FC",
    "valencia": "VCF Femenino",
    "valencia cf": "VCF Femenino",
    "betis": "R. Betis Féminas",
    "real betis balompié": "R. Betis Féminas",
    "deportivo": "Deportivo Abanca",
    "deportivo la coruña": "Deportivo Abanca",
    "tenerife": "Costa Adeje Tenerife",
    "costa adeje": "Costa Adeje Tenerife",
    "badalona": "FC Badalona Women",
    "fc levante badalona": "FC Badalona Women",
    "levante las planas": "FC Badalona Women",
    "logroño": "Logroño United",
    "dux logroño": "Logroño United",
    "alhama": "Alhama CF ElPozo",
    "madrid cff": "Madrid CFF",
}


def validate_competitions(frame):
    if "competition_code" not in frame or not frame.competition_code.isin(GENDERS).all():
        raise ValueError("Explicit es.1/es.2/es.w.1 competition codes are required.")
    expected = frame.competition_code.map(GENDERS)
    if "gender" in frame:
        if not frame.gender.eq(expected).all():
            raise ValueError("Competition gender mismatch: es.1/es.2 are men; es.w.1 is women.")
    elif expected.eq("women").any():
        raise ValueError("Women's fixtures/history require explicit gender='women'.")


def women_team_name(name):
    cleaned = name.strip()
    cleaned = cleaned.removesuffix(" [F]")
    if not cleaned:
        raise ValueError("Nonempty women's team name required.")
    return WOMEN_ALIASES.get(cleaned.casefold(), cleaned) + " [F]"
