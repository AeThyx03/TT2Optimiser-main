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
from src.tt2_optimizer import Settings, default_spells, optimize_skills, rank_items
from src.tt2_player import ImportError, parse_player


@lru_cache(maxsize=128)
def skill_icon(key):
    """Embed bundled icons so deployment paths cannot break the skill grid."""
    path = Path(__file__).resolve().parents[1] / "static" / "skill-icons" / f"{key}.png"
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


@lru_cache(maxsize=256)
def item_icon(key):
    path = Path(__file__).resolve().parents[1] / "static" / "item-icons" / f"{key}.png"
    if not path.is_file():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def collection_card(row, currency, featured=False):
    name = html.escape(row["Name"])
    icon = item_icon(row["ID"])
    artwork = f'<img src="{icon}" alt="{name}">' if icon else '<span class="item-art-missing">Artwork<br>unavailable</span>'
    priority = row["Priority"]
    badge = "Upgrade first" if featured else f"#{priority}" if priority else row["Status"]
    efficiency = row["Relative efficiency %"]
    efficiency_text = f"{efficiency:g}% of best relative value" if efficiency is not None else "Unranked"
    reason = "Primary effect + collection damage" if row["Status"] == "Ranked (estimate)" else "Build-relevant primary effect" if row["Status"] == "Ranked (primary effect estimate)" else row["Status"]
    available = "Within current balance" if row["Affordable"] is True else "Save more first" if row["Affordable"] is False else "Price not modeled" if row["Next cost (estimate)"] is None else "Balance not provided"
    primary = row["Primary gain log10 (estimate)"]
    primary_text = "Primary effect does not benefit this build / gold source" if primary == "0" else "Primary effect is not modeled" if primary is None else "Primary effect benefits this build / gold source"
    price_text = f'Next level ≈ {row["Next cost (estimate)"]} {currency}' if row["Next cost (estimate)"] else "Next-level price unavailable"
    st.markdown(
        f'<article class="collection-card{ " featured" if featured else ""}">'
        f'<div class="item-art">{artwork}</div><div class="item-body">'
        f'<span class="item-badge">{html.escape(badge)}</span><h4>{name}</h4>'
        f'<div class="item-level">Level {html.escape(row["Level"])}{ " · Enchanted" if row["Enchanted"] else ""}</div>'
        f'<div class="item-reason">{html.escape(row["Effect description"])}</div>'
        f'<div class="item-reason">{primary_text}</div>'
        f'<div class="item-efficiency">{efficiency_text}</div>'
        f'<div class="item-meter"><span style="width:{efficiency or 0}%"></span></div>'
        f'<div class="item-cost">{price_text}</div>'
        f'<div class="item-reason">{html.escape(reason)} · {available if priority else ""}</div>'
        '</div></article>', unsafe_allow_html=True,
    )

def install_player(payload, source):
    player = parse_player(payload, source)
    st.session_state["tt2_player"] = player
    st.session_state.pop("tt2_result", None)


