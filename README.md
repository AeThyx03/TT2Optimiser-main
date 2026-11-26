# Titan Forge · TT2 Player Optimizer

Paste your in-game player JSON to plan skill points and review artifact and monument priorities.

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

In Tap Titans 2, open Settings → Services → Export. Paste the complete JSON, and select Import player. Player data stays in the current session.

Users who paste JSON need **no tokens**. To optionally enable **Connect to TT2**,
the deployment owner sets `TT2_APPLICATION_TOKEN` in Streamlit secrets or the
server environment. For local use, add this top-level entry to
`.streamlit/secrets.toml` (ignored by Git):

```toml
TT2_APPLICATION_TOKEN = "your-application-token"
```

For Streamlit Community Cloud, put this entry in the app's Secrets settings.
Restart the app after configuring it. Without this credential, only JSON import
is shown. The application token is never displayed to visitors. Do not configure
your personal player token on the server or commit either token to Git.

When enabled, each user opens **Connect to TT2**, enters **their own player token**,
and selects **Import from TT2**. Manage player tokens in TT2 → Options → Services
→ Player API Token. The masked player token stays in session memory;
**Forget player token** clears it. Use a trusted deployment: the hosting server
processes the tokens and sends them to GameHive. JSON import remains the default.

The connector authenticates the `/player` Socket.IO namespace over the `/api`
transport path, then calls `POST /player/data` while that connection is open.
It requests skills, artifacts, seasonal artifacts, equipment sets, stage, total SP,
and relic counters, and disconnects after each import. Refresh is manual, with
a two-minute cooldown including failed attempts, and no automatic retries.
GameHive also enforces its limits across sessions and deployments. Errors retain
the previously imported profile. Install the updated requirements and restart
Streamlit when upgrading from a JSON-only version.

