"""Audit abandoned/cancelled matches separately from pending sporting results."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from quantfootball.data.competitions import GENDERS
from quantfootball.market.snapshots import instant, key


class SportingStatusLookup:
    def __init__(self, folder=None):
        self.excluded = {}
        if folder is None:
            return
        paths = sorted(Path(folder).glob("*-es.*-*.json"))
        if not paths:
            raise ValueError("No public league status snapshots found.")
        slugs = {"es.1": "laliga-easports", "es.2": "laliga-hypermotion", "es.w.1": "futbol-femenino"}
        for path in paths:
            match = re.fullmatch(r"(\d{4})-(es\.1|es\.2|es\.w\.1)-(\d{2})\.json", path.name)
            if not match:
                raise ValueError("Invalid league snapshot name.")
            year, code, week = match.groups()
            source = json.loads(path.read_text(encoding="utf-8"))
            captured = instant(source["fetched_at"])
            season = f"{year}-{str(int(year) + 1)[-2:]}"
            url = urlsplit(source["source_url"])
            if (url.scheme != "https" or url.hostname != "www.laliga.com"
                    or url.path != f"/{slugs[code]}/resultados/{season}/jornada-{int(week)}"
                    or source["season"] != season or source["matchday"] != int(week)
                    or captured > datetime.now(UTC)):
                raise ValueError("Inconsistent public sporting status provenance.")
            for row in source["matches"]:
                if row["status"] not in ("Abandoned", "Cancelled"):
                    continue
                kickoff = instant(row["date"])
                if row["status"] == "Abandoned" and captured < kickoff:
                    raise ValueError("An abandoned match cannot be observed before kickoff.")
                fixture = {"competition_code": code, "gender": GENDERS[code],
                           "home_team": row["home_team"], "away_team": row["away_team"]}
                date = kickoff.astimezone(ZoneInfo("Europe/Madrid")).date().isoformat()
                identity = (*key(fixture), date)
                if identity in self.excluded:
                    raise ValueError("Overlapping non-sporting status snapshots.")
                self.excluded[identity] = {**fixture, "date": date, "status": row["status"],
                    "reason": "No completed sporting result; awarded Quiniela sign is separate",
                    "kickoff": kickoff.isoformat(), "captured_at": captured.isoformat(),
                    "source_url": source["source_url"], "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def find(self, fixture, registered_at):
        row = self.excluded.get((*key(fixture), fixture["date"][:10]))
        if row and instant(row["kickoff"]) <= registered_at:
            raise ValueError("Excluded match started before its frozen prediction.")
        return row
