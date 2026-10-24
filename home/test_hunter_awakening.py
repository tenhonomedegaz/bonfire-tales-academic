import json
import uuid
from io import StringIO

from django.core.management import call_command
from django.urls import reverse

from .hunter_awakening import command, on_marked_prey_death, panel
from .hunter_catalog import compose_order_revision
from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemClasse, TbPersonagemCacador
from .models import TbTalento, TbPersonagemTalento
from .test_criador import _CriadorBase
from .test_hunter_catalog import HunterCatalogTests


class HunterAwakeningTests(_CriadorBase):
    setup_catalog = HunterCatalogTests.setup_catalog

    def setUp(self):
        self.setup_catalog()
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        order_ids = json.loads(output.getvalue())['order_ids']
        ruleset = compose_order_revision(self.new, class_id=self.classe.pk,
                                          order_ids=order_ids)
        self.user = self._novo_usuario('awakening')
        self.person = TbPersonagem.objects.create(dono=self.user, nome='Desperto', nivel=3)
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=self.classe, id_subclasse_id=order_ids['ordem-do-despertar'],
            nivel=3, principal=True)
        self.profile = TbPersonagemCacador.objects.create(personagem_classe=self.pc,
            ruleset=ruleset, ability='wis')
        self.client.force_login(self.user)
        self.url = reverse('hunter_preparation', args=[self.person.pk])

    def act(self, action, *, operation_id=None, version=None, **changes):
        self.profile.refresh_from_db()
        data = dict(character_id=self.person.pk, owner_id=self.user.pk,
                    operation_id=operation_id or uuid.uuid4(),
                    expected_version=self.profile.version if version is None else version,
                    action=action, confirmed=True, seconds=0)
        data.update(changes)
        return command(**data)

    def test_form_http_replay_timer_rest_and_linked_sheet(self):
        self.assertTrue(panel(self.profile)['ready'])
        op = str(uuid.uuid4())
        posted = self.client.post(self.url, dict(action='awakening',
            awakening_event='activate', operation_id=op, version=0, confirmed='1',
            initial_howl='1'))
        self.assertEqual(posted.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.awakening['active'])
        self.assertTrue(self.profile.awakening['initial_howl'])
        self.assertEqual(self.act('activate', operation_id=op, version=0,
                                  initial_howl=True)['remaining_seconds'], 3600)
        self.assertEqual(TbOperacaoRecurso.objects.filter(operation_id=op).count(), 1)
        self.assertContains(self.client.get(reverse('hunter_sheet', args=[self.person.pk])),
                            'Forma Desperta')
        self.assertEqual(self.act('elapsed', seconds=600)['remaining_seconds'], 3000)
        self.profile.refresh_from_db()
        self.assertFalse(self.act('elapsed', seconds=3000)['active'])
        with self.assertRaises(ValueError):
            self.act('activate')
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'curto', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['ready'])
        self.assertTrue(self.act('activate')['active'])

    def test_final_secret_cost_rolls_back_and_elder_rescue(self):
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['final_eligible'])
        with self.assertRaises(ValueError):
            self.act('final')
        self.act('activate')
        self.profile.refresh_from_db()
        active = self.act('final')
        self.assertEqual(active['final_remaining_seconds'], 60)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_temporario, 36)
        resource = self.person.recursos.get(chave=f'hunter:{self.profile.pk}:secrets')
        self.assertEqual(resource.maximo - resource.atual, 4)
        self.profile.refresh_from_db()
        self.assertFalse(self.act('elapsed', seconds=60)['final'])
        self.person.pv_atual = 0
        self.person.save(update_fields=['pv_atual'])
        self.profile.refresh_from_db()
        self.assertFalse(self.act('elder_rescue')['elder_ready'])
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_atual, 36)
        with self.assertRaises(ValueError):
            self.act('elder_rescue')
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]),
                         {'tipo': 'longo', 'next': self.url})
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['elder_ready'])

    def test_final_secret_applies_temporary_hp_tags_once_and_preserves_higher_pool(self):
        from .content_versions import seal_ruleset
        from .epic_talent_catalog import PARTIAL_EFFECTS
        from .versioned_classes import EVALUATOR, VOCABULARY
        from .versioned_origins import snapshot_origins

        talent = TbTalento.objects.create(
            nome='Teste de PV temporários', slug='teste-pv-temporarios',
            tipo='geral', tags_json=PARTIAL_EFFECTS['dadiva-da-saude-abundante'])
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=talent,
            categoria='epico', nome=talent.nome)
        self.pc.nivel = 18
        self.pc.save(update_fields=['nivel'])
        self.act('activate')
        with self.assertRaisesRegex(ValueError, 'Talent absent from pinned ruleset'):
            self.act('final')
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_temporario, 0)
        origin_revision = snapshot_origins()
        self.profile.refresh_from_db()
        revisions = [origin_revision if entry.identity == 'origin-catalog'
                     else entry.revision for entry in
                     self.profile.ruleset.entries.select_related('revision')]
        self.profile.ruleset = seal_ruleset(
            revisions, evaluator_version=EVALUATOR,
            vocabulary_version=VOCABULARY)
        self.profile.save(update_fields=['ruleset'])
        operation_id = uuid.uuid4()
        response = self.act('final', operation_id=operation_id)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_temporario, 41)
        talent.tags_json = []
        talent.save(update_fields=['tags_json'])
        self.person.pv_temporario = 0
        self.person.save(update_fields=['pv_temporario'])
        from .temporary_hp import grant_temporary_hp
        self.assertEqual(grant_temporary_hp(
            self.person, 36, ruleset=self.profile.ruleset), 41)
        self.person.talentos.filter(id_talento=talent).delete()
        self.person.pv_temporario = 0
        self.person.save(update_fields=['pv_temporario'])
        self.assertEqual(grant_temporary_hp(
            self.person, 36, ruleset=self.profile.ruleset), 36)
        TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=talent,
            categoria='epico', nome=talent.nome)
        self.assertEqual(self.act('final', operation_id=operation_id,
                                  version=response['version'] - 1), response)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_temporario, 36)
        self.person.pv_temporario = 50
        self.person.save(update_fields=['pv_temporario'])
        self.assertEqual(grant_temporary_hp(
            self.person, 36, ruleset=self.profile.ruleset), 41)
        self.person.refresh_from_db()
        self.assertEqual(self.person.pv_temporario, 50)

    def test_permissions_wrong_order_and_stale_event(self):
        with self.assertRaises(TbPersonagem.DoesNotExist):
            self.act('activate', owner_id=self.user.pk + 100)
        with self.assertRaises(ValueError):
            self.act('activate', version=-1)
        with self.assertRaises(ValueError):
            self.act('activate', confirmed=False)
        self.assertFalse(self.profile.awakening)
        self.pc.id_subclasse_id = None
        self.pc.save(update_fields=['id_subclasse'])
        self.profile.refresh_from_db()
        self.assertIsNone(panel(self.profile))
        with self.assertRaises(ValueError):
            self.act('activate')

    def test_howl_spends_once_mark_pauses_clock_and_prey_death_restores_use(self):
        self.act('activate')
        self.profile.refresh_from_db()
        first = self.act('howl')
        self.assertEqual(first['howl_count'], 1)
        resource = self.person.recursos.get(chave=f'hunter:{self.profile.pk}:secrets')
        self.assertEqual(resource.maximo - resource.atual, 2)
        self.profile.refresh_from_db()
        self.profile.mark = {'active': True, 'target': 'Presa'}
        self.profile.save(update_fields=['mark'])
        self.assertTrue(panel(self.profile)['timeless'])
        self.assertEqual(self.act('elapsed', seconds=3600)['remaining_seconds'], 3600)
        self.profile.refresh_from_db()
        self.assertTrue(on_marked_prey_death(self.profile))
        self.profile.save(update_fields=['awakening'])
        self.profile.refresh_from_db()
        self.assertTrue(panel(self.profile)['ready'])
        self.assertFalse(on_marked_prey_death(self.profile))
        self.profile.mark = {'active': False, 'reason': 'dead'}
        self.profile.save(update_fields=['mark'])
        self.assertFalse(self.act('elapsed', seconds=3600)['active'])
