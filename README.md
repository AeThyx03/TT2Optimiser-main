# TT2 Player Optimizer

Paste your in-game player JSON to plan skill points and review artifact and monument priorities.

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

In Tap Titans 2, open Settings → Services → Export. Paste the complete JSON and select Import player. Player data stays in the current session.

Choose a damage type and gold source, then plan a full respec or spend available points. Optimized ranks appear in a compact six-tree grid. Copy the build JSON back into the game.

Enable **Include QoL skills** to balance the existing damage/gold objective with
prestige speed, idle multi-spawns, mana support and build-specific skips and spell
uptime. Disabled preserves the original scoring. Utility uses pinned skill effects
and explicit diminishing-return weights (`4 × log10(1 + effect gain / scale)`)
in `src/tt2_optimizer.py`. Weights are heuristic preferences, not measured damage
or run times. The model does not simulate mana demand, special-titan frequency,
offline progress or a fastest possible prestige. Spending mode retains owned ranks;
both modes still enforce SP budgets, stage locks and prerequisites.

Skill planning uses a prerequisite-aware greedy heuristic, not a guaranteed global optimum. Artifact priorities include additive artifact damage, price estimates and affordability. Monument priorities use build-relevant primary gains and a relative cost curve; off-build monuments are unranked. They are not exact spending plans. Skill/artifact tables are pinned to 8.3.0; monument data uses the alternate season matching the supplied screenshots/export. See THIRD_PARTY_NOTICES.md for sources and model limits.

Run tests with `python -m unittest discover -s tests -v`.

Collection primary-effect model: `1 + EffectPerLevel × level^GrowthExpo`. Finite ratios are used up to level 1e12; larger levels use stable log-space derivatives. Game exports' compact `e` enchantment flags are recognized. Artifact prices use `CostCoef × level^CostExpo`, with additive damage `DamageBonus × level`. Monument cost coefficients are used only as a relative curve; absolute season/acquisition scaling is unavailable, so no memento price or affordability is reported. Shared All Monument Damage is excluded from upgrade priorities. Capped/inactive items and off-build/unmodeled monuments are unranked. BoS remains a separate farming decision. Season counters, equipment interactions, full artifact synergies, and the monument L40 column are not fully modeled.

All 33 supplied monument descriptions are recorded in `data/tt2/monument_descriptions.json`. The player's export confirms Rosabella's Village is ID 6, Mound of Brothers' Meet is ID 27, and Grand Air Chariot is ID 37. `EndgameSeasonArtifactInfo_1.csv` matches the supplied season's effects and growth magnitudes; display names are corrected by screenshots plus export IDs/levels. ID 33 is unverified and excluded. Rosabella, Three Cup Mana Pool, Hideout of Stratagem, Lost Cups Five and Sword Master's Shrine cannot become Heavenly Strike upgrade priorities through cheap shared damage. Active spells can be set under Advanced options for conditional spell boosts and gold/damage per spell. Artifact amplifiers account for owned, build-relevant artifacts. Rankings remain estimates; different season exports require compatible tables.
