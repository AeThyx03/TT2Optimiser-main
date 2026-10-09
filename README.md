# TT2 Player Optimizer

Paste your in-game player JSON to plan skill points and review artifact and monument priorities.

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

In Tap Titans 2, open Settings → Services → Export. Paste the complete JSON and select Import player. Player data stays in the current session.

Choose a damage type and gold source, then plan a full respec or spend available points. Optimized ranks appear in a compact six-tree grid. Copy the build JSON back into the game.

Skill planning uses a prerequisite-aware greedy heuristic, not a guaranteed global optimum. Artifact and monument priorities are approximate, not exact spending plans. Game tables are pinned to 8.3.0; review version warnings before applying a build. See THIRD_PARTY_NOTICES.md for sources and model limits.

Run tests with `python -m unittest discover -s tests -v`.
