from django.test import TestCase
from django.urls import reverse
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .character_engine import derive
from .models import TbPersonagem, TbClassehabilidade


class HunterLinkedSheetTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.url = reverse('hunter_sheet', args=[self.person.pk])
        self.person.publico = False
        self.person.save()

    def test_render_calculation_frozen_source_and_read_only(self):
        feature = TbClassehabilidade.objects.create(id_classe=self.cl,
            nome='Frozen defense', niveladquirido=1, tags_json=['speed:+5ft'])
        self.bind(self.data)
        expected = derive(self.person, ruleset=self.ruleset)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)
        self.assertContains(response, 'Atributos e salvaguardas')
        self.assertContains(response, 'Ataques disponíveis')
        self.assertContains(response, 'Maestrias escolhidas')
        self.assertEqual(response.context['sheet'], expected)
        writes = [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(
            ('INSERT ', 'UPDATE ', 'DELETE '))]
        self.assertEqual(writes, [])
        feature.tags_json=['speed:+50ft'];feature.save()
        self.cl.nome='Changed live class';self.cl.save()
        reloaded=self.client.get(self.url)
        self.assertEqual(reloaded.context['sheet'], expected)
        self.assertNotContains(reloaded,'Changed live class')
        self.assertContains(reloaded,reverse('hunter_preparation',args=[self.person.pk]))

    def test_private_public_staff_and_post_permissions(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.person.publico=True;self.person.save()
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.context['can_prepare'])
        self.person.publico=False;self.person.save()
        self.other.is_staff=True;self.other.save()
        self.assertEqual(self.client.get(self.url).status_code,200)
        self.assertEqual(self.client.post(self.url,{'ability':'wis'}).status_code,405)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ability,'int')
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code,302)

    def test_acquired_spell_missing_from_revision_is_visible_but_not_prepared(self):
        from .models import TbMagia
        self.bind(self.data)
        acquired = TbMagia.objects.create(nome='Magia adquirida depois',
            slug='magia-adquirida-depois', nivel=2)
        row = self.person.magias.create(id_magia=acquired, nome=acquired.nome,
            nivel=2, preparada=True, origem=self.cl.nome)
        response = self.client.get(self.url)
        self.assertContains(response, acquired.nome)
        self.assertContains(response, 'aquisição preservada; indisponível nesta revisão')
        spell = next(spell for spell in response.context['sheet']['magias']
                     if spell['nome'] == acquired.nome)
        self.assertTrue(spell['suspensa_na_revisao'])
        self.assertFalse(spell['preparada'])
        from .views import _magias_sheet_info
        info = _magias_sheet_info(self.person, response.context['sheet'], [],
                                 ruleset=self.ruleset)
        registered = next(spell for spell in info['lista'] if spell['id'] == row.pk)
        self.assertTrue(registered['suspensa_na_revisao'])
        self.assertFalse(registered['pode_alternar'])
        self.assertFalse(registered['preparada'])
        rejected = self.client.post(reverse('personagem_toggle_magia',
                                            args=[self.person.pk, row.pk]))
        self.assertIn('prep=invalida', rejected.url)
        rejected_catalog = self.client.post(reverse('personagem_toggle_magia_catalogo',
            args=[self.person.pk, self.cl.pk, acquired.slug]))
        self.assertIn('prep=invalida', rejected_catalog.url)
        row.refresh_from_db()
        self.assertTrue(row.preparada)
        self.assertEqual(row.id_magia_id, acquired.pk)

    def test_missing_revision_does_not_fall_back_to_current_catalog(self):
        from .content_versions import seal_ruleset, create_revision
        from .versioned_classes import EVALUATOR,VOCABULARY
        self.profile.ruleset=seal_ruleset([create_revision('hunter-rework',self.data)],
            evaluator_version=EVALUATOR,vocabulary_version=VOCABULARY)
        self.profile.save()
        response=self.client.get(self.url)
        self.assertContains(response,'revisão vinculada está incompleta',status_code=409)
        self.assertIsNone(response.context['sheet'])
        self.profile.delete()
        self.assertEqual(self.client.get(self.url).status_code,404)

    def test_preparation_links_to_sheet(self):
        response=self.client.get(reverse('hunter_preparation',args=[self.person.pk]))
        self.assertContains(response,self.url)

    def test_equipped_attack_and_escaped_names_are_displayed(self):
        from .models import TbItemMundano
        weapon=TbItemMundano.objects.create(nome='<script>alert(1)</script>',
            slug='sheet-blade',categoria='arma',subcategoria='arma_simples')
        self.cl.tags_json=['prof{armas_simples}'];self.cl.save()
        self.person.inventario.create(nome=weapon.nome,id_item_mundano=weapon,
            equipado=True,tags_json=['dmg:1d6(cortante)'])
        self.bind(self.data)
        response=self.client.get(self.url)
        self.assertContains(response,'&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response,weapon.nome)
        attacks=response.context['sheet']['ataques']['perfis']
        self.assertEqual(len(attacks),1)
        self.assertTrue(attacks[0]['proficiente'])
        self.assertContains(response,attacks[0]['dano'])

    def test_rest_returns_to_linked_sheet_and_public_view_has_no_controls(self):
        response=self.client.get(self.url)
        self.assertContains(response,'Concluir descanso longo')
        self.assertContains(response,'Revisão vinculada')
        self.assertNotContains(response,'Revis?o')
        rest=reverse('personagem_descansar',args=[self.person.pk])
        response=self.client.post(rest,{'tipo':'longo','next':self.url},follow=True)
        self.assertEqual(response.redirect_chain,[(self.url,302)])
        self.assertContains(response,'Revisão vinculada')
        self.assertEqual(self.person.recursos.get(chave=f'hunter:{self.profile.pk}:secrets').atual,3)
        self.person.publico=True;self.person.save()
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url),'Concluir descanso')
