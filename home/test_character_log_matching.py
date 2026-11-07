import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from .character_log_matching import candidates_for, reward_for


class MatchingPolicyTests(unittest.TestCase):
    def quest(self, **kwargs):
        values = dict(name='A longa jornada perdida', questMaster='123456789012345678',
            questDate=datetime(2026, 8, 30, 15, tzinfo=timezone.utc), endDate=None,
            rewardAventurasOverride=2, timeEvents=[])
        values.update(kwargs)
        return SimpleNamespace(**values)

    def test_exact_and_fuzzy_requirements(self):
        q = self.quest()
        entry = {'title': q.name, 'date': None, 'master': ''}
        self.assertEqual(candidates_for(entry, [q], []), [q])
        entry.update(title='A longa jornada perdida!', date='2026-08-30', master='Mestre Historico')
        entry['title'] = 'A longa jornada perdidas'
        aliases = [('Mestre Historico', q.questMaster)]
        self.assertEqual(candidates_for(entry, [q], aliases), [q])
        self.assertEqual(candidates_for(entry, [q], []), [])
        entry['date'] = '2026-09-30'
        self.assertEqual(candidates_for(entry, [q], aliases), [])

    def test_bot_priority_boost_and_no_double_boost(self):
        entry = {'adventures': 4, 'declared_rewards': {'boost_spent': 'Sim'}}
        self.assertEqual(reward_for(entry, self.quest(), None)[0], 4)
        self.assertEqual(reward_for(entry, self.quest(), {'rewardAmount': 4})[0], 4)
        entry['declared_rewards'] = {}
        self.assertEqual(reward_for(entry, self.quest(), None)[0], 2)

    def test_duration_rounding_requires_report_and_near_next_stage(self):
        def timed(minutes):
            from datetime import timedelta
            start = datetime(2026, 8, 30, 15, tzinfo=timezone.utc)
            return self.quest(rewardAventurasOverride=None, timeEvents=[
                {'eventType': 'run', 'date': start.isoformat()},
                {'eventType': 'finish', 'date': (start + timedelta(minutes=minutes)).isoformat()}])
        entry = {'adventures': 2}
        self.assertEqual(reward_for(entry, timed(280), None)[0], 2)
        self.assertTrue(reward_for(entry, timed(280), None)[1]['rounded'])
        self.assertEqual(reward_for(entry, timed(279), None)[0], 1)
        entry['adventures'] = 1
        self.assertEqual(reward_for(entry, timed(280), None)[0], 1)
        self.assertIsNone(reward_for(entry, self.quest(rewardAventurasOverride=None), None)[0])
