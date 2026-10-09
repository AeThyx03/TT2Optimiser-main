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

Skill planning uses a prerequisite-aware greedy heuristic, not a guaranteed global optimum. Artifact and monument priorities are approximate, not exact spending plans. Game tables are pinned to 8.3.0; review version warnings before applying a build. See THIRD_PARTY_NOTICES.md for sources and model limits.

Run tests with `python -m unittest discover -s tests -v`.