def inventory(player, settings, kind):
    rows = rank_items(player, settings, kind)
    if not rows:
        st.info(f"No {kind} were included in this export. Import a full player export to see them here.")
        return
    currency = "relics" if kind == "artifacts" else "mementos"
    ranked = [r for r in rows if r["Priority"] is not None]
    if kind == "monuments":
        st.caption("Build upgrade priorities use relevant primary effects and a relative cost curve. Off-build monuments stay unranked even if they are cheap. Shared All Monument Damage does not choose upgrades. Exact memento prices and affordability are unavailable.")
        if any(r["Status"] == "Effect needs compatible season data" for r in rows):
            st.info("Your screenshots correct several effects that differ from the bundled season table. Those entries show their in-game descriptions, but stay unranked until compatible growth and cost data are available.")
    if ranked:
        best = ranked[0]
        collection_card(best, currency, featured=True)
        if kind == "monuments":
            st.info(f"Focus upgrades on {best['Name']} first for {settings.build} / {settings.gold}. Compare value per memento, rather than matching monument levels. Re-import after upgrades to see when another monument becomes the better choice.")
        else:
            st.caption(f"Best next upgrade for {settings.build} / {settings.gold}: {best['Name']}.")
        if best["Affordable"] is False:
            next_affordable = next((r for r in ranked if r["Affordable"] is True), None)
            if next_affordable:
                st.caption(f"Best value needs more {currency}. Best affordable alternative: {next_affordable['Name']} (#{next_affordable['Priority']}).")
            else:
                st.caption(f"Your current balance cannot buy a ranked next level. Save more {currency}.")
    else:
        st.info("No upgrade can be ranked from this collection: check caps, season activity and supported effects.")
    st.caption("Relative value = modeled primary gain divided by the snapshot's cost curve. Absolute prices are unavailable. Your build, gold source and active spells determine relevance; season counters remain fixed." if kind == "monuments" else "Upgrade value = modeled next-level gain per currency spent, including shared artifact damage. Primary effects use your selected build and gold source. These are estimates; conditional effects remain fixed.")
    search = st.text_input(f"Search {kind}", key=f"search_{kind}", placeholder="Name, effect, or ID")
    only = st.checkbox("Show ranked upgrades only", key=f"ranked_{kind}")
    if kind == "monuments":
        # Clear an old checked filter from sessions created before prices were
        # withheld, so a disabled control cannot hide every monument.
        st.session_state["affordable_monuments"] = False
    affordable = st.checkbox("Show affordable upgrades only", key=f"affordable_{kind}", disabled=kind == "monuments" or player.relics is None)
    visible = [r for r in rows if (not only or r["Priority"] is not None) and (not affordable or r["Affordable"] is True) and search.lower() in (r["Name"] + r["Effect"] + r["ID"]).lower()]
    display = [{field: r[field] for field in ("Priority", "Name", "Level", "Relative efficiency %", "Next cost (estimate)", "Affordable", "Gain log10 (estimate)", "Primary gain log10 (estimate)", "Collection gain log10 (estimate)", "Enchanted", "Status", "Effect", "ID")} for r in visible]
    if not visible:
        st.info("No items match these filters.")
    for start in range(0, len(visible), 2):
        columns = st.columns(2)
        for col, row in zip(columns, visible[start:start + 2]):
            with col:
                collection_card(row, currency)
    with st.expander("Compare upgrade numbers"):
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
      .skill-board {max-width:540px;margin:1rem auto;background:#131820;padding:8px;border:1px solid #45505e;border-radius:14px;overflow:hidden}
      .skill-summary {background:#202731;color:#f5d685;text-align:center;padding:12px 3px;margin-bottom:8px;border-radius:8px;font:600 clamp(13px,3vw,18px) sans-serif;border-bottom:1px solid #46505c}
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
    theme = Path(__file__).resolve().parents[1] / "static" / "player-ui.css"
    css = theme.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    data = catalog()
    st.markdown('<div class="eyebrow"><span class="brand-sigil">⚔</span> TAP TITANS 2 <span class="brand-tag">BUILD LAB</span></div>', unsafe_allow_html=True)
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

    qol = st.toggle("Include QoL skills", value=False, key="include_qol", help="Balance damage with prestige speed, idle support and mana. Uses approximate utility weights, not a run-time simulation.")
    if qol:
        st.caption("Speed + damage: considers Cloaking, multi-spawns, mana, spell uptime and skips for your build. These compete for SP; fastest runs and maximum damage cannot both be guaranteed.")

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
            spell_names = {"BurstDamage":"Heavenly Strike", "CritBoost":"Deadly Strike", "HandOfMidas":"Hand of Midas", "TapBoost":"Fire Sword", "HelperBoost":"War Cry", "ShadowClone":"Shadow Clone", "DualPet":"Dual Summon", "StreamOfBlades":"Blade Stream", "ThunderVolley":"Thunder Ship", "TwilightFairy":"Twilight Fairies", "GoldenMissile":"Golden Missile"}
            active_spells = st.multiselect("Active spells for monument scoring", list(data["spell_reductions"]), default=list(default_spells(build)), max_selections=4, format_func=spell_names.get, key=f"monument_spells_{build}", help="Choose the spells active during your run. This controls spell boosts, Portal of Shadows, and damage/gold per activated spell.")
    settings = Settings(build, gold, weight, contracts, attempts, qol=qol, active_spells=tuple(active_spells))

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
    skills_tab, artifact_tab, monument_tab = st.tabs(["Skills", "Artifacts", "Monuments"])
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
            if qol:
                st.caption(f"QoL utility gain: +{result['utility_gain']:.3f} · combined damage + utility objective. Utility is not extra damage or a predicted run time.")
            render_skill_tree(result["levels"], player.skills)
            export = {
                "Version": data["version"],
                "Skills": {key: str(level) for key, level in result["levels"].items() if level > 0},
            }
            build_json = json.dumps(export, separators=(",", ":"))
            copy_col, _ = st.columns([1, 3])
            with copy_col:
                components.html(f"""
                  <button id="copy-build" style="background:#e9b949;color:#171b23;border:1px solid #f7d477;border-radius:9px;padding:10px 16px;font:600 14px sans-serif;cursor:pointer;width:100%">Copy build JSON</button>
                  <span id="copy-status" role="status" style="display:block;color:#71d7ba;font:12px sans-serif;padding-top:4px"></span>
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
    with artifact_tab:
        st.subheader("Your artifact priorities")
        st.caption(f"Available relics: {player.relics:.4E}" if player.relics is not None else "Available relics were not included in this export.")
        inventory(player, settings, "artifacts")
        st.info("Book of Shadows is kept separate: its relic-farming value depends on your prestige and tournament goals.")
    with monument_tab:
        st.subheader("Your seasonal monuments")
        st.caption(f"Available mementos: {player.mementos:.4E}" if player.mementos is not None else "Available mementos were not included in this export.")
        st.caption("Monument season data matches your supplied screenshots and export. Live season counters and equipment interactions are not fully simulated; use Advanced options to set your active spells.")
        inventory(player, settings, "monuments")