API imports do not update the bundled balance tables. The API schema supplies no
game version or season identifier; confirm table compatibility before applying
recommendations. Protocol: [REST specification](https://tt2-docs.gamehivegames.com/rest/openapi.yaml)
and [Socket documentation](https://tt2-docs.gamehivegames.com/socket/).

Choose your goal, damage type, and gold source in the build controls. Use the Skill workshop to plan a full respec or spend available points. The default Skill tree view follows the game’s six class tabs, node positions, prerequisite connections, icons, and optimized level numbers. Select a node for current/planned levels and SP changes. Copy the build JSON back into the game.

Open **Season builds** after importing a profile to compare all six damage types
against your current monuments. The import provides owned IDs, levels, and
enchantment flags. Enter the current primary damage or gold multiplier from
the game and select which builds it applies to. For a conditional effect,
enter the effective multiplier at the intended condition and spell setup.
The comparison uses only the recorded multipliers and assumes they multiply.
Shared All Monument Damage can be omitted because it applies equally to every
build. The push score uses log₁₀ damage plus the selected gold weight times
log₁₀ gold. It measures support from the recorded monuments.

For speed, record runs over the same start and target stages with the same
perks and monument levels. The comparison ranks the median time of completed
runs in that range. GameHive's player API provides inventory and levels.
Record effect values and times from the game. Importing another snapshot
clears the comparison so measurements stay with the levels and season used.

The Relic armory and Season atlas show compact upgrade rows, priorities, and estimated lifetime memento targets. Model explanations and comparison exports are available in expandable panels.

Choose a skill **Optimization goal**:

- **Maximum damage:** scores modeled damage/gold only, with no speed utility reward.
- **Speed:** prioritizes progression utility with damage support (`0.35 × damage/gold score + 3 × speed utility`).
- **Balanced:** gives damage/gold and speed utility equal objective weights (`damage/gold score + speed utility`).

The UI initially enables mana-heavy contracts for Maximum damage and disables them
for Speed/Balanced. Each preset's Advanced options can override this preference.
Lightning Strike's proc budget defaults to 60 attempts for Maximum damage, 3 for
Speed and 15 for Balanced; each preset retains its own override. These are assumed
proc counts, not measured waiting times. Explicit Python `lightning_attempts`
values override the goal default.

Speed utility uses pinned skill effects and diminishing returns
(`4 × log10(1 + effect gain / scale)`) for build-specific skips, attack cadence,
cooldown improvements, spawn opportunities, mana support and spell uptime. Gold
cooldown bonuses are routed to the chosen gold source. The speed breakdown reports
the raw utility gained by category; it does not report seconds or damage multipliers.
These weights are explicit heuristic preferences. The model does not simulate a
full prestige: starting stage, titan density, damage thresholds, mana consumption,
spawn frequencies and player reaction times are absent. Speed cannot guarantee a
fastest prestige, and Balanced is a tradeoff rather than simultaneous independent
maxima. Changing the goal invalidates the displayed skill plan; optimize again.
Spending mode retains owned ranks; every goal enforces SP budgets, stage locks and
prerequisites. Legacy Python callers with `qol=True` use Balanced unless an explicit
`optimization_goal` overrides it. Artifact/monument priorities retain their primary
effect model; these presets choose skill allocations.

Skill planning uses a prerequisite-aware greedy heuristic, not a guaranteed global optimum. Artifact priorities include additive artifact damage, price estimates and affordability. Monuments report primary and shared-damage gains; upgrade-cost rankings are unavailable. Provisional allocation weights exclude off-build monuments. Monument cards show estimated target shares of lifetime investment, while next-level efficiency remains separate in the comparison table. They are not exact spending plans. Skill/artifact tables are pinned to 8.3.0; monument data uses the alternate season matching the supplied screenshots/export. See THIRD_PARTY_NOTICES.md for sources and model limits.

Run tests with `python -m unittest discover -s tests -v`.

Collection primary-effect model: `1 + EffectPerLevel × level^GrowthExpo`. Finite ratios are used up to level 1e12; larger levels use stable log-space derivatives. Game exports' compact `e` enchantment flags are recognized. Artifact prices use `CostCoef × level^CostExpo`, with additive damage `DamageBonus × level`. Monument cost coefficients do not establish the upgrade-cost formula; absolute season/acquisition scaling is unavailable, so no memento price or affordability is reported. Shared All Monument Damage uses the screenshot-matched estimate `DamageBonus ** (level ** DamageExpo)`; displayed percentage magnitudes add a factor of 100. The comparison table includes the finite change in the sum of owned monument damage contributions. Capped/inactive items and off-build/unmodeled monuments are unranked. BoS remains a separate farming decision. Season counters, equipment interactions, full artifact synergies, and the monument L40 column are not fully modeled.

Lifetime monument targets currently use a provisional, cost-independent split proportional to build-relevant `weight × GrowthExpo`. They are not optimized lifetime spending shares: the upgrade-cost formula is unresolved, and the rejected polynomial cost model is no longer used to infer a budget or concentrate investment. Shared damage is reported as a finite change in the complete additive pool, but is excluded from these fallback targets. No monument gain-per-memento priority or relative efficiency is published without a supported upgrade-cost model. Targets sum to 100% across supported, owned, uncapped primary effects; unknown effects remain blank and off-build/capped items get zero. Discovery, enchantment and capped-item spending are excluded. Available mementos are not a lifetime spending denominator.

All 33 supplied monument descriptions are recorded in `data/tt2/monument_descriptions.json`. The player's export confirms Rosabella's Village is ID 6, Mound of Brothers' Meet is ID 27, and Grand Air Chariot is ID 37. `EndgameSeasonArtifactInfo_1.csv` matches the supplied season's effects and growth magnitudes; display names are corrected by screenshots plus export IDs/levels. ID 33 is unverified and excluded. Rosabella, Three Cup Mana Pool, Hideout of Stratagem, Lost Cups Five and Sword Master's Shrine cannot become Heavenly Strike upgrade priorities through cheap shared damage. Active spells can be set under Advanced options for conditional spell boosts and gold/damage per spell. Artifact amplifiers account for owned, build-relevant artifacts. Rankings remain estimates; different season exports require compatible tables.


### Monument cost validation

The October 12 paired exports and eight screenshots add two measured x1000 purchases: Glassbone costs 9.12e71 and Hierophant costs 4.78e71. `measured_session_check()` fits each local geometric price sequence from the single-level and batch quotes, then independently checks the following quote (Glassbone x942 and Hierophant x1000). Errors are approximately 0.20% and 0.10%. This validates a local approximation, not a global cost law or lifetime optimum. With four active spells and gold weight 0.7, the observed Glassbone batch provides about 15.49 times the weighted log gain per memento of the Hierophant batch. The shared-damage pool is counted once, and Hierophant's individual shared damage is not mistaken for an increase to that pool.

The exported `Mementos` field remains 7.259e72 before and after these purchases, whereas the displayed balance falls from 2.42e72 to 1.51e72 to 1.03e72. The UI therefore labels this field **Exported mementos**, not available currency. Exact cumulative spending, current balance and game version cannot be recovered from these two exports alone; their monument levels are also rounded at this magnitude.

The October 9 screenshots show Glassbone at level ~126.33K and 23.95% lifetime mementos, versus Hierophant at ~125.22K and 12.49%. Assuming the same lifetime denominator and unchanged cost modifiers, the observed cumulative investment ratio is 1.918, while the current polynomial cost model predicts 1.029. This contradiction survives rounding allowances. The former concentration solver and gain-per-memento ordering have been removed. Target percentages remain visible as provisional primary-effect allocation weights, not calibrated optimal shares.

The offline `tt2_monument_validation` utility checks this audit and measured purchase JSON. Record `monument`, `level_before`, `level_after`, and `mementos_spent`; optionally include both `damage_before_percent` and `damage_after_percent`. Two independent purchases per monument for at least two monuments permit a local relative-cost consistency check. A fitted common scale alone is not validation: disagreements between purchase scales reject the model. A local pass does not establish global lifetime targets. Do not use predictions as observations. Rounded balance differences can have large relative errors. Evidence and remaining measurements are recorded in `data/tt2/monument_validation_observations.json`.
