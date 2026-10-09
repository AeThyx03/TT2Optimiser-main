"""Player optimizer interface shared by standalone and multipage entrypoints."""
import json
import html
import base64
from functools import lru_cache
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.tt2_data import BUILDS, GOLD_SOURCES, catalog
from src.tt2_optimizer import Settings, optimize_skills, rank_items, validate_allocation
from src.tt2_player import ImportError, parse_player


@lru_cache(maxsize=128)
def skill_icon(key):
    """Embed bundled icons so deployment paths cannot break the skill grid."""
    path = Path(__file__).resolve().parents[1] / "static" / "skill-icons" / f"{key}.png"
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")

def install_player(payload, source):
    player = parse_player(payload, source)
    st.session_state["tt2_player"] = player
    st.session_state.pop("tt2_result", None)


def inventory(player, settings, kind):
    rows = rank_items(player, settings, kind)
    if not rows:
        st.info(f"No {kind} were included in this export. Import a full player export to see them here.")
        return
    st.caption("Approximate upgrade priorities use your owned levels, the selected build and gold source, and the snapshot's growth and cost exponents. These are relative priorities, not exact prices or a relic spending plan. Conditional effects, enchantment changes and total artifact damage interactions are not simulated.")
    search = st.text_input(f"Search {kind}", key=f"search_{kind}", placeholder="Name, effect, or ID")
    only = st.checkbox("Show ranked upgrades only", key=f"ranked_{kind}")
    visible = [r for r in rows if (not only or r["Priority"] is not None) and search.lower() in (r["Name"] + r["Effect"] + r["ID"]).lower()]
    display = [{"Priority": r["Priority"], "Name": r["Name"], "Level": r["Level"], "Status": r["Status"], "Effect": r["Effect"], "ID": r["ID"]} for r in visible]
    st.dataframe(pd.DataFrame(display), hide_index=True, width="stretch")
    st.download_button(f"Download {kind} priorities", pd.DataFrame(display).to_csv(index=False), f"tt2-{kind}.csv", "text/csv", key=f"download_{kind}")


def render_skill_tree(levels, current_levels):
    """Render the planned allocation in a compact, color-coded TT2 tree layout."""
    classes = [
        ("Knight", "Knight", "K", "#a6a4a2"),
        ("Pet", "Summoner", "Su", "#e56870"),
        ("Warlord", "Warlord", "W", "#ffdc6a"),
        ("Sorcerer", "Sorcerer", "So", "#77a5e9"),
        ("Rogue", "Rogue", "R", "#92c47f"),
        ("Alchemist", "Alchemist", "A", "#9984d0"),
    ]
    skills = catalog()["skills"]
    st.markdown("""<style>
      .skill-board {max-width:540px;margin:1rem auto;background:#17191c;padding:2px;border:2px solid #111;border-radius:6px;overflow:hidden}
      .skill-summary {background:#d3d3d3;color:#111;text-align:center;padding:9px 3px;font:500 clamp(13px,3vw,20px) sans-serif;border-bottom:2px solid #111}
      .skill-tree-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:2px}
      .skill-class {min-width:0;--tree:#999}
      .skill-class-head {display:grid;grid-template-columns:1fr 2fr;gap:2px;margin-bottom:2px;color:#111;font:500 clamp(13px,3vw,21px) sans-serif}
      .skill-class-head span {background:var(--tree);text-align:center;padding:8px 0;border-radius:5px}
      .skill-nodes {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:2px;background:#17191c}
      .skill-node {aspect-ratio:1;position:relative;background:var(--tree);border-radius:5px;overflow:hidden}
      .skill-node img {width:100%;height:100%;object-fit:cover;display:block}
      .skill-node.empty img {opacity:.25}
      .skill-node-level {position:absolute;inset:0;display:grid;place-items:center;font:bold clamp(16px,4.6vw,29px) Arial,sans-serif;color:white;-webkit-text-stroke:1px #111;paint-order:stroke fill;text-shadow:2px 2px 1px #000,-2px -2px 1px #000,2px -2px 1px #000,-2px 2px 1px #000}
    </style>""", unsafe_allow_html=True)
    sp_by_class = {}
    for key, level in levels.items():
        skill = skills[key]
        sp_by_class[skill["Class"]] = sp_by_class.get(skill["Class"], 0) + skill["costs"][level]
    total_sp = sum(sp_by_class.values())
    available = st.session_state["tt2_player"].total_sp
    summary = f'{total_sp} / {available} ({available - total_sp} SP remaining)'
    panels = []
    for class_key, label, short, color in classes:
        rows = sorted((s for s in skills.values() if s["Class"] == class_key), key=lambda s: int(s["Slot"]))
        class_sp = sp_by_class.get(class_key, 0)
        nodes = []
        by_slot = {1 if int(skill["Slot"]) == 0 else int(skill["Slot"]) + 2: skill for skill in rows}
        for slot in range(15):
            skill = by_slot.get(slot)
            if skill is None:
                nodes.append('<div class="skill-node" aria-hidden="true"></div>')
                continue
            key = skill["TalentID"]
            level = int(levels.get(key, 0))
            current = int(current_levels.get(key, 0))
            name = html.escape(skill["Name"])
            title = html.escape(f'{skill["Name"]} · current {current} → planned {level} · max {skill["max"]}')
            rank = f'<span class="skill-node-level">{level}</span>' if level else ""
            nodes.append(
                f'<div class="skill-node{ " empty" if not level else ""}" title="{title}" aria-label="{title}">'
                f'<img src="{skill_icon(key)}" alt="{name}">'
                f'{rank}</div>'
            )
        panels.append(
            f'<section class="skill-class" style="--tree:{color}"><header class="skill-class-head">'
            f'<span title="{html.escape(label)}">{short}</span><span>{class_sp}</span></header>'
            f'<div class="skill-nodes">{"".join(nodes)}</div></section>'
        )
    st.markdown(f'<div class="skill-board"><div class="skill-summary">{summary}</div><div class="skill-tree-grid">{"".join(panels)}</div></div>', unsafe_allow_html=True)


