import json
import unittest
from src.tt2_tree_ui import skill_tree_document


class SkillTreePresentationTests(unittest.TestCase):
    def test_game_slots_levels_and_point_totals(self):
        document = skill_tree_document({'TapDmg': 3, 'TwilightBell': 2}, {'TapDmg': 1}, 500, lambda key: 'icon:'+key)
        payload = json.loads(document.split('const data=', 1)[1].split(';\nconst nav=', 1)[0])
        self.assertEqual(len(payload['trees']), 6)
        knight = payload['trees'][0]
        nodes = {n['id']: n for n in knight['nodes']}
        self.assertEqual((nodes['TapDmg']['x'], nodes['TapDmg']['y']), (310, 80))
        self.assertEqual((nodes['TwilightBell']['x'], nodes['TwilightBell']['y']), (310, 640))
        self.assertEqual(nodes['TwilightBell']['parent'], 'BurstDamageMultiCastSkill')
        self.assertEqual(nodes['TapDmg']['level'], 3)
        self.assertEqual(nodes['TapDmg']['current'], 1)
        self.assertEqual(knight['spent'], sum(n['cost'] for n in nodes.values()))
        self.assertEqual(payload['spent'], knight['spent'])
        self.assertEqual(payload['total'], 500)
        self.assertTrue(any(n['level'] == 0 for n in nodes.values()))
