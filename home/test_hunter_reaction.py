import uuid
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from .hunter_reaction import panel, use
from .models import TbOperacaoRecurso


class ReactionTests(TestCase):
    def setUp(self):
        from .test_hunter_colony import ColonyHandTests
        ColonyHandTests.setUp(self)
        self.pc.nivel = 6
        self.pc.save()
        self.profile.refresh_from_db()

    def command(self, ability='int', trigger='attack'):
        return dict(character_id=self.person.pk, owner_id=self.user.pk, ability=ability,
            trigger=trigger, confirmed=True, operation_id=str(uuid.uuid4()),
            expected_version=panel(self.profile, ability)['version'])

    def test_post_replay_and_both_rests(self):
        self.assertContains(self.client.get(self.url), 'Usar Resposta Instintiva')
        cmd = self.command()
        response = self.client.post(self.url, dict(action='reaction', reaction_ability='int',
            trigger='attack', confirmed='1', operation_id=cmd['operation_id'],
            resource_version=cmd['expected_version']))
        self.assertEqual(response.status_code, 302)
        result = use(**cmd)
        self.assertEqual(result['current'], 3)
        self.assertEqual(result['movement_feet'], 5)
        self.assertFalse(result['damage_resistance'])
        self.assertEqual(TbOperacaoRecurso.objects.count(), 1)
        for rest in ('curto','longo'):
            self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo':rest})
            self.assertEqual(panel(self.profile,'int')['current'],4)
            self.assertEqual(use(**cmd),result)
            self.assertEqual(panel(self.profile,'int')['current'],4)
            use(**self.command())

    def test_gates_upgrade_and_old_revision(self):
        with self.assertRaises(ValueError): use(**self.command(trigger='save'))
        for level in (5,6,13,14,20):
            self.pc.nivel=level; self.pc.save(); self.profile.refresh_from_db()
            result=panel(self.profile,'int')
            if level==5: self.assertIsNone(result)
            else: self.assertEqual(result['upgraded'],level>=14)
        result=use(**self.command(trigger='save'))
        self.assertEqual(result['movement_feet'],30)
        self.assertTrue(result['damage_resistance'])
        self.assertFalse(result['attack_disadvantage'])
        self.data.pop('swarm_reaction'); self.bind(self.data)
        self.assertIsNone(panel(self.profile,'int'))

    def test_balance_ability_switch_stale_atomic_and_owner(self):
        cmd=self.command()
        with patch('home.hunter_reaction.TbOperacaoRecurso.objects.create',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError): use(**cmd)
        self.assertFalse(self.person.recursos.exists())
        use(**cmd)
        with self.assertRaises(ValueError): use(**self.command(ability='wis'))
        with self.assertRaises(ValueError): use(**dict(cmd,operation_id=str(uuid.uuid4())))
        with self.assertRaises(ValueError): use(**dict(self.command(),confirmed=False))
        for _ in range(3): use(**self.command())
        with self.assertRaises(ValueError): use(**self.command())
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,{'action':'reaction'}).status_code,404)
