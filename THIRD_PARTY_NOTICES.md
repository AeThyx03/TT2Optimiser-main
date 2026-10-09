# TT2 Player Optimizer sources

The alchemy application has been retired from this player-only interface.

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
- Artifact/monument priorities use finite next-level ratios for the modeled
  1 + coefficient × level^growth effect, plus additive collection damage. Estimated
  cost uses coefficient × level^cost exponent. Large levels use log-space
  derivatives. Imported enchantment multipliers scale the primary effect once.
  Unmodeled primary effects can rank only for their known collection damage.
  Prices, conditional counters and monument behavior remain estimates, not
  verified live-game spending plans. The ambiguous L40 column is not used.
- Seasonal activity comes from EndgameSeasonArtifactInfo.csv; the `_1` table is
  retained as an upstream alternate snapshot, but is not silently substituted.
- The current upstream table transposes the display names of IDs 6 and 33.
  Catalog names are corrected to Mound of Brothers' Meet (6) and Rosabella's
  Village (33), matching the alternate snapshot's ID/name mapping and the
  supplied in-game screenshot showing Rosabella's companion deadly damage.
  IDs, effect types, growth parameters, costs and activity are unchanged.
- Player data and tokens are never required for offline JSON calculations.

## Artifact formula reference

The finite effect/cost model and additive artifact damage were checked against
TT2Master public source (Apache-2.0), without copying its implementation:
https://github.com/nebula2/tt2-master/blob/main/src/TT2Master/Model/Arti/ArtifactOptimization.cs
and https://github.com/nebula2/tt2-master/blob/main/src/TT2Master.Shared/Models/Artifact.cs.
Monument table parameters are used as an estimate; the older artifact reference
does not verify current monument formulas.

## Collection artwork

85 artifact PNGs were retrieved from TT2Master Android drawable resources at
commit 3837595d662f542b5d8b5b81320eed21fb1a9d9b:
https://github.com/nebula2/tt2-master/tree/3837595d662f542b5d8b5b81320eed21fb1a9d9b/src/TT2Master.Android/Resources/drawable
Game artwork belongs to Game Hive. Missing icons are explicitly labeled as
unavailable; substitute artwork is not presented as the original item image.
