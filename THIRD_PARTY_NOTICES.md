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
- Primary gains use finite ratios for 1 + coefficient × level^growth. Large
  levels use log-space derivatives; imported enchantment multipliers scale the
  primary effect once. Artifact priorities also include additive collection
  damage. Monument comparisons include a screenshot-matched shared-damage curve.
  The former relative cost curve fails the supplied lifetime-share comparison
  and is no longer used for upgrade ordering or budget reconstruction.
  Allocation percentages are provisional weighted primary-effect shares;
  they omit shared-damage allocation until upgrade costs are established. Monument absolute prices and affordability are withheld.
  Conditional counters and synergies remain estimates. Measured upgrade checks
  validate only the observed range, not the global optimum.
- Monument parameters use EndgameSeasonArtifactInfo_1.csv, whose effects and
  growth magnitudes match the supplied 33 screenshots and player export. The
  screenshots/export correct display names: Rosabella's Village = ID 6,
  Mound of Brothers' Meet = ID 27, Grand Air Chariot = ID 37. ID 33 is unverified
  and excluded. Metadata and provenance are in monument_descriptions.json.
  This is a profile for the supplied season, not automatic support for every
  season. The ambiguous L40 column is not used.
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
