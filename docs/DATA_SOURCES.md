# Quant Football — Data Sources Registry

No source is approved until coverage, cost, licence/terms and reproducibility are reviewed.

## QF-DATA-001 — OpenFootball España / football.json

- **Status:** approved for V0 historical match results
- **Cost:** €0
- **Coverage:** Spain, including Primera División / LaLiga and Segunda División
- **Historical depth:** multi-season historical coverage; current-season files are also maintained
- **Format:** Football.TXT upstream; generated JSON available without API key
- **Fields of interest:** season, round/matchday, date, home team, away team, full-time score
- **Licence:** CC0 / public domain
- **Commercial constraint:** none stated in the CC0/public-domain licence
- **Known issues:** limited depth compared with commercial event providers; team naming and update quality still need validation
- **Use in Quant Football:** canonical V0 source for reproducible historical LaLiga results

References:
- https://github.com/openfootball/espana
- https://github.com/openfootball/football.json

## QF-DATA-002 — football-data.org

- **Status:** approved as candidate operational API
- **Cost:** €0 free tier
- **Coverage:** LaLiga included in free tier
- **Rate limit:** 10 calls/minute on free plan
- **Fields of interest:** fixtures, results, schedules, league tables
- **Historical depth:** free plan is primarily basic/current competition access; deeper history is part of paid ML plans
- **Licence / terms:** governed by football-data.org Terms & Conditions
- **Known issues:** free tier is not sufficient by itself for the historical training corpus
- **Use in Quant Football:** future fixtures / current-season operational updates, subject to implementation testing

References:
- https://www.football-data.org/coverage
- https://www.football-data.org/pricing
- https://www.football-data.org/documentation/api

## QF-DATA-003 — Football-Data.co.uk

- **Status:** research-only candidate; not approved as product core
- **Cost:** €0
- **Coverage:** long historical LaLiga results, match stats and bookmaker odds
- **Historical depth:** extensive; European season archives reach back to the 1990s
- **Fields of interest:** results, match statistics, opening/closing 1X2 odds, totals, Asian handicap
- **Licence / commercial constraints:** site states that free use is intended for private individuals only and excludes commercial or data-training products using automated bots/scrapers/AI
- **Known issues:** licensing is incompatible with using it as the long-term production backbone if Quant Football becomes commercial
- **Use in Quant Football:** optional private research/benchmarking only unless explicit permission/licensing is obtained

Reference:
- https://www.football-data.co.uk/data.php

## V0 decision

For the first Quant Football dataset:

1. Use **OpenFootball CC0** as the historical LaLiga results backbone.
2. Validate current/future fixtures with **football-data.org**.
3. Do not make Football-Data.co.uk a hard dependency of the product.
4. Keep odds/market data as a separate later data problem (QF-M5).

## Next validation tasks

- inspect OpenFootball LaLiga schema and season naming
- verify earliest usable season
- test team-name consistency across seasons
- check missing/duplicated fixtures
- define canonical Quant Football match schema
- implement reproducible ingestion into Parquet
