# Titan Forge · TT2 Player Optimizer

Paste your in-game player JSON to plan skill points and review artifact and monument priorities.

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

In Tap Titans 2, open Settings → Services → Export. Paste the complete JSON, and select Import player. Player data stays in the current session.

Choose your goal, damage type, and gold source in the build controls. Use the Skill workshop to plan a full respec or spend available points. The default Skill tree view follows the game’s six class tabs, node positions, prerequisite connections, icons, and optimized level numbers. Select a node for current/planned levels and SP changes. Copy the build JSON back into the game.

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

Skill planning uses a prerequisite-aware greedy heuristic, not a guaranteed global optimum. Artifact priorities include additive artifact damage, price estimates and affordability. Monument priorities include primary gains plus level-exponential shared damage and a relative cost curve; off-build monuments are unranked. Monument cards show estimated target shares of lifetime investment, while next-level efficiency remains separate in the comparison table. They are not exact spending plans. Skill/artifact tables are pinned to 8.3.0; monument data uses the alternate season matching the supplied screenshots/export. See THIRD_PARTY_NOTICES.md for sources and model limits.

Run tests with `python -m unittest discover -s tests -v`.

Collection primary-effect model: `1 + EffectPerLevel × level^GrowthExpo`. Finite ratios are used up to level 1e12; larger levels use stable log-space derivatives. Game exports' compact `e` enchantment flags are recognized. Artifact prices use `CostCoef × level^CostExpo`, with additive damage `DamageBonus × level`. Monument cost coefficients are used only as a relative curve; absolute season/acquisition scaling is unavailable, so no memento price or affordability is reported. Shared All Monument Damage uses the screenshot-matched estimate `DamageBonus ** (level ** DamageExpo)`; displayed percentage magnitudes add a factor of 100. Next-level rankings include the finite change in the sum of owned monument damage contributions. Capped/inactive items and off-build/unmodeled monuments are unranked. BoS remains a separate farming decision. Season counters, equipment interactions, full artifact synergies, and the monument L40 column are not fully modeled.

Lifetime monument targets reconstruct a relative cumulative investment budget from imported levels using `CostCoef / (CostExpo + 1) * level ** (CostExpo + 1)`. Each relevant monument is tested as the dominant shared-damage contributor. Its investment share is optimized against the weighted primary effects of all relevant monuments; remaining investment follows primary-effect marginal power. The highest-scoring candidate supplies the targets. This uses the dominant-term approximation to additive shared damage (appropriate when its exponent is thousands), rather than omitting shared damage or forcing a fixed 80% allocation. Targets change with progression and build, and are rounded to total 100%. Relative costs and the shared-damage curve remain estimates; absolute season/acquisition scaling is unavailable. Discovery, enchantment and capped-item spending are excluded. These are scalable-pool targets, not exact game lifetime shares or instructions to redistribute sunk investments. The export's available mementos are not its lifetime investment denominator. Current shares and exact upgrade counts remain unavailable.

All 33 supplied monument descriptions are recorded in `data/tt2/monument_descriptions.json`. The player's export confirms Rosabella's Village is ID 6, Mound of Brothers' Meet is ID 27, and Grand Air Chariot is ID 37. `EndgameSeasonArtifactInfo_1.csv` matches the supplied season's effects and growth magnitudes; display names are corrected by screenshots plus export IDs/levels. ID 33 is unverified and excluded. Rosabella, Three Cup Mana Pool, Hideout of Stratagem, Lost Cups Five and Sword Master's Shrine cannot become Heavenly Strike upgrade priorities through cheap shared damage. Active spells can be set under Advanced options for conditional spell boosts and gold/damage per spell. Artifact amplifiers account for owned, build-relevant artifacts. Rankings remain estimates; different season exports require compatible tables.
