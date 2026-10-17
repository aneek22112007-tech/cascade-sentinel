# Sources

Every numeric figure in this repository is **synthetic** (`provenance: 'synthetic'`).
District names (Rajpur, Kalinagar) are fictional archetypes structured on
published north-India heat–agriculture–labour–health cascade patterns, not
copied from any real district's statistics.

Day-one forecast fields that should hold India Meteorological Department (IMD)
values are stored as `"TODO_REAL_VALUE"` with a synthetic fallback used at
runtime. Do not treat the shipped `tmax_c` / `anomaly_c` numbers as IMD
observations.

## Where to replace TODO_REAL_VALUE

| Field | What to fetch | Portal |
| --- | --- | --- |
| `tmax_c`, `anomaly_c`, `duration_days` for May 2024 and May 2025 heatwaves | IMD heatwave bulletins and press releases (max temp, departure from normal, duration) | https://mausam.imd.gov.in/ and https://internal.imd.gov.in/pages/press_release_mausam.php |
| Health outcome observations | IDSP / NCDC weekly outbreak reports (heat-stress illness, acute diarrhoeal disease) | https://idsp.mohfw.gov.in/ |
| Mandi prices (fodder, wheat, milk) | Agmarknet arrivals and modal prices | https://agmarknet.gov.in/ |
| National / regional food-security context | FAO GIEWS country briefs for India | https://www.fao.org/giews/countrybrief/country.jsp?code=IND |

`(:Source)` nodes with `provenance: 'real'` are catalog entries for these
portals. They contain **no copied figures** — only title, URL, and access note.

Synthetic corridor weights, elasticities, episode outcomes, and intervention
trial counts were chosen so the double-run backtest is deterministic and the
designed roles (act / defeated precedent / UNPRECEDENTED / cool-shelter flip)
hold. They are not estimates of any real programme's success rate.
