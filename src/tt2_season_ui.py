"""Season comparison controls for the player optimiser."""
import math

import pandas as pd
import streamlit as st

from src.tt2_data import BUILDS
from src.tt2_optimizer import scientific_from_log
from src.tt2_season import MonumentEffect, compare_monuments, compare_prestige_times, log_multiplier


def render_season_builds(player, settings):
    st.subheader("Compare builds this season")
    st.caption("Compare monument bonuses at their current levels, then time your best candidates over the same stage range.")
    observations = st.session_state.setdefault(
        "tt2_season_observations", {"effects": {}, "runs": {}},
    )
    effects = observations["effects"]
    owned = {key: level for key, level in player.monuments.items() if level > 0}

    st.markdown("#### Monument power")
    if owned:
        st.caption(
            "Use each monument’s current primary effect in TT2. Enter its effective multiplier "
            "for the builds it boosts, including any active condition or enchantment. "
            "You can skip All Monument Damage because it applies equally to every build."
        )
        with st.expander("Record a monument bonus", expanded=not effects):
            with st.form("season_monument_effect"):
                def monument_label(key):
                    enchanted = " · enchanted" if key in player.monument_enchanted else ""
                    return f"{key} · Lv {owned[key]:g}{enchanted}"

                monument = st.selectbox("Owned monument", list(owned), format_func=monument_label)
                kind = st.radio("Bonus type", ("Damage", "Gold"), horizontal=True, key="season_bonus_type")
                builds = st.multiselect("Builds receiving this bonus", BUILDS)
                value = st.text_input("Current bonus", placeholder="x1.23e400 or +50%", max_chars=48)
                submitted = st.form_submit_button("Save bonus", type="primary")
            if submitted:
                try:
                    if not builds:
                        raise ValueError("Select the builds that receive this bonus.")
                    key = (monument, kind, tuple(build for build in BUILDS if build in builds))
                    if any(
                        existing != key and existing[:2] == key[:2] and set(existing[2]).intersection(builds)
                        for existing in effects
                    ):
                        raise ValueError("A recorded bonus already covers one of these builds. Remove it before changing its build group.")
                    effects[key] = MonumentEffect(monument, key[2], kind, log_multiplier(value))
                except ValueError as error:
                    st.error(str(error))
    else:
        st.info("Import a player with owned monuments to compare their bonuses.")

    if effects:
        rows = compare_monuments(effects.values(), settings.gold_weight)
        leaders = [row[0] for row in rows if math.isclose(row[3], rows[0][3], rel_tol=0, abs_tol=1e-8)]
        recorded = len({effect.monument for effect in effects.values()})
        if len(leaders) == len(BUILDS):
            st.info("The recorded bonuses give all six builds equal monument support.")
        else:
            st.success(f"Best supported by recorded monuments · {', '.join(leaders)}")
        st.caption(
            f"Recorded {recorded} of {len(owned)} owned monuments. "
            f"Push score uses log₁₀ damage plus {settings.gold_weight:g} × log₁₀ gold "
            f"for {settings.gold}. Base damage, equipment, and unrecorded effects can change the winner."
        )
        st.dataframe(pd.DataFrame(
            [(build, scientific_from_log(damage), scientific_from_log(gold), score)
             for build, damage, gold, score in rows],
            columns=["Build", "Damage multiplier", "Gold multiplier", "Push score"],
        ), hide_index=True, column_config={"Push score": st.column_config.NumberColumn(format="%.3f")})
        with st.expander("Review recorded bonuses"):
            saved = st.selectbox(
                "Recorded bonus", list(effects), format_func=lambda key:
                f"{key[0]} · {key[1]} · {', '.join(key[2])} · ×{scientific_from_log(effects[key].log_gain)}",
            )
            if st.button("Remove bonus"):
                del effects[saved]
                st.rerun()
    elif owned:
        st.info("Add a bonus to see which builds the recorded monuments favour.")

    st.markdown("#### Prestige speed")
    st.caption("Time each build over the same start and target stages, with the same perks and monument levels. Repeat runs to reduce the effect of luck.")
    runs = observations["runs"]
    with st.expander("Record a timed run"):
        with st.form("season_prestige_run"):
            start_col, end_col = st.columns(2)
            start = start_col.number_input("Start stage", min_value=1, max_value=999_999_999, value=None)
            end = end_col.number_input("Target stage", min_value=2, max_value=1_000_000_000, value=None)
            build = st.selectbox("Timed build", BUILDS)
            elapsed = st.number_input("Elapsed seconds", min_value=0.1, max_value=86_400.0, value=None, step=0.1)
            add_run = st.form_submit_button("Save timed run")
        if add_run:
            if start is None or end is None or elapsed is None or start >= end:
                st.error("Enter the elapsed time and a target stage above the start stage.")
            else:
                runs.setdefault((start, end), {}).setdefault(build, []).append(elapsed)

    if runs:
        stage_range = st.selectbox(
            "Compare timed runs over", list(runs), format_func=lambda pair: f"{pair[0]:,}–{pair[1]:,}",
        )
        times = compare_prestige_times(runs[stage_range])
        if len(times) >= 2:
            leaders = [build for build, seconds, _ in times if seconds == times[0][1]]
            st.success(f"Fastest measured · {', '.join(leaders)}")
        else:
            st.info("Time another build over this stage range to compare prestige speed.")
        st.dataframe(pd.DataFrame(times, columns=["Build", "Median seconds", "Runs"]), hide_index=True)
        if st.button("Clear runs for this stage range"):
            del runs[stage_range]
            st.rerun()
    else:
        st.info("Save timed runs for at least two builds to identify the fastest measured build.")
