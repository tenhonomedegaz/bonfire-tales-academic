import uuid
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from .hunter_preparation import preparation
from .hunter_resources import state, use_secret
from .hunter_rework import prepare, catalog
from .models import TbOperacaoRecurso


class ColonyHandTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.pc.id_subclasse=self.subs['ordem-do-enxame']
        self.pc.nivel=18
        self.pc.save()
        self.profile.refresh_from_db()
        self.person.inteligencia=18
        self.person.save()

    def command(self):
        self.profile.refresh_from_db()
        return dict(character_id=self.person.pk,owner_id=self.user.pk,
            secret_id='mao-da-colonia',enhanced=False,operation_id=str(uuid.uuid4()),
            expected_version=state(self.profile,preparation(self.profile))['version'])

    def test_use_receipt_replay_and_long_rest(self):
        self.assertContains(self.client.get(self.url),'Mão da Colônia')
        cmd=self.command()
        self.assertEqual(self.client.post(self.url, {
            'action': 'use', 'secret': cmd['secret_id'],
            'operation_id': cmd['operation_id'],
            'resource_version': cmd['expected_version'],
        }).status_code, 302)
        response=use_secret(**cmd)
        self.assertEqual((response['spent'],response['current']),(4,14))
        self.assertEqual(response['casting'],dict(spell="Bigby's Hand",circle=6,
            duration_seconds=60,concentration=False,action='action',includes_mage_hand=True,
            ability='int',save_dc=18,spell_attack=10))
        self.assertEqual(use_secret(**cmd),response)
        self.assertEqual(TbOperacaoRecurso.objects.count(),1)
        rest=reverse('personagem_descansar',args=[self.person.pk])
        self.client.post(rest,{'tipo':'curto'})
        self.assertEqual(self.person.recursos.get(chave__startswith='hunter:').atual,14)
        self.client.post(rest,{'tipo':'longo'})
        self.assertEqual(self.person.recursos.get(chave__startswith='hunter:').atual,18)
        use_secret(**cmd)
        self.assertEqual(self.person.recursos.get(chave__startswith='hunter:').atual,18)

    def test_gates_old_revision_no_optional_slot_and_no_upgrade(self):
        for order in catalog()['orders']:
            for level in (17,18,20):
                result=prepare(level=level,ability='int',order=order['id'])
                self.assertEqual(bool(result['exclusive']), level >= 18)
                if level >= 18:
                    self.assertEqual(result['exclusive'][0]['order'], order['id'])
        self.assertNotIn('mao-da-colonia',[s['id'] for s in preparation(self.profile)['options']])
        with self.assertRaises(ValueError):
            use_secret(**dict(self.command(),enhanced=True))
        self.data.pop('exclusive_secrets')
        self.bind(self.data)
        with self.assertRaises(ValueError):use_secret(**self.command())
        self.assertFalse(TbOperacaoRecurso.objects.exists())

    def test_balance_stale_permissions_and_atomic_receipt(self):
        cmd=self.command()
        with patch('home.hunter_resources.TbOperacaoRecurso.objects.create',side_effect=RuntimeError('receipt')):
            with self.assertRaises(RuntimeError):use_secret(**cmd)
        self.assertFalse(self.person.recursos.exists())
        for _ in range(4):use_secret(**self.command())
        with self.assertRaises(ValueError):use_secret(**self.command())
        self.assertEqual(self.person.recursos.get(chave__startswith='hunter:').atual,2)
        with self.assertRaises(ValueError):use_secret(**dict(cmd,operation_id=str(uuid.uuid4())))
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,{'action':'use','secret':'mao-da-colonia'}).status_code,404)