def render():
    st.set_page_config(page_title="TT2 · Player Optimizer", page_icon="⚔️", layout="wide")
    st.markdown("""<style>
      .block-container {max-width:1120px;padding-top:1.45rem;padding-bottom:3rem;padding-left:clamp(1rem,3vw,2.5rem);padding-right:clamp(1rem,3vw,2.5rem);}
      h1 {letter-spacing:-.045em;text-align:left;margin:.25rem 0 .2rem;font-size:clamp(2rem,4vw,3rem);}
      .eyebrow {font-size:.76rem;letter-spacing:.16em;font-weight:800;color:#91a0ff;text-align:left;text-transform:uppercase;}
      .hero-subtitle {text-align:left;color:#c4c6ce;margin:0 0 1.35rem;font-size:1.02rem;}
      [data-testid="stAppViewContainer"] {background:radial-gradient(ellipse at top left,#202b43 0%,#111827 55%,#0f172a 100%);}
      [data-testid="stHeader"] {background:#202226;}
      [data-testid="stMetric"] {background:#182235;border:1px solid #ffffff20;border-radius:10px;padding:16px;}
      [data-testid="stMetricLabel"] {font-size:.85rem;}
      [data-testid="stSidebar"] {background:#202226;border-right:1px solid #ffffff18;}
      [data-testid="stButton"] button,[data-testid="stDownloadButton"] button {border-radius:8px;border-color:#ffffff30;}
      [data-testid="stButton"] button[kind="primary"] {background:#5f73e8;border-color:#5f73e8;}
      div[data-testid="stTabs"] button {font-weight:600;}
      .st-key-player_metrics [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
      .st-key-player_metrics [data-testid="stColumn"] {min-width:135px;flex:1 1 135px;}
      [data-testid="stMetricValue"] {font-size:1.65rem;}
      .st-key-reference_inputs {max-width:1120px;margin:.2rem auto 1rem;padding:1rem 1.2rem;border:1px solid #ffffff20;border-radius:14px;background:#182235;box-shadow:0 14px 35px #0002;}
      .st-key-reference_inputs h3 {margin:.1rem 0 .7rem;text-align:left;}
      .st-key-reference_inputs [data-testid="stWidgetLabel"] p {color:#e4e7ee;font-weight:650;}
      .st-key-reference_inputs [data-testid="stExpander"] {margin-top:.8rem;background:#25272b;border:1px solid #ffffff20;border-radius:10px;}
      .st-key-player_import {max-width:1120px;margin:.2rem auto 1.4rem;padding:1.1rem 1.2rem 1rem;border:1px solid #ffffff20;border-radius:14px;background:#2b2e34;box-shadow:0 12px 30px #0002;}
      .st-key-player_import h3 {margin:.05rem 0 .15rem;}
      .st-key-player_import [data-testid="stTextArea"] textarea {font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.82rem;background:#202226;border-color:#ffffff26;}
      .st-key-player_import form button {width:100%;min-height:2.8rem;font-weight:700;}
      [data-testid="stExpander"] {border-color:#ffffff24;border-radius:10px;}
      [data-testid="stDataFrame"] {border:1px solid #ffffff1c;border-radius:8px;overflow:hidden;}
    </style>""", unsafe_allow_html=True)
    data = catalog()
    st.markdown('<div class="eyebrow">TAP TITANS 2</div>', unsafe_allow_html=True)
    st.title("Player optimizer")
    st.markdown('<p class="hero-subtitle">Paste your in-game export, choose your build, and plan your next skill upgrades.</p>', unsafe_allow_html=True)
    player = st.session_state.get("tt2_player")
    if player and st.button("Clear imported player"):
        for key in ("tt2_player", "tt2_result", "json_input"):
            st.session_state.pop(key, None)
        st.rerun()
    with st.expander("Replace player JSON" if player else "Paste player JSON", expanded=not bool(player)):
        st.caption("In Tap Titans 2, open Settings → Services → Export, then paste the complete JSON export here. Your import stays in this browser session.")
        with st.form("player_json_import", clear_on_submit=False):
            raw = st.text_area("Player JSON", key="json_input", height=180, placeholder='Paste the full export, for example: {"Version":"8.3.0", ...}')
            submitted = st.form_submit_button("Import player", type="primary", width="stretch")
        if submitted:
            try:
                install_player(raw, "Pasted JSON")
                st.rerun()
            except ImportError as e:
                st.error(str(e))

    if not player:
        st.caption(f"Game tables {data['version']} · Player data stays in this session")
        return

    with st.container(key="reference_inputs"):
        st.subheader("Build settings")
        build_col, gold_col = st.columns(2)
        build = build_col.selectbox("Damage type", BUILDS)
        gold = gold_col.selectbox("Gold type", GOLD_SOURCES)
        with st.expander("Advanced options"):
            weight = st.slider("Gold weighting", 0.0, 1.0, .7, .05, help="Gold is converted into modeled pushing value with this exponent.")
            contracts = st.checkbox("Include mana-heavy contracts", value=False)
            attempts = st.number_input("Lightning Strike attempts per titan", 0, 1000, 60, help="Model assumption; adjust to match your attack rate and time to kill.")
    settings = Settings(build, gold, weight, contracts, attempts)

    player = st.session_state.get("tt2_player")
    if not player:
        st.info("Paste your full in-game export above to see your skill points, skill plan, artifacts, and seasonal monuments.")
        return

    st.subheader(player.name)
    st.caption(f"{player.source} · Max prestige stage {player.max_stage:,} · {build} / {gold}")
    for message in player.warnings:
        st.warning(message)
    with st.container(key="player_metrics"):
        cols = st.columns(5)
        cols[0].metric("Total skill points", f"{player.total_sp:,}")
        cols[1].metric("Spent", f"{player.spent_sp:,}" if player.skills_known else "Unknown")
        cols[2].metric("Available", f"{player.available_sp:,}" if player.skills_known else "Unknown")
        cols[3].metric("Artifacts owned", sum(v > 0 for v in player.artifacts.values()))
        cols[4].metric("Monuments owned", sum(v > 0 for v in player.monuments.values()))
    skills_tab, artifact_tab, monument_tab, about_tab = st.tabs(["Skills", "Artifacts", "Monuments", "Data & method"])
    with skills_tab:
        st.subheader("Plan your allocation")
        st.caption("A prerequisite-aware heuristic ranks multi-level upgrades by modeled gain per SP. It is not a guaranteed global optimum. Mana, prestige speed and active play assumptions still need your judgment.")
        c1, c2 = st.columns([3, 1])
        mode_label = c1.radio("Planning mode", ["Full respec", "Spend available points"], horizontal=True)
        mode = "respec" if mode_label == "Full respec" else "spend"
        limit = player.total_sp if mode == "respec" else player.available_sp
        reserve = c2.number_input("Keep SP unspent", min_value=0, max_value=max(0, limit), value=0, step=1, key=f"reserve_{mode}")
        if mode == "respec":
            st.caption("Full respec reallocates your total SP; applying it in-game requires a skill-tree reset. Reserve points for mana and utility skills you want to choose manually.")
        fingerprint = (repr(player), settings, mode, reserve)
        if st.button("Optimize skill points", type="primary", disabled=mode == "spend" and not player.skills_known):
            try:
                with st.spinner("Comparing upgrades and their prerequisites…"):
                    result = optimize_skills(player, settings, mode, reserve)
                st.session_state["tt2_result"] = (fingerprint, result)
            except ValueError as e:
                st.error(str(e))
        saved = st.session_state.get("tt2_result")
        if saved and saved[0] != fingerprint:
            st.info("Your inputs changed. Optimize again to refresh the plan.")
            saved = None
        if saved:
            result = saved[1]
            st.success(f"Valid plan · {result['spent']:,} SP allocated · {result['remaining']:,} SP unspent")
            if result["remaining"] > reserve:
                st.caption("Remaining points cannot buy another positively scored package within the selected constraints. They can be saved or used for utility skills.")
            st.caption(f"Modeled gain: +{result['log_gain']:.3f} log10 · {build} / {gold}")
            render_skill_tree(result["levels"], player.skills)
            allocation = [{"Tree": s["Class"], "Skill": s["Name"], "Current": player.skills.get(k, 0), "Planned": result["levels"].get(k, 0), "Change": result["levels"].get(k, 0) - player.skills.get(k, 0), "Planned SP": s["costs"][result["levels"].get(k, 0)]}
                          for k, s in data["skills"].items() if result["levels"].get(k, 0) or player.skills.get(k, 0)]
            with st.expander("Detailed skill allocation"):
                st.dataframe(pd.DataFrame(allocation), hide_index=True, width="stretch")
            export = {
                "Version": data["version"],
                "Skills": {key: str(level) for key, level in result["levels"].items() if level > 0},
            }
            build_json = json.dumps(export, separators=(",", ":"))
            copy_col, download_col, _ = st.columns([1, 1.4, 3])
            with copy_col:
                components.html(f"""
                  <button id="copy-build" style="background:#6276ee;color:white;border:0;border-radius:7px;padding:10px 16px;font:600 14px sans-serif;cursor:pointer;width:100%">Copy build JSON</button>
                  <span id="copy-status" role="status" style="display:block;color:#91bf7f;font:12px sans-serif;padding-top:4px"></span>
                  <script>
                    const buildText = {json.dumps(build_json)};
                    const button = document.getElementById('copy-build');
                    const status = document.getElementById('copy-status');
                    button.addEventListener('click', async () => {{
                      try {{
                        await navigator.clipboard.writeText(buildText);
                      }} catch (error) {{
                        const field = document.createElement('textarea');
                        field.value = buildText;
                        field.setAttribute('readonly', '');
                        field.style.position = 'fixed';
                        field.style.left = '-9999px';
                        document.body.appendChild(field);
                        field.select();
                        const copied = document.execCommand('copy');
                        field.remove();
                        if (!copied) throw error;
                      }}
                      status.textContent = 'Copied — paste into Tap Titans 2';
                    }});
                  </script>
                """, height=54, scrolling=False)
            with download_col:
                st.download_button("Download build JSON", build_json, "tt2-skill-build.json", "application/json", width="stretch")
            with st.expander("Preview game-ready JSON"):
                st.code(build_json, language="json")
            with st.expander("Upgrade sequence and prerequisite packages"):
                st.dataframe(pd.DataFrame(result["steps"]), hide_index=True, width="stretch")
        with st.expander("Current skill allocation"):
            if player.skills_known:
                errors = validate_allocation(player.skills, player.max_stage)
                for error in errors:
                    st.warning(error)
                st.dataframe(pd.DataFrame([{"Skill": data["skills"][k]["Name"], "Level": v, "Spent SP": data["skills"][k]["costs"][v]} for k, v in player.skills.items()]), hide_index=True, width="stretch")
            else:
                st.info("Current skill allocation was not included.")
    with artifact_tab:
        st.subheader("Your artifact priorities")
        st.caption(f"Available relics: {player.relics:.4E}" if player.relics is not None else "Available relics were not included in this export.")
        inventory(player, settings, "artifacts")
        st.info("Book of Shadows is kept separate: its relic-farming value depends on your prestige and tournament goals.")
    with monument_tab:
        st.subheader("Your seasonal monuments")
        st.caption(f"Available mementos: {player.mementos:.4E}" if player.mementos is not None else "Available mementos were not included in this export.")
        st.warning("Season activity and scaling come from the pinned snapshot, not a live season check. Conditional monument effects are held constant in the approximate ranking.")
        inventory(player, settings, "monuments")
    with about_tab:
        st.subheader("Traceable data. Explicit assumptions.")
        st.write(f"Bundled game version: **{data['version']}**. The app works offline after installation. No claim is made that this snapshot matches the latest live game.")
        for repo, commit in data["sources"].items():
            st.markdown(f"[{repo} · {commit[:8]}](https://github.com/rawrzcookie/{repo}/tree/{commit})")
        st.write("Skill costs use Co0 for level 1, cumulative rank costs, parent-skill requirements, lower-tier SP gates and stage unlocks. Scores use build reductions, gold weighting, owned multicast/mythic equipment and selected Lightning Strike assumptions. The engine searches multi-level packages greedily; it does not guarantee the best possible allocation.")
        st.write("Artifact and monument rankings use an asymptotic marginal-efficiency estimate: weight × GrowthExpo / (ln(10) × CostCoef × level^(CostExpo + 1)). Unmodeled effects, inactive monuments, unknown IDs and capped items are displayed without fabricated priorities. This model does not predict exact upgrade levels, damage, or prestige time.")
        st.markdown("Formula adaptations and reduction tables credit [rawrzcookie's MIT optimizer](https://github.com/rawrzcookie/rawrzcookie.github.io). See THIRD_PARTY_NOTICES.md for provenance and limitations.")
