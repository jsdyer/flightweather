# Flight Weather

Keep airport forecasts on the record, then compare them with later METAR/SPECI observations. An independent static CoolCode tool using NOAA/NWS Aviation Weather Center reports. No account or API key required.

<!-- coolcode:guide -->
Choose an airport and a dated capture, then select a TAF edition. **Saved before observation** shows only outcomes that occurred after this tool had saved that forecast. A new collection can have no such outcomes yet; hourly captures grow the record. **Issued before observation (reconstructed)** can inspect earlier observations but is explicitly labelled retrospective. TEMPO and PROB alternatives stay separate, and BECMG transitions are excluded from deterministic pairing until the next FM period. Save receipt JSON to keep a portable copy.
<!-- /coolcode:guide -->

## Use it

Open [Flight Weather](https://coolcode.ca/flightweather/). The initial collection covers Vancouver (CYVR), Halifax (CYHZ), Victoria (CYYJ) and Abbotsford (CYXX). Search by code/city and switch airport without another API request. The latest retained observation, original raw METAR/SPECI, forecast validity periods and original TAF are visible. Wind speed and numeric ceiling charts keep missing values as gaps. Exact observations and forecast values are also in the comparison table and CSV.

The first capture includes a 24-hour METAR/SPECI backfill and the current TAF for each airport. It does **not** pretend those forecasts were collected before the backfilled observations. Leave the hourly collector running and future observations become eligible for the default comparison. Reconstructed mode is useful for reading the forecast and observed reports together immediately, but is not a pre-captured forecast experiment.

This is a weather evidence explorer, not an operational aviation briefing or flight-planning service.

## Expand or customize

Edit [`web/config.json`](web/config.json). Add an airport to the `airports` array, for example:

```json
{"icao":"CYYZ","label":"Toronto","region":"Ontario"}
```

Every airport requires a unique four-letter uppercase ICAO code and a label; `region` is optional. The UI provides an entry builder under **Add another airport**. Any reporting airport supported by AWC can be added; non-reporting codes or airports without TAFs show explicit gaps. Counts and selectors derive from the record, not four hard-coded defaults. Archived reports from a removed airport are retained until the rolling history expires.

| Setting | Default | Meaning |
| --- | --- | --- |
| `airports` | Four Canadian airports | Airport watchlist; 1–40 airports per collection |
| `defaultAirport` | `CYVR` | Initially selected airport, falling back to an available airport |
| `observationHours` | `24` | METAR/SPECI lookback per collection; 1–48 hours |
| `historyDays` | `90` | Rolling report/capture window; 2–365 days |
| `requestDelaySeconds` | `1` | Pause after each source request; 1–30 seconds |
| `maxAirports` | `40` | Can lower the safety limit; cannot raise it above 40 |

A push changing the config, collector or refresh workflow starts **Flight Weather · Refresh reports**. You can also run it manually in GitHub Actions. Successful refreshes commit `web/data/ledger.json`, then **Flight Weather · Check and publish** tests and deploys the updated site. Ordinary UI/documentation pushes rebuild the existing snapshot without a fresh source fetch. To collect locally:

```sh
python3 scripts/refresh.py
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

The workflow schedule is `17 * * * *` (hourly, UTC). Edit `.github/workflows/refresh.yml` to change cadence. GitHub schedules can be delayed or disabled after inactivity; the UI flags collections over four hours old. A failed fetch or malformed response leaves the last ledger untouched, and a failed refresh does not trigger deployment. A valid empty response is recorded as a coverage gap. A collection returning no observations anywhere fails conservatively.

The public file retains a rolling window; commits in Git preserve older file versions unless repository history is rewritten. Download receipt JSON for an independent copy. **Import receipt JSON** restores a supported collection in this tab only; reload to return to the published record. Current configuration does not invalidate earlier receipts.

## Comparison method

- Reports retain the provider's raw text and decoded fields. Observation time, TAF issue time, TAF validity periods and the tool's first/last capture times are separate.
- A candidate observation must be in the selected TAF's validity interval and occur at or after issue time. Default mode additionally requires observation time **strictly after** first capture. Retrospective mode does not.
- Prevailing BASE/FM groups apply at their encoded start-inclusive/end-exclusive intervals. The latest applicable BASE/FM group is selected. An observation inside an overlapping TEMPO/PROB period keeps that conditional context; the alternative is never substituted for the prevailing group.
- BECMG timing is not deterministic. This implementation conservatively omits the prevailing comparison from the beginning of a BECMG group until a later FM group starts, including its aftermath. It does not silently treat the old forecast as still applicable.
- These are descriptive per-report comparisons, not an overall accuracy grade. Different lead times, amended forecasts, conditional groups and unequal SPECI reporting frequency prevent a simple fair score.
- Wind speed is in knots, direction in true degrees. Calm or variable direction has no angular error. Ceiling is the lowest BKN/OVC layer, or vertical visibility when explicitly reported, in feet above the aerodrome. A missing ceiling or only FEW/SCT is not converted to zero.
- Visibility is in statute miles; the API's `6+` remains `>6`. Lower bounds are never treated as exact values for error scoring. Missing observations and decoded fields remain unavailable.
- Distinct corrected raw/decoded reports retain separate IDs and first capture times. Receipt/ingestion flags do not create duplicates. A first capture does not assert the forecast was unchanged before the tool observed it.

## Source and access

- [AWC Data API and usage restrictions](https://aviationweather.gov/data/api/)
- [Current OpenAPI schema](https://aviationweather.gov/data/schema/openapi.yaml)
- METAR: `/api/data/metar?ids=CYVR&format=json&hours=24`
- TAF: `/api/data/taf?ids=CYVR&format=json` (there is no `hours` query parameter for TAF)

AWC expressly does not permit browser cross-origin API access. GitHub's collector makes bounded server-side HTTPS requests with an identifying User-Agent, and the public page reads only its own saved files. One METAR and one TAF request per configured airport, with pauses, is well below the published 100-request/minute limit. Responses at the 400-record ceiling are rejected rather than silently represented as complete. No private proxy or API key is needed.

NOAA/NWS remains the report source; this is an independent presentation, not an official NOAA service. Follow the source's current usage guidance. Original source requests and capture-level returned counts are retained in the receipt. Terms/guidance reviewed 2026-11-23.

## Privacy and hosting

Airport search, comparison choices, configuration entry building and imported files remain in tab memory. No browser query is sent to AWC. Following an official report link opens that external service. The shared CoolCode counter records aggregate opens, not airport searches or imported reports. There is no persistent local storage and no frontend secret.

Source is in `web/`, collection in `scripts/refresh.py`, pure comparison logic in `web/model.mjs`. The offline build publishes only `dist/` to GitHub Pages at `/flightweather/`. Do not add a CNAME. Tests cover no-lookahead pairing, conditional and BECMG handling, missing values, import validation, expandable configuration and source/capture retention. Browser smoke tests in CI check the actual app at a project subpath and on mobile.
