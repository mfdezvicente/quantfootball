"""Current three-way football odds from the licensed The Odds API v4 feed.

No historical endpoints, automatic retries or paid subscriptions are invoked.
Public request metadata omits the key. Outcome order is resolved by names, never
by the position in a bookmaker's array. Unknown aliases remain auditable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import requests

from quantfootball.data.teams import canonicalize_team
from quantfootball.market.snapshots import devig, instant

API_ROOT = "https://api.the-odds-api.com/v4"
SPORT_KEYS = {"es.1": "soccer_spain_la_liga", "es.2": "soccer_spain_segunda_division"}
ALIASES = {
    "Barcelona": "FC Barcelona", "Atletico Madrid": "Club Atlético de Madrid",
    "Athletic Bilbao": "Athletic Club", "Athletic Club Bilbao": "Athletic Club",
    "Alaves": "Deportivo Alavés", "Deportivo Alaves": "Deportivo Alavés",
    "Espanyol": "RCD Espanyol de Barcelona", "Osasuna": "CA Osasuna",
    "Celta Vigo": "RC Celta de Vigo", "Celta de Vigo": "RC Celta de Vigo",
    "Betis": "Real Betis Balompié", "Sevilla": "Sevilla FC",
    "Valencia": "Valencia CF", "Villarreal": "Villarreal CF", "Getafe": "Getafe CF",
    "Elche": "Elche CF", "Levante": "Levante UD", "Malaga": "Málaga CF",
    "Deportivo La Coruna": "Deportivo La Coruña", "Deportivo Coruna": "Deportivo La Coruña",
    "Almeria": "UD Almería", "Almería": "UD Almería", "Burgos": "Burgos CF",
    "Cadiz": "Cádiz CF", "Cádiz": "Cádiz CF", "Leganes": "CD Leganés",
    "Leganés": "CD Leganés", "Sabadell": "CE Sabadell", "Andorra": "FC Andorra",
    "FC Andorra": "FC Andorra", "Granada": "Granada CF", "Sporting": "Sporting Gijón",
    "Castellon": "CD Castellón", "Castellón": "CD Castellón", "Ceuta": "AD Ceuta FC",
    "Las Palmas": "UD Las Palmas", "Girona": "Girona FC", "Mallorca": "RCD Mallorca",
    "Cordoba": "Córdoba CF", "Córdoba": "Córdoba CF", "Tenerife": "CD Tenerife",
    "Oviedo": "Real Oviedo", "Eibar": "SD Eibar",
    "Málaga": "Málaga CF", "Alavés": "Deportivo Alavés",
    "Sabadell FC": "CE Sabadell", "Andorra CF": "FC Andorra",
}


class OddsAPIError(RuntimeError):
    """A message safe to log: it never includes a request URL, response or key."""


def _public_events(payload):
    if not isinstance(payload, list):
        raise OddsAPIError("La API no devolvió una lista de eventos válida.")
    output = []
    for event in payload:
        if not isinstance(event, dict):
            raise OddsAPIError("La API devolvió un evento no válido.")
        books = []
        source_books = event.get("bookmakers", [])
        if not isinstance(source_books, list):
            raise OddsAPIError("La API devolvió casas de apuestas no válidas.")
        for book in source_books:
            if not isinstance(book, dict) or not isinstance(book.get("markets", []), list):
                raise OddsAPIError("La API devolvió mercados no válidos.")
            markets = []
            for market in book.get("markets", []):
                if not isinstance(market, dict):
                    raise OddsAPIError("La API devolvió un mercado no válido.")
                if market.get("key") == "h2h":
                    outcomes = market.get("outcomes", [])
                    if not isinstance(outcomes, list) or any(not isinstance(o, dict) for o in outcomes):
                        raise OddsAPIError("La API devolvió resultados de mercado no válidos.")
                    markets.append({"key": "h2h", "last_update": market.get("last_update"),
                        "outcomes": [{"name": o.get("name"), "price": o.get("price")}
                                     for o in outcomes]})
            books.append({"key": book.get("key"), "title": book.get("title"),
                          "last_update": book.get("last_update"), "markets": markets})
        output.append({**{k: event.get(k) for k in (
            "id", "sport_key", "commence_time", "home_team", "away_team")}, "bookmakers": books})
    return output


class OddsAPIClient:
    def __init__(self, key):
        self._key = key
        self._session = requests.Session()

    def _get(self, endpoint, parameters):
        started = datetime.now(UTC)
        try:
            response = self._session.get(API_ROOT + endpoint,
                params={**parameters, "apiKey": self._key}, timeout=(10, 30), allow_redirects=False)
        except requests.RequestException:
            raise OddsAPIError("No se pudo conectar con The Odds API; no se reintentó la petición.") from None
        if response.status_code != 200:
            details = {401: "Revisa la clave.", 403: "Revisa los permisos de la cuenta.",
                       429: "Cuota o límite de peticiones alcanzado."}.get(response.status_code, "")
            raise OddsAPIError(f"The Odds API devolvió HTTP {response.status_code}. {details}")
        received = datetime.now(UTC)
        try:
            body = response.json()
        except (ValueError, requests.RequestException):
            raise OddsAPIError("La API devolvió una respuesta que no es JSON válido.") from None
        quota = {}
        for header in ("x-requests-used", "x-requests-remaining", "x-requests-last"):
            raw = response.headers.get(header)
            if raw is not None:
                try:
                    quota[header] = int(raw)
                except ValueError:
                    raise OddsAPIError("La API devolvió información de cuota no válida.") from None
        return body, {"source_url": API_ROOT + endpoint, "parameters": parameters,
                      "request_started_at": started.isoformat(), "received_at": received.isoformat(),
                      "quota": quota}

    def sports(self):
        payload, metadata = self._get("/sports/", {"all": "true"})
        if not isinstance(payload, list) or any(not isinstance(s, dict) for s in payload):
            raise OddsAPIError("El catálogo de deportes no es válido.")
        sports = [{k: s.get(k) for k in ("key", "group", "title", "active", "has_outrights")}
                  for s in payload]
        return json.loads(json.dumps(sports).replace(self._key, "[REDACTED]")), metadata

    def current_odds(self, code, start=None, end=None):
        if code not in SPORT_KEYS:
            raise ValueError("Competición no autorizada para esta conexión.")
        parameters = {"regions": "eu", "markets": "h2h", "oddsFormat": "decimal", "dateFormat": "iso"}
        if start:
            parameters["commenceTimeFrom"] = instant(start).isoformat(timespec="seconds").replace("+00:00", "Z")
        if end:
            parameters["commenceTimeTo"] = instant(end).isoformat(timespec="seconds").replace("+00:00", "Z")
        payload, metadata = self._get(f"/sports/{SPORT_KEYS[code]}/odds/", parameters)
        events = _public_events(payload)
        # Credential strings are removed even if unexpectedly echoed in success data.
        events = json.loads(json.dumps(events).replace(self._key, "[REDACTED]"))
        metadata["payload_sha256"] = hashlib.sha256(json.dumps(events, sort_keys=True).encode()).hexdigest()
        return {"competition_code": code, "events": events, **metadata}


def convert_records(records, *, aliases=None, is_example=False):
    if not records:
        raise ValueError("No hay capturas de cuotas para convertir.")
    mapping = {**ALIASES, **(aliases or {})}
    if any(not isinstance(k, str) or not isinstance(v, str) or not k.strip() or not v.strip()
           for k, v in mapping.items()):
        raise ValueError("Los alias deben relacionar dos nombres no vacíos.")
    retrieved = max(instant(r["received_at"]) for r in records)
    fixtures, rejected, identifiers = [], [], set()
    for record in records:
        code = record["competition_code"]
        if code not in SPORT_KEYS:
            raise ValueError("Sólo se han aprobado Primera y Segunda para esta integración.")
        received = instant(record["received_at"])
        for event in record["events"]:
            event_id = (code, event.get("id"))
            if not event_id[1] or event_id in identifiers:
                raise ValueError("Evento duplicado o sin identificador del proveedor.")
            identifiers.add(event_id)
            if event.get("sport_key") != SPORT_KEYS[code]:
                raise ValueError("El deporte recibido no corresponde a la competición solicitada.")
            raw_home, raw_away = event.get("home_team"), event.get("away_team")
            if not all(isinstance(t, str) and t.strip() for t in (raw_home, raw_away)):
                raise ValueError("El proveedor no identifica correctamente los equipos.")
            home, away = [canonicalize_team(mapping.get(t, t)) for t in (raw_home, raw_away)]
            if home == away:
                raise ValueError("Una pareja de equipos se ha convertido en la misma identidad.")
            kickoff = instant(event["commence_time"])
            parameters = record.get("parameters", {})
            if ((parameters.get("commenceTimeFrom") and kickoff < instant(parameters["commenceTimeFrom"]))
                or (parameters.get("commenceTimeTo") and kickoff > instant(parameters["commenceTimeTo"]))):
                rejected.append({"event_id": event_id[1], "reason": "outside_requested_window"})
                continue
            if kickoff <= received:
                rejected.append({"event_id": event_id[1], "reason": "already_started"})
                continue
            quotes = []
            for book in event["bookmakers"]:
                for market in book["markets"]:
                    try:
                        if market["key"] != "h2h":
                            continue
                        observed = instant(market.get("last_update") or book.get("last_update"))
                        if observed > received or observed >= kickoff:
                            raise ValueError("future_quote")
                        outcomes = market["outcomes"]
                        names = [o["name"] for o in outcomes]
                        if len(names) != 3 or len(set(names)) != 3 or set(names) != {raw_home, "Draw", raw_away}:
                            raise ValueError("not_three_way_regulation_h2h")
                        prices = {o["name"]: float(o["price"]) for o in outcomes}
                        odds = [prices[t] for t in (raw_home, "Draw", raw_away)]
                        devig(odds)
                        if not isinstance(book["key"], str) or not book["key"].strip():
                            raise ValueError("missing_bookmaker_key")
                        quotes.append({"bookmaker": book["key"], "bookmaker_title": book["title"],
                                       "observed_at": observed.isoformat(), "odds_1x2": odds})
                    except (ValueError, TypeError, KeyError):
                        rejected.append({"event_id": event_id[1], "bookmaker": book.get("key"),
                                         "reason": "invalid_future_or_non_three_way_market"})
            if quotes:
                fixtures.append({"competition_code": code, "gender": "men", "home_team": home,
                    "away_team": away, "starts_at": kickoff.isoformat(), "quotes": quotes,
                    "provider_event_id": event["id"], "provider_home_team": raw_home,
                    "provider_away_team": raw_away})
            else:
                rejected.append({"event_id": event_id[1], "reason": "no_eligible_three_way_quotes"})
    return {"schema_version": 1, "is_example": is_example,
            "source_url": "https://the-odds-api.com/", "provider": "the_odds_api_v4",
            "snapshot_at": retrieved.isoformat(), "retrieved_at": retrieved.isoformat(),
            "fixtures": fixtures, "rejected": rejected,
            "coverage": {"configured_competitions": sorted({r["competition_code"] for r in records}),
                         "not_configured": ["es.w.1"], "fixture_count": len(fixtures)},
            "timing_note": "Snapshot is the end of sequential acquisition; each quote retains its source timestamp. No claim of a simultaneous bookmaker observation."}
