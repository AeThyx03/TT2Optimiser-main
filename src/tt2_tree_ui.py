"""Game-style optimized tree presentation, with live node inspection."""
import json
from pathlib import Path
from src.tt2_data import catalog

CLASSES = (("Knight", "Knight", "#dddddf", "⚔"),
           ("Pet", "Summoner", "#ff782c", "◆"),
           ("Warlord", "Warlord", "#f3ce28", "✦"),
           ("Sorcerer", "Sorcerer", "#4cbbe8", "♨"),
           ("Rogue", "Rogue", "#84c75a", "➶"),
           ("Alchemist", "Alchemist", "#b25aff", "♛"))


def skill_tree_document(levels, current_levels, total_sp, icon_loader):
    skills = catalog()["skills"]
    trees = []
    for key, name, color, symbol in CLASSES:
        nodes = []
        for skill_id, skill in skills.items():
            if skill["Class"] != key:
                continue
            slot = int(skill["Slot"])
            level, current = int(levels.get(skill_id, 0)), int(current_levels.get(skill_id, 0))
            nodes.append(dict(id=skill_id, name=skill["Name"], note=skill["Note"],
                              level=level, current=current, max=skill["max"],
                              cost=skill["costs"][level], delta=skill["costs"][level]-skill["costs"][current],
                              parent=skill["TalentReq"], x=310 if slot == 0 else 130+180*((slot-1)%3),
                              y=80 if slot == 0 else 220+140*((slot-1)//3), icon=icon_loader(skill_id)))
        trees.append(dict(name=name, color=color, symbol=symbol, nodes=nodes,
                          spent=sum(n["cost"] for n in nodes)))
    spent = sum(t["spent"] for t in trees)
    payload = dict(trees=trees, total=total_sp, spent=spent)
    template = (Path(__file__).resolve().parents[1]/"static"/"optimized-tree.html").read_text(encoding="utf-8")
    return template.replace("__TREE_DATA__", json.dumps(payload).replace("<", "\\u003c"))
