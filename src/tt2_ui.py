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
from src.tt2_optimizer import GOAL_LIGHTNING_ATTEMPTS, Settings, default_spells, optimize_skills, rank_items
from src.tt2_player import ImportError, parse_player


@lru_cache(maxsize=128)
def skill_icon(key):
    """Embed bundled skill icons independently of deployment paths."""
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
    artwork = f'<div class="item-art"><img src="{icon}" alt="{name}"></div>' if icon else ""
    priority = row["Priority"]
    status = "Not recommended" if row["Status"] == "Not recommended for this build / gold source" else row["Status"]
    badge = "Upgrade first" if featured else f"#{priority}" if priority else status
    percentage = row["Relative efficiency %"]
    value_text = f"{percentage:g}% relative efficiency" if percentage is not None else "Unranked"
    price = row["Next cost (estimate)"]
    cost_text = f'<div class="item-cost">Next level ≈ {price} {currency}</div>' if price else ""
    if currency == "mementos":
        percentage = row["Target lifetime mementos % (estimate)"]
        value_text = f"{percentage:.2f}% target of lifetime mementos" if percentage is not None else "Target unavailable"
        cost_text = ""
    st.markdown(
        f'<article class="collection-card{ " featured" if featured else ""}{ " unranked" if priority is None else ""}">'
        f'{artwork}<div class="item-body">'
        f'<span class="item-badge">{html.escape(badge)}</span><h4>{name}</h4>'
        f'<div class="item-level">Level {html.escape(row["Level"])}{ " · Enchanted" if row["Enchanted"] else ""}</div>'
        f'</div><div class="item-value"><div class="item-efficiency">{value_text}</div>'
        f'<div class="item-meter"><span style="width:{percentage or 0}%"></span></div>'
        f'{cost_text}</div></article>', unsafe_allow_html=True,
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
        st.caption("Estimated lifetime allocation · 100% total")
        with st.expander("How to reach your lifetime targets"):
            st.markdown("Compare each target with **% of lifetime Mementos** in the game's Monument Info. A 20% target means roughly one fifth of your lifetime investment should go to that monument. Add investment to monuments below their targets as you earn more mementos; a 0% target means no additional investment for this build. Your existing investment cannot be reduced by upgrading.")
            st.caption("Estimates use effect and cumulative cost growth; discovery, enchantment, capped-item spending and shared collection damage are excluded. Current lifetime shares and exact target levels are unavailable in this export. Available mementos are separate from lifetime investment.")
        if any(r["Status"] == "Effect needs compatible season data" for r in rows):
            st.info("Some effects need compatible season data before they can be ranked.")
    if ranked:
        best = ranked[0]
        collection_card(best, currency, featured=True)
        if best["Affordable"] is False:
            next_affordable = next((r for r in ranked if r["Affordable"] is True), None)
            if next_affordable:
                st.caption(f"Best value needs more {currency}. Best affordable alternative: {next_affordable['Name']} (#{next_affordable['Priority']}).")
            else:
                st.caption(f"Your current balance cannot buy a ranked next level. Save more {currency}.")
    else:
        st.info("No upgrade can be ranked from this collection: check caps, season activity and supported effects.")
    visible = rows
    display = [{field: r[field] for field in ("Priority", "Name", "Level", "Relative efficiency %", "Next cost (estimate)", "Affordable", "Gain log10 (estimate)", "Primary gain log10 (estimate)", "Collection gain log10 (estimate)", "Enchanted", "Status", "Effect", "ID")} for r in visible]
    if kind == "monuments":
        for record, row in zip(display, visible):
            record["Target lifetime mementos % (estimate)"] = row["Target lifetime mementos % (estimate)"]
            record["Effect description"] = row["Effect description"]
            record["Next-level efficiency % of best"] = record.pop("Relative efficiency %")
    # The featured recommendation is already visible above the collection.
    card_rows = [r for r in visible if not ranked or r["ID"] != ranked[0]["ID"]]
    for row in card_rows:
        collection_card(row, currency)
    with st.expander("Compare upgrade numbers"):
        st.dataframe(pd.DataFrame(display), hide_index=True, width="stretch")
        st.download_button(f"Download {kind} priorities", pd.DataFrame(display).to_csv(index=False), f"tt2-{kind}.csv", "text/csv", key=f"download_{kind}")


def render_skill_tree(levels, current_levels):
    from src.tt2_tree_ui import skill_tree_document
    components.html(skill_tree_document(levels, current_levels, st.session_state["tt2_player"].total_sp, skill_icon), height=920, scrolling=True)


@st.dialog("Privacy Policy")
def privacy_policy():
    st.caption("Tap Titans 2 Optimizer · Last updated October 9, 2026")
    st.markdown("""
This policy describes how the current version of Tap Titans 2 Optimizer, created by Aethyx, handles your data. This is an unofficial community tool.

### 1. Information you provide
The app processes the player JSON you import, your selected settings, and the resulting optimization plans to calculate recommendations. Only import your game export; do not include passwords or other sensitive information.

### 2. Processing and storage
Calculations run on the computer or server hosting the app. When you use a hosted version, your inputs are sent to that server for processing; they are not processed solely in your browser.

The current optimizer keeps imported data and settings in temporary session memory. It does not intentionally save player exports to a database or file. Downloaded plans and copied build JSON remain wherever you choose to save or paste them.

### 3. Third-party services
The current interface does not integrate Google Analytics, Google AdSense, or Ko-fi. Streamlit usage statistics are disabled in the app configuration. A hosting provider may process connection information, such as IP addresses and access logs, under its own policies.

### 4. Your choices
You can use the app without importing data, although optimization requires a player export. Select **Clear imported player** under **Replace player JSON** to remove the imported profile, pasted JSON, and saved plan from the active session. This does not delete files you downloaded or copies you saved elsewhere.

### 5. Changes
This policy will be updated if the app adds persistent storage, analytics, advertising, or other data-processing services.
""")


def render_footer():
    with st.container(key="app_footer"):
        st.markdown('<footer class="creator-credit">Created by Aethyx · Unofficial community tool</footer>', unsafe_allow_html=True)
        if st.button("Privacy", key="privacy_link"):
            privacy_policy()


def render():
    st.set_page_config(page_title="Tap Titans 2 Optimizer", page_icon="⚔️", layout="wide")
    theme = Path(__file__).resolve().parents[1] / "static" / "player-ui.css"
    css = theme.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    st.markdown('<header class="app-title"><span class="title-emblem" aria-hidden="true">⚔</span><h1>Tap Titans 2 <span>Optimizer</span></h1></header>', unsafe_allow_html=True)
    data = catalog()
    player = st.session_state.get("tt2_player")
    player = st.session_state.get("tt2_player")
    with st.expander("Replace player JSON" if player else "Paste player JSON", expanded=not bool(player)):
        if player and st.button("Clear imported player"):
            for key in ("tt2_player", "tt2_result", "json_input"):
                st.session_state.pop(key, None)
            st.rerun()
        st.caption("TT2 → Settings → Services → Export. Paste the full JSON below.")
        with st.form("player_json_import", clear_on_submit=False):
            raw = st.text_area("Player JSON", key="json_input", height=180, placeholder='Paste the full export, for example: {"Version":"8.3.0", ...}')
            submitted = st.form_submit_button("Import player", type="primary", width="stretch")
        if submitted:
            try:
                install_player(raw, "Pasted JSON")
                st.rerun()
            except ImportError as e:
                st.error(str(e))

    if player:
        with st.container(key="reference_inputs"):
            goal_labels = {"Maximum damage": "push", "Speed": "speed", "Balanced": "balanced"}
            goal_label = st.radio("Optimization goal", list(goal_labels), horizontal=True, key="optimization_goal")
            goal = goal_labels[goal_label]
            build_col, gold_col = st.columns(2)
            build = build_col.selectbox("Damage type", BUILDS)
            gold = gold_col.selectbox("Gold type", GOLD_SOURCES)
            with st.expander("Advanced options"):
                weight = st.slider("Gold weighting", 0.0, 1.0, .7, .05, help="Gold is converted into modeled pushing value with this exponent.")
                contracts = st.checkbox("Include mana-heavy contracts", value=goal == "push", key=f"contracts_{goal}")
                attempts = st.number_input("Lightning Strike attempts per titan", 0, 1000, GOAL_LIGHTNING_ATTEMPTS[goal], key=f"lightning_attempts_{goal}", help="Preset proc budget: Push 60, Speed 3, Balanced 15. Override to match your play. This is not elapsed time.")
                spell_names = {"BurstDamage":"Heavenly Strike", "CritBoost":"Deadly Strike", "HandOfMidas":"Hand of Midas", "TapBoost":"Fire Sword", "HelperBoost":"War Cry", "ShadowClone":"Shadow Clone", "DualPet":"Dual Summon", "StreamOfBlades":"Blade Stream", "ThunderVolley":"Thunder Ship", "TwilightFairy":"Twilight Fairies", "GoldenMissile":"Golden Missile"}
                active_spells = st.multiselect("Active spells for monument scoring", list(data["spell_reductions"]), default=list(default_spells(build)), max_selections=4, format_func=spell_names.get, key=f"monument_spells_{build}", help="Choose the spells active during your run. This controls spell boosts, Portal of Shadows, and damage/gold per activated spell.")
    if not player:
        render_footer()
        return
    settings = Settings(build, gold, weight, contracts, attempts, active_spells=tuple(active_spells), optimization_goal=goal)

    player = st.session_state.get("tt2_player")
    if not player:
        st.info("Paste your full in-game export above to see your skill points, skill plan, artifacts, and seasonal monuments.")
        return

    st.markdown(f'<div class="profile-line"><div><h2>{html.escape(build)} <span>/ {html.escape(gold)}</span></h2></div><div class="stage-marker"><small>MAX STAGE</small><strong>{player.max_stage:,}</strong></div></div>', unsafe_allow_html=True)
    for message in player.warnings:
        st.warning(message)
    with st.container(key="player_metrics"):
        cols = st.columns(2)
        cols[0].metric("Total SP", f"{player.total_sp:,}")
        cols[1].metric("Available SP", f"{player.available_sp:,}" if player.skills_known else "Unknown")
        spent_text = f"{player.spent_sp:,}" if player.skills_known else "Unknown"
        st.markdown(f'<div class="secondary-stats"><span>Spent <strong>{spent_text}</strong></span><span>Artifacts <strong>{sum(v > 0 for v in player.artifacts.values())}</strong></span><span>Monuments <strong>{sum(v > 0 for v in player.monuments.values())}</strong></span></div>', unsafe_allow_html=True)
    skills_tab, artifact_tab, monument_tab = st.tabs(["Skills", "Artifacts", "Monuments"])
    with skills_tab:
        c1, c2 = st.columns([3, 1])
        mode_label = c1.radio("Planning mode", ["Full respec", "Spend available points"], horizontal=True)
        mode = "respec" if mode_label == "Full respec" else "spend"
        limit = player.total_sp if mode == "respec" else player.available_sp
        reserve = c2.number_input("Keep SP unspent", min_value=0, max_value=max(0, limit), value=0, step=1, key=f"reserve_{mode}")
        if mode == "respec":
            st.caption("Reset your skill tree in-game to apply a full respec.")
        fingerprint = (repr(player), settings, mode, reserve)
        if st.button("Optimize build", type="primary", key="optimize_build", width="stretch", disabled=mode == "spend" and not player.skills_known):
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
            st.caption(f"{goal_label} · Damage/gold gain: +{result['log_gain']:.3f} log10")
            if settings.objective_weights[1] > 0:
                st.caption(f"Speed utility gain: +{result['utility_gain']:.3f} · estimated")
            render_skill_tree(result["levels"], player.skills)
            if settings.objective_weights[1] > 0:
                with st.expander("Speed breakdown"):
                    st.dataframe(pd.DataFrame([{"Factor": k, "Utility gain": round(v, 3)} for k, v in result["speed_components"].items() if v > 0]), hide_index=True, width="stretch")
            export = {
                "Version": data["version"],
                "Skills": {key: str(level) for key, level in result["levels"].items() if level > 0},
            }
            build_json = json.dumps(export, separators=(",", ":"))
            copy_col, _ = st.columns([1, 3])
            with copy_col:
                components.html(f"""
                  <button id="copy-build" style="background:#bca1ff;color:#181122;border:1px solid #bca1ff;border-radius:9px;padding:10px 16px;font:600 14px sans-serif;cursor:pointer;width:100%">Copy build JSON</button>
                  <span id="copy-status" role="status" style="display:block;color:#bca1ff;font:12px sans-serif;padding-top:4px"></span>
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
        st.caption(f"Available relics: {player.relics:.4E}" if player.relics is not None else "Available relics were not included in this export.")
        inventory(player, settings, "artifacts")
        with st.expander("Artifact model details"):
            st.caption("Estimated next-level value includes primary effects and shared damage. Book of Shadows is a separate farming decision.")
    with monument_tab:
        st.caption(f"Available mementos: {player.mementos:.4E}" if player.mementos is not None else "Available mementos were not included in this export.")
        inventory(player, settings, "monuments")
    render_footer()
