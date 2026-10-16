from django.test import TestCase
from django.urls import reverse

from .bestiary_catalog import cr_classification, size_keys, type_key, type_keys
from .models import TbBestiario, TbClasse


class BestiaryCatalogClassificationTests(TestCase):
    def test_public_catalog_identifies_owner_scaled_placeholder_without_guessing_stats(self):
        creature = TbBestiario.objects.create(
            slug='espirito-de-teste', nome='Espirito de Teste', tipo='elemental',
            escala_com_dono=True, statblock_json={
                'name': 'Espirito de Teste', 'size': '', 'type': 'elemental', 'alignment': ''})
        url = reverse('bestiario')
        response = self.client.get(url, {'q': creature.slug})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Statblock incompleto: atributos e acoes ainda nao foram cadastrados')
        self.assertContains(response, 'ND pendente')
        creature.statblock_json['traits'] = [{'name': 'Vinculo', 'entries': ['Escala com o dono.']}]
        creature.save(update_fields=['statblock_json'])
        self.assertNotContains(self.client.get(url, {'q': creature.slug}), 'Statblock incompleto:')

    def test_large_catalog_paginates_statblocks_and_searches_all_records(self):
        TbBestiario.objects.bulk_create([
            TbBestiario(slug=f'criatura-{index:02}',
                         nome='Zágua derradeira' if index == 44 else f'Criatura {index:02}',
                         tipo='Besta', tamanho='M', nd='1',
                         statblock_json={'trait': [{'name': f'Traço {index}',
                                                    'entries': ['Descrição.']}]})
            for index in range(45)
        ])
        url = reverse('bestiario')
        first = self.client.get(url, {'tipo': 'besta'})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.context['criaturas']), 40)
        self.assertEqual(first.context['total_criaturas'], 45)
        self.assertTrue('id="bz-count">40</span> de 45 criatura(s)' in first.content.decode())
        self.assertEqual(first.content.decode().count('class="monster-panel '), 40)
        self.assertTrue('tipo=besta&amp;page=2' in first.content.decode())

        second = self.client.get(url, {'tipo': 'besta', 'page': '2'})
        self.assertEqual(len(second.context['criaturas']), 5)
        self.assertEqual(second.context['total_criaturas'], 45)
        self.assertTrue('id="bz-count">5</span> de 45 criatura(s)' in second.content.decode())
        self.assertTrue('Zágua derradeira' in second.content.decode())

        searched = self.client.get(url, {'tipo': 'besta', 'q': 'zagua'})
        self.assertEqual([item['slug'] for item in searched.context['criaturas']],
                         ['criatura-44'])
        self.assertEqual(searched.context['total_criaturas'], 1)

    def test_summon_reference_alias_resolves_in_widget_and_card(self):
        creature = TbBestiario.objects.create(
            slug='corcel-de-outro-mundo', nome='Corcel de Outro Mundo',
            tipo='Celestial', tamanho='L', nd='2', statblock_json={'hp': 30})
        for route, params, name_key in (
            ('api_creature_preview', {'slug': 'corcel_de_outro_mundo'}, 'nome'),
            ('api_card_preview', {'table': 'tbBestiario', 'args': 'corcel_de_outro_mundo'}, 'title'),
        ):
            response = self.client.get(reverse(route), params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()[name_key], creature.nome)
        self.assertEqual(self.client.get(reverse('api_creature_preview'),
                                         {'slug': 'criatura_inexistente'}).status_code, 404)

    def test_exact_slug_precedes_underscore_alias(self):
        TbBestiario.objects.create(slug='corcel-de-outro-mundo', nome='Hifen',
                                   statblock_json={'hp': 30})
        TbBestiario.objects.create(slug='corcel_de_outro_mundo', nome='Sublinhado',
                                   statblock_json={'hp': 40})
        response = self.client.get(reverse('api_creature_preview'),
                                   {'slug': 'corcel_de_outro_mundo'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['nome'], 'Sublinhado')

    def test_public_catalog_and_preview_show_description_without_raw_mechanical_tags(self):
        creature = TbBestiario.objects.create(
            slug='cantor-do-bosque', nome='Cantor do Bosque', tipo='Feérico',
            tamanho='M', nd='2', statblock_json={
                'trait': [{'name': 'Canto Arcano',
                           'entries': ['Conjura uma magia conhecida.',
                                       {'name': 'Efeito', 'entries': ['Alcança um aliado.']}],
                           'tags_json': ['cast{spell:magia-secreta, at-will}']}],
            })
        for url in (reverse('mundo_bestiario'), reverse('api_creature_preview') + '?slug=' + creature.slug):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            body = (response.json()['statblock_html'] if url.startswith(reverse('api_creature_preview'))
                    else response.content.decode())
            self.assertIn('Canto Arcano', body)
            self.assertIn('Conjura uma magia conhecida.', body)
            self.assertIn('Efeito: Alcança um aliado.', body)
            self.assertNotIn('**Efeito**', body)
            self.assertNotIn('cast{spell:', body)
        creature.refresh_from_db()
        self.assertEqual(creature.statblock_json['trait'][0]['tags_json'],
                         ['cast{spell:magia-secreta, at-will}'])

    def test_public_catalog_renders_only_safe_existing_creature_art(self):
        creature = TbBestiario.objects.create(
            slug='corcel-ilustrado', nome='Corcel Ilustrado',
            imagem_url='/media/bestiario/corcel.png', statblock_json={})
        url = reverse('bestiario')
        body = self.client.get(url, {'q': creature.slug}).content.decode()
        self.assertIn('src="/media/bestiario/corcel.png"', body)
        self.assertIn('alt="Ilustração de Corcel Ilustrado"', body)
        creature.imagem_url = 'javascript:alert(1)'
        creature.save(update_fields=['imagem_url'])
        body = self.client.get(url, {'q': creature.slug}).content.decode()
        self.assertNotIn('class="monster-art"', body)
        self.assertNotIn('javascript:alert(1)', body)
        creature.imagem_url = None
        creature.save(update_fields=['imagem_url'])
        body = self.client.get(url, {'q': creature.slug}).content.decode()
        self.assertNotIn('class="monster-art"', body)

    def test_preview_preserves_ability_paragraphs_and_escapes_content(self):
        creature = TbBestiario.objects.create(
            slug='conjurador-de-teste', nome='Conjurador de Teste',
            statblock_json={'trait': [{
                'name': 'Conjuracao',
                'entries': ['Conjura as seguintes magias:\n\nÀ vontade: Luz\n\n1/dia: Escudo <script>alert(1)</script>'],
            }]},
        )
        response = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
        self.assertEqual(response.status_code, 200)
        html = response.json()['statblock_html']
        self.assertIn('Conjura as seguintes magias:<br><br>À vontade: Luz<br><br>1/dia:', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>', html)

    def test_preview_decodes_legacy_literal_breaks_without_losing_rule_or_escaping(self):
        creature = TbBestiario.objects.create(
            slug='legacy-gullet', nome='Legacy Gullet',
            statblock_json={'actions': [{
                'name': 'Mordida',
                'entries': [
                    'O alvo é engolido.\\n\\nA garganta comporta duas criaturas '
                    'e exige CD 20 <script>alert(1)</script> para regurgitar.'
                ],
            }]},
        )
        response = self.client.get(reverse('api_creature_preview'), {'slug': creature.slug})
        self.assertEqual(response.status_code, 200)
        html = response.json()['statblock_html']
        self.assertIn('O alvo é engolido.<br><br>A garganta comporta duas criaturas', html)
        self.assertIn('CD 20 &lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>', html)
        creature.refresh_from_db()
        self.assertIn('\\n\\n', creature.statblock_json['actions'][0]['entries'][0])

    def test_explicit_aliases_and_special_values(self):
        self.assertEqual(type_key('Besta (Dinossauro)'), 'besta')
        self.assertEqual(type_key('demonio'), 'corruptor')
        self.assertEqual(type_key('fada'), 'feerico')
        self.assertIsNone(type_key('espirito'))
        self.assertEqual(type_key('swarm of Tiny Beasts'), 'besta')
        self.assertIsNone(type_key('Celestial, Fey, or Fiend'))
        self.assertEqual(type_keys('Celestial, Fey, or Fiend'),
                         ('celestial', 'feerico', 'corruptor'))
        self.assertEqual(type_keys('celestial ou corruptor (Tit\ufffd)'),
                         ('celestial', 'corruptor'))
        self.assertEqual(type_keys('enxame de mortos-vivos mi\ufffddos'), ('morto-vivo',))
        self.assertEqual(size_keys('Small or Medium'), ('S', 'M'))
        self.assertEqual(size_keys('Huge or Gargantuan'), ('H', 'G'))
        self.assertEqual(cr_classification('1/4 (XP 50; PB +2)')[:2], ('nd:1/4', 0.25))
        self.assertEqual(cr_classification('2 (XP 450; PB +2)')[:2], ('nd:2', 2.0))
        self.assertEqual(cr_classification('None (XP 0; PB equals your bonus)')[1], float('inf'))

    def test_imported_demon_and_fey_types_are_visible_in_canonical_filters(self):
        for slug, kind in (('demonio-menor', 'demonio'), ('espirito-feerico', 'fada'),
                           ('espirito-sem-tipo', 'espirito')):
            TbBestiario.objects.create(slug=slug, nome=slug, tipo=kind, statblock_json={})
        url = reverse('bestiario')
        for kind, expected in (('corruptor', 'demonio-menor'), ('feerico', 'espirito-feerico')):
            response = self.client.get(url, {'tipo': kind})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([item['slug'] for item in response.context['criaturas']], [expected])
        searched = self.client.get(url, {'q': 'corruptor'})
        self.assertEqual([item['slug'] for item in searched.context['criaturas']],
                         ['demonio-menor'])
        pending = self.client.get(url, {'tipo': 'pending'})
        self.assertEqual([item['slug'] for item in pending.context['criaturas']], ['espirito-sem-tipo'])

    def test_combined_filters_and_nd_order_share_the_same_projection(self):
        for slug, nome, kind, size, nd in (
            ('beast-multi', 'Besta múltipla', 'Besta (Dinossauro)', 'Small or Medium', '1/4 (XP 50; PB +2)'),
            ('beast-small', 'Besta pequena', 'Besta', 'Pequeno', '1/4 (XP 60; PB +2)'),
            ('fiend-large', 'Corruptor grande', 'Corruptor (Demônio)', 'L', '2 (XP 450; PB +2)'),
            ('variable', 'Tipo variável', 'Celestial, Fey, or Fiend', None,
             'None (XP 0; PB equals your bonus)'),
        ):
            TbBestiario.objects.create(slug=slug, nome=nome, tipo=kind,
                                       tamanho=size, nd=nd, statblock_json={})
        url = reverse('bestiario')
        response = self.client.get(url, {'tipo': 'besta', 'tam': 'S', 'nd': 'nd:1/4'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual({c['slug'] for c in response.context['criaturas']},
                         {'beast-multi', 'beast-small'})
        self.assertEqual(next(c['tamanho'] for c in response.context['criaturas']
                              if c['slug'] == 'beast-multi'), 'Pequeno / Médio')
        self.assertIn('id="bz-count">2</span>', response.content.decode())
        old_link = self.client.get(url, {'tipo': 'Besta', 'tam': 'Pequeno',
                                         'nd': '1/4 (XP 50; PB +2)'})
        self.assertEqual({c['slug'] for c in old_link.context['criaturas']},
                         {'beast-multi', 'beast-small'})
        medium = self.client.get(url, {'tam': 'M'})
        self.assertEqual([c['slug'] for c in medium.context['criaturas']], ['beast-multi'])
        pending = self.client.get(url, {'tipo': 'pending', 'tam': 'pending'})
        self.assertEqual([c['slug'] for c in pending.context['criaturas']], [])
        for kind in ('celestial', 'feerico', 'corruptor'):
            filtered = self.client.get(url, {'tipo': kind})
            self.assertIn('variable', [c['slug'] for c in filtered.context['criaturas']])
        descending = self.client.get(url, {'ord': 'nd_desc'})
        self.assertEqual([c['slug'] for c in descending.context['criaturas']],
                         ['fiend-large', 'beast-multi', 'beast-small', 'variable'])

    def test_missing_and_explicitly_unrated_nd_have_distinct_filters_and_cards(self):
        for slug, nd in (
            ('nd-ausente', None),
            ('sem-nd-fixo', 'None (XP 0; PB equals your bonus)'),
            ('nd-zero', '0 (XP 10)'),
            ('nd-especial', 'Varies with summoner'),
        ):
            TbBestiario.objects.create(slug=slug, nome=slug, tipo='Besta',
                                       tamanho='M', nd=nd, statblock_json={'cr': nd})
        url = reverse('bestiario')
        for key, expected, label in (
            ('pending', 'nd-ausente', 'ND pendente'),
            ('unrated', 'sem-nd-fixo', 'Sem ND fixo'),
            ('nd:0', 'nd-zero', 'ND 0'),
            ('raw:Varies with summoner', 'nd-especial', 'ND Varies with summoner'),
        ):
            response = self.client.get(url, {'nd': key})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([item['slug'] for item in response.context['criaturas']], [expected])
            self.assertIn((key, label), response.context['nds'])
            self.assertIn('id="bz-count">1</span> de 1 criatura(s)', response.content.decode())
        self.assertEqual(cr_classification(None)[0], 'pending')
        self.assertEqual(cr_classification('None (XP 0; PB equals your bonus)')[0], 'unrated')
        self.assertEqual(cr_classification(0)[:2], ('nd:0', 0.0))
        from .views import _statblock_display_full
        self.assertEqual(_statblock_display_full({'cr': 0})['cr'], '0')
        for slug, label in (('nd-ausente', 'pendente'), ('sem-nd-fixo', 'Sem ND fixo')):
            preview = self.client.get(reverse('api_creature_preview'), {'slug': slug})
            self.assertEqual(preview.status_code, 200)
            self.assertIn(label, preview.json()['statblock_html'])
        self.assertIsNone(TbBestiario.objects.get(slug='nd-ausente').nd)
        self.assertEqual(TbBestiario.objects.get(slug='sem-nd-fixo').nd,
                         'None (XP 0; PB equals your bonus)')

    def test_owner_scale_and_class_link_filter_without_changing_type_or_nd(self):
        classe = TbClasse.objects.create(nome='Guardiao', slug='guardiao-teste')
        TbBestiario.objects.create(
            slug='espirito-vinculado', nome='Espirito Vinculado', tipo='Besta',
            escala_com_dono=True, companheiro_classe=classe,
            statblock_json={'type': 'Besta', 'name': 'Espirito Vinculado'})
        TbBestiario.objects.create(
            slug='espirito-solto', nome='Espirito Solto', tipo='Besta',
            escala_com_dono=True, statblock_json={'type': 'Besta'})
        TbBestiario.objects.create(
            slug='besta-comum', nome='Besta Comum', tipo='Besta',
            tamanho='M', nd='1', statblock_json={'type': 'Besta'})
        url = reverse('bestiario')
        scaled = self.client.get(url, {'uso': 'owner_scaled', 'tipo': 'besta',
                                       'nd': 'pending'})
        self.assertEqual(scaled.status_code, 200)
        self.assertEqual({c['slug'] for c in scaled.context['criaturas']},
                         {'espirito-vinculado', 'espirito-solto'})
        self.assertEqual(scaled.context['total_criaturas'], 2)
        self.assertIn('id="bz-count">2</span> de 2 criatura(s)', scaled.content.decode())
        linked = self.client.get(url, {'uso': 'linked_companion', 'tipo': 'besta'})
        self.assertEqual([c['slug'] for c in linked.context['criaturas']],
                         ['espirito-vinculado'])
        self.assertIn('Classe/subclasse', linked.content.decode())
        self.assertEqual(linked.context['criaturas'][0]['nd_key'], 'pending')
        self.assertEqual(self.client.get(reverse('api_creature_preview'),
                                         {'slug': 'espirito-vinculado'}).status_code, 200)
        self.assertEqual(TbBestiario.objects.get(slug='espirito-vinculado').tipo, 'Besta')
