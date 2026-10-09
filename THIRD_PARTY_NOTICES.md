# TT2 Player Optimizer sources

The existing Alchemy application retains its original license and behavior.

## rawrzcookie.github.io

The build reduction tables, spell tables, adapted skill effect formulas and
skill tree icons are from https://github.com/rawrzcookie/rawrzcookie.github.io
(MIT).
The full copyright and license notice is preserved in
`data/tt2/RAWRZCOOKIE_LICENSE.txt`. The exact source commit is recorded in
`data/tt2/sources.json`. The new Python allocation search is a separate greedy
heuristic, not a port of the upstream allocation algorithm.

## TT2_CSV

CSV game tables are from https://github.com/rawrzcookie/TT2_CSV, pinned in
`data/tt2/sources.json`. The source commit was updated October 6, 2026 and
includes current equipment tables. Its `UpdateInfo.csv` still identifies 7.20.0;
the optimizer's game-version label is set to 8.3.0 separately because that
upstream version marker has not caught up.
The repository does not declare a separate license for these game tables.
Game names and data belong to their respective owners. This project is an
unofficial companion and is not affiliated with GameHive.

## tt2_breakpoints

Historical event currency thresholds are from
https://github.com/rawrzcookie/tt2_breakpoints, pinned in `sources.json`.
No separate license is declared by that repository. Its bot code is not bundled
or run by this application. Thresholds are historical, not live targets.

## API contract

Official reference: https://tt2-docs.gamehivegames.com/ and its REST documentation.
The request shape (POST /player/data, API-Authenticate header, player_token and
properties body) was also checked against the provider implementation at
https://github.com/SilicalNZ/TapTitans2py/blob/master/tap_titans/providers/rest_api.py.
No provider source code is copied into this application.

## Model limits

- Skill recommendations are deterministic greedy multi-level packages. Costs,
  parent skills, lower-tier SP thresholds, level caps and stage locks are checked.
  Global optimality is not guaranteed.
- The score uses log-space effect ratios, build reductions, configurable gold
  weighting, selected equipment sets and a user-specified Lightning Strike
  attempt count. Extra spell-level effects assume base spell caps of 30, or 35
  with The Fallen Angel. It does not model mana sustain, prestige speed, every
  artifact/monument interaction, or in-game timing.
- Artifact/monument priorities use the explicit asymptotic model documented in
  the UI. They are not exact purchase costs, a spending plan, or damage predictions.
  Unmodeled effects and unknown IDs are kept visible without invented rankings.
- Seasonal activity comes from EndgameSeasonArtifactInfo.csv; the `_1` table is
  retained as an upstream alternate snapshot, but is not silently substituted.
- Player data and tokens are never required for offline JSON calculations.
