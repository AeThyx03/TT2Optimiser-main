"""Player optimizer interface shared by standalone and multipage entrypoints."""
import json
import html

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.tt2_data import BUILDS, GOLD_SOURCES, catalog, table
from src.tt2_optimizer import Settings, optimize_skills, rank_items, validate_allocation
from src.tt2_player import ImportError, parse_player

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
      .skill-summary {display:flex;flex-wrap:wrap;justify-content:center;gap:.55rem;margin:.5rem 0 1rem}
      .skill-summary span {padding:.45rem .75rem;background:#303238;border:1px solid #ffffff25;border-radius:7px;font-weight:650}
      .skill-tree-grid {display:grid;grid-template-columns:repeat(3,minmax(230px,1fr));gap:.8rem;align-items:start}
      .skill-class {--tree:#999;background:#25272b;border:1px solid #ffffff25;border-radius:8px;overflow:hidden;min-width:0}
      .skill-class-head {display:flex;align-items:center;justify-content:space-between;padding:.5rem .65rem;background:var(--tree);color:#17191c;font-weight:750;border-bottom:2px solid #111}
      .skill-class-head small {font-size:.78rem;font-weight:650;opacity:.85}
      .skill-nodes {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:2px;background:#111;padding:2px}
      .skill-node {height:84px;position:relative;display:flex;flex-direction:column;justify-content:space-between;padding:.35rem;background-color:color-mix(in srgb,var(--tree) 24%,#17191c);background-size:cover;background-position:center;color:#fff;text-shadow:0 1px 2px #000;overflow:hidden}
      .skill-node.empty {opacity:.42}
      .skill-node-name {position:absolute;left:0;right:0;bottom:0;padding:.2rem .24rem;background:#101216b8;font-size:.58rem;line-height:1.1;font-weight:650;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
      .skill-node-level {position:absolute;inset:0;display:grid;place-items:center;font-size:1.65rem;font-weight:900;line-height:1;color:#fff;-webkit-text-stroke:1px #151515;text-shadow:2px 2px 2px #111,0 0 4px #111;pointer-events:none}
      .skill-node-current {position:absolute;right:.2rem;top:.2rem;font-size:.57rem;background:#111d;padding:.08rem .2rem;border-radius:3px;color:#f2f2f2;z-index:1}
      @media(max-width:900px){.skill-tree-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:560px){.skill-tree-grid{grid-template-columns:1fr}.skill-node{height:74px}}
    </style>""", unsafe_allow_html=True)
    sp_by_class = {}
    for key, level in levels.items():
        skill = skills[key]
        sp_by_class[skill["Class"]] = sp_by_class.get(skill["Class"], 0) + skill["costs"][level]
    total_sp = sum(sp_by_class.values())
    st.markdown(
        '<div class="skill-summary">'
        f'<span>Planned: {total_sp:,} SP</span>'
        f'<span>Current: {sum(skills[k]["costs"][v] for k, v in current_levels.items()):,} SP</span>'
        f'<span>Remaining: {max(0, int(st.session_state.get("tt2_player").total_sp) - total_sp):,} SP</span>'
        '</div>', unsafe_allow_html=True,
    )
    panels = []
    for class_key, label, short, color in classes:
        rows = sorted((s for s in skills.values() if s["Class"] == class_key), key=lambda s: int(s["Slot"]))
        class_sp = sp_by_class.get(class_key, 0)
        nodes = []
        for skill in rows:
            key = skill["TalentID"]
            level = int(levels.get(key, 0))
            current = int(current_levels.get(key, 0))
            name = html.escape(skill["Name"])
            title = html.escape(f'{skill["Name"]} · current {current} → planned {level} · max {skill["max"]}')
            current_badge = f'<span class="skill-node-current">{current} →</span>' if current != level else ""
            nodes.append(
                f'<div class="skill-node{" empty" if not level else ""}" title="{title}" '
                f'style="--tree:{color};background-image:linear-gradient(rgba(14,15,18,.38),rgba(14,15,18,.48)),url(\'/app/static/skill-icons/{key}.png\')">'
                f'<span class="skill-node-name">{name}</span>'
                f'{current_badge}'
                f'<span class="skill-node-level">{level}</span></div>'
            )
        panels.append(
            f'<section class="skill-class" style="--tree:{color}"><header class="skill-class-head">'
            f'<span>{short} · {html.escape(label)}</span><small>{class_sp:,} SP</small></header>'
            f'<div class="skill-nodes">{"".join(nodes)}</div></section>'
        )
    st.markdown(f'<div class="skill-tree-grid">{"".join(panels)}</div>', unsafe_allow_html=True)


def render():
    st.set_page_config(page_title="TT2 · Player Optimizer", page_icon="⚔️", layout="wide")
    st.markdown("""<style>
      .block-container {max-width:1280px;padding-top:1.45rem;padding-bottom:3rem;padding-left:clamp(1rem,3vw,2.5rem);padding-right:clamp(1rem,3vw,2.5rem);}
      h1 {letter-spacing:-.045em;text-align:center;margin:.25rem 0 .2rem;font-size:clamp(2rem,4vw,3rem);}
      .eyebrow {font-size:.76rem;letter-spacing:.16em;font-weight:800;color:#91a0ff;text-align:center;text-transform:uppercase;}
      .hero-subtitle {text-align:center;color:#c4c6ce;margin:0 0 1.35rem;font-size:1.02rem;}
      [data-testid="stAppViewContainer"] {background:linear-gradient(180deg,#292b30 0%,#24262a 45%,#202226 100%);}
      [data-testid="stHeader"] {background:#202226;}
      [data-testid="stMetric"] {background:#2d3035;border:1px solid #ffffff20;border-radius:10px;padding:16px;}
      [data-testid="stMetricLabel"] {font-size:.85rem;}
      [data-testid="stSidebar"] {background:#202226;border-right:1px solid #ffffff18;}
      [data-testid="stButton"] button,[data-testid="stDownloadButton"] button {border-radius:8px;border-color:#ffffff30;}
      [data-testid="stButton"] button[kind="primary"] {background:#5f73e8;border-color:#5f73e8;}
      div[data-testid="stTabs"] button {font-weight:600;}
      .st-key-player_metrics [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
      .st-key-player_metrics [data-testid="stColumn"] {min-width:135px;flex:1 1 135px;}
      [data-testid="stMetricValue"] {font-size:1.65rem;}
      .st-key-reference_inputs {max-width:940px;margin:.2rem auto 1rem;padding:1rem 1.2rem;border:1px solid #ffffff20;border-radius:14px;background:linear-gradient(145deg,#30333a,#282a30);box-shadow:0 14px 35px #0002;}
      .st-key-reference_inputs h3 {margin:.1rem 0 .7rem;text-align:left;}
      .st-key-reference_inputs [data-testid="stWidgetLabel"] p {color:#e4e7ee;font-weight:650;}
      .st-key-reference_inputs [data-testid="stExpander"] {margin-top:.8rem;background:#25272b;border:1px solid #ffffff20;border-radius:10px;}
      .st-key-player_import {max-width:940px;margin:.2rem auto 1.4rem;padding:1.1rem 1.2rem 1rem;border:1px solid #ffffff20;border-radius:14px;background:#2b2e34;box-shadow:0 12px 30px #0002;}
      .st-key-player_import h3 {margin:.05rem 0 .15rem;}
      .st-key-player_import [data-testid="stTextArea"] textarea {font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.82rem;background:#202226;border-color:#ffffff26;}
      .st-key-player_import form button {width:100%;min-height:2.8rem;font-weight:700;}
      [data-testid="stExpander"] {border-color:#ffffff24;border-radius:10px;}
      [data-testid="stDataFrame"] {border:1px solid #ffffff1c;border-radius:8px;overflow:hidden;}
    </style>""", unsafe_allow_html=True)
    data = catalog()
    st.markdown('<div class="eyebrow">TAP TITANS 2 / BUILD WORKSHOP</div>', unsafe_allow_html=True)
    st.title("Skill Tree Optimizer")
    st.markdown('<p class="hero-subtitle">Paste your in-game export, choose your build, and plan your next skill upgrades.</p>', unsafe_allow_html=True)
    with st.sidebar:
        st.header("TT2 Optimizer")
        st.caption("Skill points, artifacts, and seasonal monuments in one planner.")
        st.divider()
        st.caption(f"Game tables · {data['version']} snapshot")
        st.caption("Player data stays in this session.")
        if "tt2_player" in st.session_state and st.button("Clear imported player", width="stretch"):
            for key in ("tt2_player", "tt2_result", "json_input"):
                st.session_state.pop(key, None)
            st.rerun()

    with st.container(key="player_import"):
        st.subheader("Paste player JSON")
        st.caption("In Tap Titans 2, open Settings → Services → Export, then paste the complete JSON export here. Your import stays in this browser session.")
        with st.form("player_json_import", clear_on_submit=False):
            raw = st.text_area("Player JSON", key="json_input", height=135, placeholder='Paste the full export, for example: {"Version":"8.3.0", ...}')
            submitted = st.form_submit_button("Import player", type="primary")
        if submitted:
            try:
                install_player(raw, "Pasted JSON")
                st.rerun()
            except ImportError as e:
                st.error(str(e))

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
    skills_tab, artifact_tab, monument_tab, event_tab, about_tab = st.tabs(["Skill planner", "Artifacts", "Seasonal monuments", "Event breakpoints", "Data & method"])
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
    with event_tab:
        st.subheader("Historical event thresholds")
        st.caption("From tt2_breakpoints. These are event-currency percentile thresholds, not skill-tree breakpoints or live targets.")
        history = table("breakpoints.csv")
        events = [r for r in history if r.get("holiday_event_id")]
        event = st.selectbox("Event snapshot", list(reversed([r["holiday_event_id"] for r in events])))
        row = next(r for r in reversed(events) if r["holiday_event_id"] == event)
        currency = st.number_input("Your event currency", min_value=0, value=0, step=100)
        cols = st.columns(3)
        for col, key, name in zip(cols, ("0.8", "0.3", "0.1"), ("Top 80%", "Top 30%", "Top 10%")):
            try:
                threshold = int(row[key])
                col.metric(name, f"{threshold:,}")
                col.caption(f"{max(0, threshold - currency):,} currency to this historical threshold")
            except (ValueError, TypeError):
                col.metric(name, "Unavailable")
    with about_tab:
        st.subheader("Traceable data. Explicit assumptions.")
        st.write(f"Bundled game version: **{data['version']}**. The app works offline after installation. No claim is made that this snapshot matches the latest live game.")
        for repo, commit in data["sources"].items():
            st.markdown(f"[{repo} · {commit[:8]}](https://github.com/rawrzcookie/{repo}/tree/{commit})")
        st.write("Skill costs use Co0 for level 1, cumulative rank costs, parent-skill requirements, lower-tier SP gates and stage unlocks. Scores use build reductions, gold weighting, owned multicast/mythic equipment and selected Lightning Strike assumptions. The engine searches multi-level packages greedily; it does not guarantee the best possible allocation.")
        st.write("Artifact and monument rankings use an asymptotic marginal-efficiency estimate: weight × GrowthExpo / (ln(10) × CostCoef × level^(CostExpo + 1)). Unmodeled effects, inactive monuments, unknown IDs and capped items are displayed without fabricated priorities. This model does not predict exact upgrade levels, damage, or prestige time.")
        st.markdown("Formula adaptations and reduction tables credit [rawrzcookie's MIT optimizer](https://github.com/rawrzcookie/rawrzcookie.github.io). See THIRD_PARTY_NOTICES.md for provenance and limitations.")
