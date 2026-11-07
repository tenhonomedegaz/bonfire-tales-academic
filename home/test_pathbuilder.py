import json
import os
import re

from django.urls import reverse

from home.models import (
    TbClasse,
    TbClassehabilidade,
    TbItemMagico,
    TbItemMundano,
    TbEssencia,
    TbLinhagem,
    TbMagia,
    TbPersonagem,
    TbPersonagemCacador,
    TbPersonagemAtributoBonus,
    TbPersonagemClasse,
    TbPersonagemEscolha,
    TbPersonagemItem,
    TbPersonagemMagia,
    TbPersonagemTalento,
    TbSubclasse,
    TbTalento,
    TbOpcaojogo,
    TbRaca,
    TbTracoracial,
)
from home.test_criador import _CriadorBase

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
_JS = os.path.join(_STATIC, 'js', 'pathbuilder.js')
_CSS = os.path.join(_STATIC, 'css', 'pages', 'pathbuilder.css')


def _texto(caminho):
    with open(caminho, encoding='utf-8') as fh:
        return fh.read()


class PathbuilderContratoClienteTests(_CriadorBase):
    """Sem navegador no CI, o que quebra a pagina em silencio e o contrato JS x template:
    um `byId('pb-x')` sem o `id` correspondente devolve null e o laboratorio morre no
    primeiro render. Estes testes amarram os dois lados."""

    def setUp(self):
        self.user = self._novo_usuario("pathbuilder-contrato")
        self.client.force_login(self.user)

    def test_todo_id_procurado_pelo_js_existe_no_template(self):
        html = self.client.get(reverse("pathbuilder_laboratorio")).content.decode("utf-8")
        js = _texto(_JS)
        ids = sorted(set(re.findall(r"byId\('([^']+)'\)", js)))
        self.assertGreaterEqual(len(ids), 12, ids)
        faltando = [i for i in ids if ('id="%s"' % i) not in html]
        self.assertEqual(faltando, [], "ids que o JS busca e o template nao tem: %s" % faltando)

    def test_ganchos_de_dados_do_js_existem_no_template(self):
        html = self.client.get(reverse("pathbuilder_laboratorio")).content.decode("utf-8")
        for gancho in ('data-step-tab', 'data-step=', 'data-build-tab', 'data-build-mode',
                       'data-item-kind', 'data-picker=', 'data-picker-search',
                       'data-picker-list', 'data-step-prev', 'data-step-next'):
            self.assertIn(gancho, html, gancho)

    def test_privacidade_e_etapa_ativa_sao_explicitas(self):
        creator = self.client.get(reverse('pathbuilder')).content.decode('utf-8')
        laboratory = self.client.get(reverse('pathbuilder_laboratorio')).content.decode('utf-8')
        js = _texto(_JS)
        self.assertIn('enviadas ao servidor para calcular a prévia', creator)
        self.assertIn('Cada prévia envia a base e a build ao servidor', laboratory)
        self.assertIn('nenhuma ficha é salva', laboratory)
        self.assertIn('data-step-tab="0" role="button" tabindex="0" aria-current="step"', laboratory)
        self.assertIn("tab.setAttribute('aria-current', 'step')", js)
        self.assertIn("tab.removeAttribute('aria-current')", js)

    def test_classes_emitidas_pelo_js_estao_estilizadas(self):
        """Nenhum cartao do laboratorio sai sem CSS (era o cheiro de 'CSS genérico de IA':
        markup novo no JS e folha de estilo desatualizada)."""
        css = _texto(_CSS)
        for classe in ('pb-opt', 'pb-opt-pick', 'pb-opt-mark', 'pb-opt-main', 'pb-opt-name',
                       'pb-opt-meta', 'pb-opt-more', 'pb-opt-desc', 'pb-opt-group',
                       'pb-opt-lines', 'pb-opts-inline', 'pb-subclass', 'pb-row',
                       'pb-row-head', 'pb-row-name', 'pb-row-note', 'pb-line',
                       'pb-line-name', 'pb-line-tools', 'pb-stepper-num', 'pb-attr',
                       'pb-attr-sig', 'pb-attr-final', 'pb-base-cell', 'pb-check', 'pb-x',
                       'pb-counter', 'pb-diff-cell', 'pb-diff-lbl', 'pb-sheet-error',
                       'pb-choice-search', 'pb-opt-control', 'pb-racial-select',
                       'pb-muted'):
            self.assertIn('.%s' % classe, css, classe)

    def test_o_laboratorio_nao_reimplementa_a_folha_no_css_nem_no_js(self):
        """A folha é a da ficha: o CSS/JS do laboratório não redeclara o vocabulário dela."""
        css = _texto(_CSS)
        js = _texto(_JS)
        for da_ficha in ('.attr-box', '.attr-stack', '.seal-num', '.hp-track',
                         '.feat-grid', '.line-row', '.ficha-panel {'):
            self.assertNotIn(da_ficha, css, da_ficha)
        # o JS injeta a folha pronta; não monta <table>/vitals/atributos por conta própria
        for markup in ('<table', 'pb-table', 'pb-vitals', 'pb-attrs"'):
            self.assertNotIn(markup, js, markup)


class PathbuilderTests(_CriadorBase):
    def setUp(self):
        self.user = self._novo_usuario("pathbuilder-user")
        self.client.force_login(self.user)

    def _post_preview(self, base, build):
        return self.client.post(
            reverse("pathbuilder_preview"),
            data=json.dumps({"base": base, "build": build}),
            content_type="application/json",
        )

    def _build(self, classe_slug, **overrides):
        build = {
            "modo": "sandbox",
            "classes": [{"slug": classe_slug, "nivel": 1, "subclasse": ""}],
            "atributos_bonus": {},
            "escolhas": {},
            "talentos": [],
            "talentos_raciais": [],
            "itens": [],
            "magias": [],
        }
        build.update(overrides)
        return build

    def test_monk_subclass_named_bonus_styles_and_duplicate_fallback(self):
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        monk = TbClasse.objects.get(slug='monge')
        cases = (
            ('misericordia', {'estilo-debilitante', 'estilo-agil'}, 'estilo-debilitante'),
            ('palma-aberta', {'estilo-habil', 'estilo-agil'}, 'estilo-habil'),
        )
        for slug, defaults, other_default in cases:
            with self.subTest(subclass_slug=slug):
                subclass = TbSubclasse.objects.get(slug=slug)
                fresh = TbPersonagem.objects.create(
                    dono=self.user, nome='Estilos novos ' + slug)
                TbPersonagemClasse.objects.create(
                    id_personagem=fresh, id_classe=monk,
                    id_subclasse=subclass, nivel=3, principal=True)
                _apply_choices(fresh, {'escolhas': {}})
                fresh_group = next(g for g in _groups_with_keys(fresh)
                                   if g['tipo'] == 'estilos_de_ki')
                self.assertEqual({e['valor'] for e in fresh_group['escolhidas']}, defaults)
                self.assertEqual(fresh_group['pendentes'], 3)
                character = TbPersonagem.objects.create(
                    dono=self.user, nome='Estilos extras ' + slug)
                row = TbPersonagemClasse.objects.create(
                    id_personagem=character, id_classe=monk,
                    id_subclasse=subclass, nivel=3, principal=True)
                base = ['estilo-agil', 'estilo-veloz', 'estilo-barreira']
                for slot, name in enumerate(base):
                    option = TbOpcaojogo.objects.get(slug=name)
                    TbPersonagemEscolha.objects.create(
                        id_personagem=character, origem='Monge: Estilos de Ki',
                        tipo='estilos_de_ki', slot=slot, id_opcao=option, valor=name)
                group = next(g for g in _groups_with_keys(character)
                             if g['tipo'] == 'estilos_de_ki')
                self.assertEqual(group['n'], 5)
                self.assertEqual(set(group['auto_options']), defaults)
                _apply_choices(character, {'escolhas': {}})
                group = next(g for g in _groups_with_keys(character)
                             if g['tipo'] == 'estilos_de_ki')
                self.assertEqual(group['n'], 5)
                self.assertEqual(group['pendentes'], 1)
                self.assertEqual({e['valor'] for e in group['escolhidas']},
                                 set(base) | {other_default})
                _apply_choices(character, {'escolhas': {
                    group['pathbuilder_key']: ['estilo-constritor']}})
                card = next(g for g in _choice_groups(character, {'escolhas': {}})
                            if g['key'] == group['pathbuilder_key'])
                self.assertEqual(card['pendentes'], 0)
                self.assertEqual(character.escolhas.filter(
                    tipo='estilos_de_ki').count(), 5)
                for level in range(3, 21):
                    row.nivel = level
                    row.save(update_fields=['nivel'])
                    progressed = next(g for g in _groups_with_keys(character)
                                      if g['tipo'] == 'estilos_de_ki')
                    self.assertEqual(progressed['n'], 5 + (level >= 5) +
                                     (level >= 11) + (level >= 17))
                    self.assertEqual({e['valor'] for e in progressed['escolhidas']},
                                     set(base) | {other_default, 'estilo-constritor'})
                row.nivel = 2
                row.save(update_fields=['nivel'])
                lower = next(g for g in _groups_with_keys(character)
                             if g['tipo'] == 'estilos_de_ki')
                self.assertEqual(lower['n'], 3)
                self.assertEqual({e['valor'] for e in lower['escolhidas']}, set(base))
                row.nivel = 3
                row.save(update_fields=['nivel'])
                restored = next(g for g in _groups_with_keys(character)
                                if g['tipo'] == 'estilos_de_ki')
                self.assertEqual({e['valor'] for e in restored['escolhidas']},
                                 set(base) | {other_default, 'estilo-constritor'})

    def test_monk_bonus_styles_http_preview_matches_subclass_page(self):
        base = self._payload('monge')
        before = TbPersonagem.objects.count()
        cases = (
            ('misericordia', {'estilo-debilitante', 'estilo-agil'}),
            ('palma-aberta', {'estilo-habil', 'estilo-agil'}),
        )
        for subclass, expected in cases:
            with self.subTest(subclass=subclass):
                build = self._build('monge', classes=[
                    {'slug': 'monge', 'nivel': 3, 'subclasse': subclass}])
                response = self._post_preview(base, build)
                self.assertEqual(response.status_code, 200, response.content[:400])
                preview = response.json()['build']
                group = next(g for g in preview['escolhas_grupos']
                             if g['kind'] == 'opcao' and
                             g['label'] == 'Estilos de Ki')
                self.assertEqual(group['limite'], 5)
                self.assertEqual({choice['valor'] for choice in group['resolvidas']},
                                 expected)
                self.assertEqual(group['pendentes'], 3)
                self.assertIn('data-pb-folha', preview['ficha_html'])
                for slug in expected:
                    self.assertIn(TbOpcaojogo.objects.get(slug=slug).nome,
                                  preview['ficha_html'])
                self.assertEqual(TbPersonagem.objects.count(), before)

    def test_mutagenic_formulas_are_known_before_preparation(self):
        from home.pathbuilder import PathbuilderError, _apply_choices, _groups_with_keys

        hunter = TbClasse.objects.get(slug='cacador')
        mutant = TbSubclasse.objects.get(slug='ordem-dos-mutantes')
        character = TbPersonagem.objects.create(dono=self.user, nome='Mutante da Matriz')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter,
            id_subclasse=mutant, nivel=3, principal=True)
        groups = _groups_with_keys(character)
        known = next(g for g in groups if g['kind'] == 'mutagenico_conhecido')
        self.assertEqual(known['n'], 4)
        self.assertEqual(len(known['universo']), 16)
        self.assertFalse(any(g['kind'] == 'mutagenico_preparado' for g in groups))

        slugs = [option['slug'] for option in known['universo'][:4]]
        _apply_choices(character, {'escolhas': {known['pathbuilder_key']: slugs}})
        prepared = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'mutagenico_preparado')
        self.assertEqual(prepared['n'], 1)
        self.assertEqual({option['slug'] for option in prepared['universo']}, set(slugs))
        with self.assertRaises(PathbuilderError):
            _apply_choices(character, {'escolhas': {
                prepared['pathbuilder_key']: [known['universo'][4]['slug']]}})
        self.assertFalse(character.escolhas.filter(tipo='mutagenico_preparado').exists())
        _apply_choices(character, {'escolhas': {prepared['pathbuilder_key']: [slugs[0]]}})
        self.assertEqual(character.escolhas.filter(tipo='mutagenico_preparado').count(), 1)
        for level, known_count, prepared_count in ((7, 5, 2), (11, 6, 2),
                                                   (15, 7, 3), (18, 8, 3)):
            row.nivel = level
            row.save(update_fields=['nivel'])
            groups = _groups_with_keys(character)
            self.assertEqual(next(g for g in groups
                                  if g['kind'] == 'mutagenico_conhecido')['n'], known_count)
            self.assertEqual(next(g for g in groups
                                  if g['kind'] == 'mutagenico_preparado')['n'], prepared_count)
        row.nivel = 3
        row.save(update_fields=['nivel'])
        self.assertEqual(character.escolhas.filter(tipo='mutagenico_preparado').count(), 1)

    def test_option_removal_keeps_unrelated_levelup_records(self):
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys
        from home.views import _ERR_OPCAO_INVALIDA, _lvl_aplicar_opcao

        hunter = TbClasse.objects.get(slug='cacador')
        mutant = TbSubclasse.objects.get(slug='ordem-dos-mutantes')
        character = TbPersonagem.objects.create(dono=self.user, nome='Escolhas protegidas')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter,
            id_subclasse=mutant, nivel=3, principal=True)
        known = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'mutagenico_conhecido')
        formula = known['universo'][0]['slug']
        _apply_choices(character, {'escolhas': {known['pathbuilder_key']: [formula]}})
        selected = character.escolhas.get(tipo='mutagenico_conhecido')
        tracking = TbPersonagemEscolha.objects.create(
            id_personagem=character, origem='Troca de Magia N7',
            tipo='troca_magia', slot=0, valor='7')

        self.assertEqual(_lvl_aplicar_opcao(character, {
            'acao': 'remover', 'escolha': tracking.pk}), [_ERR_OPCAO_INVALIDA])
        self.assertTrue(character.escolhas.filter(pk=tracking.pk).exists())
        prepared = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'mutagenico_preparado')
        _apply_choices(character, {'escolhas': {prepared['pathbuilder_key']: [formula]}})
        prepared_choice = character.escolhas.get(tipo='mutagenico_preparado')
        self.assertEqual(_lvl_aplicar_opcao(character, {
            'acao': 'remover', 'escolha': selected.pk}), [_ERR_OPCAO_INVALIDA])
        self.assertTrue(character.escolhas.filter(pk=selected.pk).exists())
        url = reverse('personagem_escolher_opcoes', args=[character.pk])
        response = self.client.post(url, {'acao': 'remover', 'escolha': selected.pk})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(character.escolhas.filter(pk=selected.pk).exists())
        self.assertEqual(_lvl_aplicar_opcao(character, {
            'acao': 'remover', 'escolha': prepared_choice.pk}), [])
        response = self.client.post(url, {'acao': 'remover', 'escolha': selected.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(character.escolhas.filter(pk=selected.pk).exists())
        self.assertTrue(character.escolhas.filter(pk=tracking.pk).exists())

    def test_mutagenic_formula_swap_is_optional_in_levelup_batch(self):
        from home.pathbuilder import _apply_choices, _groups_with_keys

        hunter = TbClasse.objects.get(slug='cacador')
        mutant = TbSubclasse.objects.get(slug='ordem-dos-mutantes')
        character = TbPersonagem.objects.create(
            dono=self.user, nome='Troca Mutagênica', nivel=6, aventuras=500)
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter,
            id_subclasse=mutant, nivel=6, principal=True)
        known = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'mutagenico_conhecido')
        self.assertEqual(known['swap'], 'level_up')
        self.assertTrue(known['constraints']['on_gain'])
        slugs = [o['slug'] for o in known['universo'][:6]]
        _apply_choices(character, {'escolhas': {known['pathbuilder_key']: slugs[:4]}})
        prepared = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'mutagenico_preparado')
        self.assertEqual(prepared['swap'], 'rest')
        _apply_choices(character, {'escolhas': {prepared['pathbuilder_key']: [slugs[0]]}})
        old = character.escolhas.get(tipo='mutagenico_conhecido', valor=slugs[0])

        page = self.client.get(reverse('personagem_subir_nivel', args=[character.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'data-lvl-card="trocar_opcao"')
        self.assertContains(page, 'data-lvl-queue="trocar_opcao"')
        actions = [
            {'tipo': 'subir_nivel', 'payload': {'classe': hunter.pk}},
            {'tipo': 'opcao', 'payload': {
                'classe': hunter.pk, 'slug': 'mutagenico_conhecido', 'val': slugs[4]}},
            {'tipo': 'trocar_opcao', 'payload': {
                'classe': hunter.pk, 'escolha': old.pk, 'val': slugs[5]}},
        ]
        apply_url = reverse('personagem_levelup_aplicar', args=[character.pk])
        invalid = self.client.post(apply_url, data=json.dumps({'acoes': actions[:1] + actions[2:]}),
                                   content_type='application/json')
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(character.escolhas.get(pk=old.pk).valor, slugs[0])
        character.refresh_from_db()
        self.assertEqual(character.nivel, 6)
        duplicate = json.loads(json.dumps(actions))
        duplicate[2]['payload']['val'] = slugs[4]
        rejected = self.client.post(apply_url, data=json.dumps({'acoes': duplicate}),
                                    content_type='application/json')
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(character.escolhas.get(pk=old.pk).valor, slugs[0])
        preview = self.client.post(
            reverse('personagem_levelup_preview', args=[character.pk]),
            data=json.dumps({'acoes': actions}), content_type='application/json')
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['erros'], [])
        self.assertEqual(character.escolhas.get(pk=old.pk).valor, slugs[0])
        self.assertEqual(character.escolhas.filter(tipo='mutagenico_preparado').count(), 1)

        applied = self.client.post(apply_url, data=json.dumps({'acoes': actions}),
                                   content_type='application/json')
        self.assertEqual(applied.status_code, 200, applied.content[:400])
        character.refresh_from_db()
        self.assertEqual(character.nivel, 7)
        self.assertEqual(character.escolhas.get(pk=old.pk).valor, slugs[5])
        self.assertEqual(character.escolhas.filter(tipo='mutagenico_conhecido').count(), 5)
        self.assertTrue(character.escolhas.filter(tipo='mutagenico_conhecido',
                                                 valor=slugs[4]).exists())
        self.assertFalse(character.escolhas.filter(tipo='mutagenico_preparado').exists())
        self.assertEqual(self.client.get(reverse('ficha_detail', args=[character.pk])).status_code, 200)
        next_page = self.client.get(reverse('personagem_subir_nivel', args=[character.pk]))
        self.assertEqual(next_page.status_code, 200)
        self.assertNotContains(next_page, 'data-lvl-card="trocar_opcao"')
        replay = self.client.post(apply_url, data=json.dumps({'acoes': actions[2:]}),
                                  content_type='application/json')
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(character.escolhas.get(pk=old.pk).valor, slugs[5])
        for before, after, expected in ((10, 11, 6), (14, 15, 7), (17, 18, 8)):
            with self.subTest(level=after):
                class_row.nivel = before
                class_row.save(update_fields=['nivel'])
                character.nivel = before
                character.save(update_fields=['nivel'])
                group = next(g for g in _groups_with_keys(character)
                             if g['kind'] == 'mutagenico_conhecido')
                chosen = {e['valor'] for e in group['escolhidas']}
                free = [o['slug'] for o in group['universo'] if o['slug'] not in chosen]
                replacing = character.escolhas.filter(
                    tipo='mutagenico_conhecido').order_by('slot').first()
                actions = [
                    {'tipo': 'subir_nivel', 'payload': {'classe': hunter.pk}},
                    {'tipo': 'opcao', 'payload': {
                        'classe': hunter.pk, 'slug': 'mutagenico_conhecido',
                        'val': free[0]}},
                    {'tipo': 'trocar_opcao', 'payload': {
                        'classe': hunter.pk, 'escolha': replacing.pk, 'val': free[1]}},
                ]
                response = self.client.post(
                    apply_url, data=json.dumps({'acoes': actions}),
                    content_type='application/json')
                self.assertEqual(response.status_code, 200, response.content[:400])
                character.refresh_from_db()
                self.assertEqual(character.nivel, after)
                self.assertEqual(character.escolhas.get(pk=replacing.pk).valor, free[1])
                self.assertEqual(character.escolhas.filter(
                    tipo='mutagenico_conhecido').count(), expected)

    def test_sealed_mutagenic_formula_prep_preserves_legacy_choice(self):
        from home.content_versions import create_revision, seal_ruleset
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.tag_engine.library import Library
        from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class
        from home.versioned_conditions import snapshot_conditions
        from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
        from home.versioned_library import snapshot_library
        from home.versioned_options import snapshot_options
        from home.versioned_origins import snapshot_origins
        from home.versioned_spells import snapshot_spells

        hunter = TbClasse.objects.get(slug='cacador')
        mutant = TbSubclasse.objects.get(slug='ordem-dos-mutantes')
        feature = TbClassehabilidade.objects.get(pk=1034)
        current_tags = feature.tags_json
        feature.tags_json = [
            tag for tag in current_tags if not tag.startswith('pick:mutagenico_conhecido:')]
        feature.tags_json = [
            tag.replace('classlvl=7:+1, classlvl=15:+1',
                        'classlvl=7:2, classlvl=15:3').split('(from_known:')[0]
            if tag.startswith('pick:mutagenico_preparado:') else tag
            for tag in feature.tags_json]
        feature.tags_json.append('reset:rest')
        feature.save(update_fields=['tags_json'])
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % hunter.pk, inventory_class(hunter.pk)),
            snapshot_options(), snapshot_mundane_items(), snapshot_magic_items(),
            snapshot_origins(), snapshot_spells(), snapshot_conditions(),
            snapshot_library(raw=Library(prefer_db=False).raw),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        feature.tags_json = current_tags
        feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Mutante legado')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter,
            id_subclasse=mutant, nivel=3, principal=True, ruleset=ruleset)
        TbPersonagemEscolha.objects.create(
            id_personagem=character, origem=feature.nome,
            tipo='mutagenico_preparado', slot=0, valor='carapaca_basilisco')
        _apply_choices(character, {'escolhas': {}})
        known = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'mutagenico_conhecido')
        self.assertEqual(known['n'], 4)
        self.assertEqual(known['swap'], 'level_up')
        self.assertTrue(known['constraints']['on_gain'])
        self.assertEqual([e['valor'] for e in known['escolhidas']],
                         ['carapaca_basilisco'])
        prepared = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'mutagenico_preparado')
        self.assertEqual(prepared['n'], 1)
        self.assertEqual(prepared['swap'], 'rest')
        self.assertEqual([e['valor'] for e in prepared['escolhidas']],
                         ['carapaca_basilisco'])
        sheet = self.client.get(reverse('ficha_detail', args=[character.pk]))
        self.assertEqual(sheet.status_code, 200)
        self.assertContains(sheet, 'Carapaça')
        for level, expected in ((7, 2), (11, 2), (15, 3), (18, 3)):
            class_row.nivel = level
            class_row.save(update_fields=['nivel'])
            group = next(g for g in _groups_with_keys(character)
                         if g['kind'] == 'mutagenico_preparado')
            self.assertEqual(group['n'], expected)
        self.assertEqual(character.escolhas.filter(
            tipo='mutagenico_preparado').count(), 1)
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        character.nivel = 6
        character.aventuras = 500
        character.save(update_fields=['nivel', 'aventuras'])
        known = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'mutagenico_conhecido')
        available = [o['slug'] for o in known['universo']
                     if o['slug'] != 'carapaca_basilisco']
        _apply_choices(character, {'escolhas': {
            known['pathbuilder_key']: available[:3]}})
        old = character.escolhas.get(tipo='mutagenico_conhecido',
                                    valor='carapaca_basilisco')
        page = self.client.get(reverse('personagem_subir_nivel', args=[character.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'data-lvl-card="trocar_opcao"')
        actions = [
            {'tipo': 'subir_nivel', 'payload': {'classe': hunter.pk}},
            {'tipo': 'opcao', 'payload': {
                'classe': hunter.pk, 'slug': 'mutagenico_conhecido',
                'val': available[3]}},
            {'tipo': 'trocar_opcao', 'payload': {
                'classe': hunter.pk, 'escolha': old.pk, 'val': available[4]}},
        ]
        response = self.client.post(
            reverse('personagem_levelup_aplicar', args=[character.pk]),
            data=json.dumps({'acoes': actions}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content[:400])
        character.refresh_from_db()
        self.assertEqual(character.nivel, 7)
        self.assertEqual(character.escolhas.get(pk=old.pk).valor, available[4])
        self.assertEqual(character.escolhas.filter(tipo='mutagenico_conhecido').count(), 5)
        self.assertFalse(character.escolhas.filter(tipo='mutagenico_preparado').exists())

    def test_sealed_monk_bonus_styles_persist_with_legacy_page_tags(self):
        from home.content_versions import create_revision, seal_ruleset
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.tag_engine.library import Library
        from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class
        from home.versioned_conditions import snapshot_conditions
        from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
        from home.versioned_library import snapshot_library
        from home.versioned_options import snapshot_options
        from home.versioned_origins import snapshot_origins
        from home.versioned_spells import snapshot_spells

        monk = TbClasse.objects.get(slug='monge')
        changed = []
        for pk in (1520, 1523):
            feature = TbClassehabilidade.objects.get(pk=pk)
            changed.append((feature, feature.tags_json))
            feature.tags_json = ['pick:opcao:estilos_de_ki:2']
            feature.save(update_fields=['tags_json'])
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % monk.pk, inventory_class(monk.pk)),
            snapshot_options(), snapshot_mundane_items(), snapshot_magic_items(),
            snapshot_origins(), snapshot_spells(), snapshot_conditions(),
            snapshot_library(raw=Library(prefer_db=False).raw),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        for feature, tags in changed:
            feature.tags_json = tags
            feature.save(update_fields=['tags_json'])

        for slug, other_default in (
                ('misericordia', 'estilo-debilitante'),
                ('palma-aberta', 'estilo-habil')):
            with self.subTest(subclass_slug=slug):
                character = TbPersonagem.objects.create(
                    dono=self.user, nome='Estilos selados ' + slug)
                TbPersonagemClasse.objects.create(
                    id_personagem=character, id_classe=monk,
                    id_subclasse=TbSubclasse.objects.get(slug=slug),
                    nivel=3, principal=True, ruleset=ruleset)
                for slot, name in enumerate(
                        ('estilo-agil', 'estilo-veloz', 'estilo-barreira')):
                    TbPersonagemEscolha.objects.create(
                        id_personagem=character, origem='Monge: Estilos de Ki',
                        tipo='estilos_de_ki', slot=slot, valor=name,
                        id_opcao=TbOpcaojogo.objects.get(slug=name))
                _apply_choices(character, {'escolhas': {}})
                group = next(g for g in _groups_with_keys(character)
                             if g['tipo'] == 'estilos_de_ki')
                self.assertEqual(group['n'], 5)
                self.assertEqual(group['pendentes'], 1)
                self.assertEqual({e['valor'] for e in group['escolhidas']},
                                 {'estilo-agil', 'estilo-veloz', 'estilo-barreira',
                                  other_default})
                sheet = self.client.get(reverse('ficha_detail', args=[character.pk]))
                self.assertEqual(sheet.status_code, 200)
                self.assertContains(sheet, TbOpcaojogo.objects.get(
                    slug=other_default).nome)

    def test_kensei_styles_replace_ki_catalog_and_add_one_slot(self):
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        monk = TbClasse.objects.get(slug='monge')
        kensei = TbSubclasse.objects.get(slug='kensei')
        character = TbPersonagem.objects.create(dono=self.user, nome='Kensei da Matriz')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=monk, id_subclasse=kensei,
            nivel=3, principal=True)
        expected = {
            'kirisaki', 'enbu', 'takitsubo', 'nobori-ten', 'sogi',
            'hebigiri', 'tengu-kaze', 'kudaki', 'maroi-no-uneri',
        }
        for level in range(3, 21):
            limit = 4 + (level >= 5) + (level >= 11) + (level >= 17)
            row.nivel = level
            row.save(update_fields=['nivel'])
            group = next(g for g in _groups_with_keys(character)
                         if g['tipo'] == 'estilos_de_ki')
            self.assertEqual(group['n'], limit)
            self.assertEqual({o['slug'] for o in group['universo']}, expected)
            card = next(g for g in _choice_groups(character, {'escolhas': {}})
                        if g['key'] == group['pathbuilder_key'])
            self.assertEqual({o['valor'] for o in card['opcoes']}, expected)
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']:
                                                ['kirisaki', 'enbu']}})
        self.assertEqual(character.escolhas.filter(tipo='estilos_de_ki').count(), 2)
        row.nivel = 3
        row.save(update_fields=['nivel'])
        reopened = next(g for g in _groups_with_keys(character)
                        if g['tipo'] == 'estilos_de_ki')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']],
                         ['kirisaki', 'enbu'])

    def test_sealed_kensei_legacy_style_tag_uses_frozen_subclass_catalog(self):
        from home.content_versions import create_revision, seal_ruleset
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys
        from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class
        from home.versioned_conditions import snapshot_conditions
        from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
        from home.versioned_library import snapshot_library
        from home.versioned_options import snapshot_options
        from home.versioned_origins import snapshot_origins
        from home.versioned_spells import snapshot_spells
        from home.tag_engine.library import Library

        monk = TbClasse.objects.get(slug='monge')
        kensei = TbSubclasse.objects.get(slug='kensei')
        feature = TbClassehabilidade.objects.get(pk=1518)
        current_tags = feature.tags_json
        feature.tags_json = ['pick:opcao:estilos_de_ki(kensei):1']
        feature.save(update_fields=['tags_json'])
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % monk.pk, inventory_class(monk.pk)),
            snapshot_options(),
            snapshot_mundane_items(),
            snapshot_magic_items(),
            snapshot_origins(),
            snapshot_spells(),
            snapshot_conditions(),
            snapshot_library(raw=Library(prefer_db=False).raw),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        feature.tags_json = current_tags
        feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Kensei Selado')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=monk, id_subclasse=kensei,
            nivel=3, principal=True, ruleset=ruleset)
        expected = {
            'kirisaki', 'enbu', 'takitsubo', 'nobori-ten', 'sogi',
            'hebigiri', 'tengu-kaze', 'kudaki', 'maroi-no-uneri',
        }
        for level in range(3, 21):
            row.nivel = level
            row.save(update_fields=['nivel'])
            group = next(g for g in _groups_with_keys(character)
                         if g['tipo'] == 'estilos_de_ki')
            self.assertEqual(group['n'], 4 + (level >= 5) +
                             (level >= 11) + (level >= 17))
            self.assertEqual({o['slug'] for o in group['universo']}, expected)
            card = next(g for g in _choice_groups(character, {'escolhas': {}})
                        if g['key'] == group['pathbuilder_key'])
            self.assertEqual({o['valor'] for o in card['opcoes']}, expected)
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']:
                                                ['kirisaki', 'enbu']}})
        row.nivel = 3
        row.save(update_fields=['nivel'])
        reopened = next(g for g in _groups_with_keys(character)
                        if g['tipo'] == 'estilos_de_ki')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']],
                         ['kirisaki', 'enbu'])

        sheet = self.client.get(reverse('ficha_detail', args=[character.pk]))
        self.assertEqual(sheet.status_code, 200)
        self.assertContains(sheet, 'Kirisaki')
        self.assertContains(sheet, 'Enbu')

    def test_elemental_monk_choice_progression_and_rollback_preserves_slots(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        monk = TbClasse.objects.get(slug='monge')
        elemental = TbSubclasse.objects.get(slug='elemental')
        character = TbPersonagem.objects.create(dono=self.user, nome='Elementos da Jornada')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=monk, id_subclasse=elemental,
            nivel=3, principal=True)
        expected = {'agua', 'ar', 'fogo', 'terra'}
        for level, selected in ((3, ['agua']), (6, ['agua', 'ar']),
                                (11, ['agua', 'ar', 'fogo']),
                                (17, ['agua', 'ar', 'fogo', 'terra'])):
            class_row.nivel = level
            class_row.save(update_fields=['nivel'])
            group = next(g for g in _groups_with_keys(character)
                         if g['kind'] == 'elemento')
            self.assertEqual(group['n'], len(selected))
            self.assertEqual({o['slug'] for o in group['universo']}, expected)
            card = next(g for g in _choice_groups(character, {'escolhas': {}})
                        if g['kind'] == 'elemento')
            self.assertEqual({o['valor'] for o in card['opcoes']}, expected)
            _apply_choices(character, {'escolhas': {group['pathbuilder_key']: selected}})
            reopened = next(g for g in picks.resolve_personagem(character)
                            if g['kind'] == 'elemento')
            self.assertEqual([e['valor'] for e in reopened['escolhidas']], selected)

        class_row.nivel = 3
        class_row.save(update_fields=['nivel'])
        lower = next(g for g in picks.resolve_personagem(character)
                     if g['kind'] == 'elemento')
        self.assertEqual(lower['n'], 1)
        self.assertEqual([e['valor'] for e in lower['escolhidas']], ['agua'])
        lower_card = next(g for g in _choice_groups(character, {'escolhas': {}})
                          if g['kind'] == 'elemento')
        self.assertEqual([e['valor'] for e in lower_card['resolvidas']], ['agua'])
        self.assertEqual(lower_card['pendentes'], 0)
        self.assertEqual(character.escolhas.filter(tipo='elemento').count(), 4)
        class_row.nivel = 17
        class_row.save(update_fields=['nivel'])
        higher = next(g for g in picks.resolve_personagem(character)
                      if g['kind'] == 'elemento')
        self.assertEqual([e['valor'] for e in higher['escolhidas']],
                         ['agua', 'ar', 'fogo', 'terra'])

    def test_sealed_elemental_monk_recovers_initial_page_menu(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        monk = TbClasse.objects.get(slug='monge')
        elemental = TbSubclasse.objects.get(slug='elemental')
        source = TbClassehabilidade.objects.get(pk=1512)
        live_tags = list(source.tags_json)
        source.tags_json = [tag.replace(' de [agua, ar, fogo, terra]', '')
                            for tag in live_tags]
        source.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, monk)
        finally:
            source.tags_json = live_tags
            source.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Elemental selado')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=monk, id_subclasse=elemental,
            nivel=3, principal=True, ruleset=ruleset)
        selected = ['agua', 'ar', 'fogo', 'terra']
        for level, count in ((3, 1), (6, 2), (11, 3), (17, 4)):
            row.nivel = level
            row.save(update_fields=['nivel'])
            group = next(g for g in _groups_with_keys(character)
                         if g['kind'] == 'elemento')
            self.assertEqual(group['n'], count)
            self.assertEqual({o['slug'] for o in group['universo']}, set(selected))
            _apply_choices(character, {'escolhas': {
                group['pathbuilder_key']: selected[:count]}})
            reopened = next(g for g in picks.resolve_personagem(character)
                            if g['kind'] == 'elemento')
            self.assertEqual([e['valor'] for e in reopened['escolhidas']],
                             selected[:count])
        row.nivel = 3
        row.save(update_fields=['nivel'])
        self.assertEqual(character.escolhas.filter(tipo='elemento').count(), 4)
        self.assertEqual([e['valor'] for e in next(
            g for g in picks.resolve_personagem(character)
            if g['kind'] == 'elemento')['escolhidas']], ['agua'])
        row.nivel = 17
        row.save(update_fields=['nivel'])
        self.assertEqual([e['valor'] for e in next(
            g for g in picks.resolve_personagem(character)
            if g['kind'] == 'elemento')['escolhidas']], selected)

    def test_paladin_martial_doctrine_exposes_only_selected_branch(self):
        from home import picks
        from home.character_engine import magias_concedidas
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        paladin = TbClasse.objects.get(slug='paladino')
        character = TbPersonagem.objects.create(dono=self.user, nome='Doutrina Marcial')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=paladin, nivel=2, principal=True)

        groups = _groups_with_keys(character)
        doctrine = next(g for g in groups if g['kind'] == 'doutrina_marcial')
        self.assertEqual({o['slug'] for o in doctrine['universo']},
                         {'estilo_de_luta', 'guerreiro_abencoado', 'armas_treinadas'})
        self.assertFalse(any(g['kind'] == 'opcao' for g in groups))
        self.assertEqual(next(g for g in groups if g['kind'] == 'arma')['n'], 2)

        _apply_choices(character, {'escolhas': {
            doctrine['pathbuilder_key']: ['estilo_de_luta']}})
        groups = _groups_with_keys(character)
        style = next(g for g in groups if g['kind'] == 'opcao'
                     and g['tipo'] == 'estilo_de_luta')
        self.assertIn('duelo', {o['slug'] for o in style['universo']})
        self.assertEqual(next(g for g in groups if g['kind'] == 'arma')['n'], 2)
        _apply_choices(character, {'escolhas': {style['pathbuilder_key']: ['duelo']}})
        self.assertEqual(next(g for g in picks.resolve_personagem(character)
                              if g['kind'] == 'opcao')['escolhidas'][0]['valor'], 'duelo')

        character.escolhas.filter(tipo='doutrina_marcial').update(valor='armas_treinadas')
        groups = _groups_with_keys(character)
        self.assertFalse(any(g['kind'] == 'opcao' for g in groups))
        mastery = next(g for g in groups if g['kind'] == 'arma')
        self.assertEqual(mastery['n'], 5)
        self.assertTrue(mastery['universo'])
        card = next(g for g in _choice_groups(character, {'escolhas': {}})
                    if g['kind'] == 'arma')
        selected_masteries = [o['valor'] for o in card['opcoes'][:5]]
        self.assertEqual(len(set(selected_masteries)), 5)
        _apply_choices(character, {'escolhas': {
            mastery['pathbuilder_key']: selected_masteries}})
        restored_mastery = next(g for g in picks.resolve_personagem(character)
                                if g['kind'] == 'arma')
        self.assertEqual({e['valor'] for e in restored_mastery['escolhidas']},
                         set(selected_masteries))

        character.escolhas.filter(tipo='doutrina_marcial').update(valor='guerreiro_abencoado')
        self.assertFalse(any(g['kind'] == 'opcao'
                             for g in _groups_with_keys(character)))
        self.assertEqual(next(g for g in _groups_with_keys(character)
                              if g['kind'] == 'arma')['n'], 2)
        pending = [g for g in magias_concedidas(character)['pendentes']
                   if g['fonte'] == 'Doutrina Marcial']
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['qtd'], 2)
        self.assertTrue(pending[0]['opcoes'])
        self.assertTrue(all(TbMagia.objects.get(slug=slug).nivel == 0
                            for slug in pending[0]['opcoes']))
        from home.views import _lvl_aplicar_magias_concedidas, _sync_magias_concedidas
        chosen_spells = pending[0]['opcoes'][:2]
        self.assertEqual(_lvl_aplicar_magias_concedidas(character, {
            'fonte': 'Doutrina Marcial', 'slot': pending[0]['slot'],
            'magias': chosen_spells}), [])
        _sync_magias_concedidas(character)
        self.assertEqual(set(character.magias.filter(
            origem='Doutrina Marcial').values_list('id_magia__slug', flat=True)),
            set(chosen_spells))
        character.escolhas.filter(tipo='doutrina_marcial').update(valor='estilo_de_luta')
        _sync_magias_concedidas(character)
        self.assertFalse(character.magias.filter(origem='Doutrina Marcial').exists())
        self.assertFalse(any(g['kind'] == 'arma' and g['n'] != 2
                             for g in picks.resolve_personagem(character)))
        self.assertIn('opcao', {g['kind'] for g in picks.resolve_personagem(character)})

        base = self._payload('paladino')
        build = self._build('paladino', classes=[
            {'slug': 'paladino', 'nivel': 2, 'subclasse': ''}])
        preview = self._post_preview(base, build)
        self.assertEqual(preview.status_code, 200, preview.content[:500])
        doctrine_card = next(g for g in preview.json()['build']['escolhas_grupos']
                             if g['kind'] == 'doutrina_marcial')
        build['escolhas'][doctrine_card['key']] = ['estilo_de_luta']
        preview = self._post_preview(base, build)
        self.assertEqual(preview.status_code, 200, preview.content[:500])
        self.assertTrue(any(g['kind'] == 'opcao' and g['limite'] == 1
                            for g in preview.json()['build']['escolhas_grupos']))

    def test_sealed_paladin_doctrine_grants_three_extra_masteries(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        paladin = TbClasse.objects.get(slug='paladino')
        feature = TbClassehabilidade.objects.get(pk=810)
        live_tags = list(feature.tags_json)
        feature.tags_json = [tag for tag in live_tags
                             if not tag.startswith('match(doutrina_marcial)')]
        feature.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, paladin)
        finally:
            feature.tags_json = live_tags
            feature.save(update_fields=['tags_json'])
        character = TbPersonagem.objects.create(dono=self.user, nome='Doutrina legada')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=paladin, ruleset=ruleset,
            nivel=2, principal=True)
        doctrine = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'doutrina_marcial')
        _apply_choices(character, {'escolhas': {
            doctrine['pathbuilder_key']: ['armas_treinadas']}})
        mastery = next(g for g in picks.resolve_personagem(character)
                       if g['kind'] == 'arma')
        self.assertEqual(mastery['n'], 5)
        mastery_key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                           if g['kind'] == 'arma')
        options = next(g['opcoes'] for g in _choice_groups(character, {'escolhas': {}})
                       if g['kind'] == 'arma')
        selected = [option['valor'] for option in options[:5]]
        self.assertEqual(len(set(selected)), 5)
        _apply_choices(character, {'escolhas': {mastery_key: selected}})
        self.assertEqual(character.escolhas.filter(tipo='maestria').count(), 5)
        class_row.nivel = 1
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'doutrina_marcial'
                             for g in picks.resolve_personagem(character)))
        class_row.nivel = 2
        class_row.save(update_fields=['nivel'])
        self.assertEqual({e['valor'] for e in next(
            g for g in picks.resolve_personagem(character)
            if g['kind'] == 'arma')['escolhidas']}, set(selected))
        character.escolhas.filter(tipo='doutrina_marcial').update(valor='estilo_de_luta')
        groups = _groups_with_keys(character)
        self.assertEqual(next(g for g in groups if g['kind'] == 'arma')['n'], 2)
        self.assertEqual(next(g for g in groups if g['kind'] == 'opcao'
                              and g['tipo'] == 'estilo_de_luta')['n'], 1)
        character.escolhas.filter(tipo='doutrina_marcial').update(valor='guerreiro_abencoado')
        groups = _groups_with_keys(character)
        self.assertEqual(next(g for g in groups if g['kind'] == 'arma')['n'], 2)
        self.assertFalse(any(g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta'
                             for g in groups))

    def test_reapplying_classes_preserves_pinned_class_and_profile(self):
        from home.pathbuilder import _apply_classes
        from home.content_versions import create_revision, seal_ruleset
        from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class

        classe = TbClasse.objects.get(slug='cacador')
        character = TbPersonagem.objects.create(dono=self.user, nome='Caçador fixado')
        initial = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, nivel=1, principal=True)
        fighter = TbClasse.objects.get(slug='guerreiro')
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % pk, inventory_class(pk))
            for pk in (classe.pk, fighter.pk)
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        initial.ruleset = ruleset
        initial.save(update_fields=['ruleset'])
        TbPersonagemCacador.objects.update_or_create(
            personagem_classe=initial,
            defaults={'ruleset': ruleset, 'ability': 'wis', 'selected': []})
        subclass = TbSubclasse.objects.filter(id_classe=initial.id_classe).first()
        self.assertIsNotNone(subclass)

        _apply_classes(character, {'classe': 'cacador'}, self._build('cacador', classes=[{
            'slug': 'cacador', 'nivel': 3, 'subclasse': subclass.slug,
        }]))
        updated = character.classes.get(id_classe__slug='cacador')
        self.assertEqual(updated.pk, initial.pk)
        self.assertEqual(updated.ruleset_id, ruleset.pk)
        self.assertEqual(updated.id_subclasse_id, subclass.pk)
        self.assertEqual(updated.cacador_rework.ruleset_id, ruleset.pk)

        _apply_classes(character, {'classe': 'cacador'}, self._build('cacador', classes=[
            {'slug': 'cacador', 'nivel': 3, 'subclasse': subclass.slug},
            {'slug': 'guerreiro', 'nivel': 1, 'subclasse': ''},
        ]))
        self.assertEqual(character.classes.count(), 2)
        self.assertEqual(character.classes.get(id_classe__slug='cacador').pk, initial.pk)
        _apply_classes(character, {'classe': 'cacador'}, self._build('cacador', classes=[{
            'slug': 'cacador', 'nivel': 2, 'subclasse': ''},
        ]))
        self.assertEqual(character.classes.count(), 1)
        reverted = character.classes.get(id_classe__slug='cacador')
        self.assertEqual(reverted.pk, initial.pk)
        self.assertEqual(reverted.ruleset_id, ruleset.pk)
        self.assertEqual(reverted.cacador_rework.ruleset_id, ruleset.pk)

    def test_pinned_class_choices_survive_live_catalog_change(self):
        from home import picks
        from home.pathbuilder import _choice_groups
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        classe = TbClasse.objects.get(slug='guerreiro')
        feature = TbClassehabilidade.objects.filter(
            id_classe=classe, id_subclasse__isnull=True, niveladquirido=1).first()
        self.assertIsNotNone(feature)
        feature.tags_json = list(feature.tags_json or []) + [
            'pick:auditoria:1(={alfa|beta})']
        feature.save(update_fields=['tags_json'])
        ruleset = CreatorPinnedCatalogTests.seal(self, classe)
        feature.tags_json = [tag for tag in feature.tags_json
                             if not tag.startswith('pick:auditoria:')]
        feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Escolha fixada')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, nivel=1,
            principal=True, ruleset=ruleset)
        groups = picks.resolve_personagem(character, kinds={'auditoria'})
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['ruleset'].pk, ruleset.pk)
        self.assertEqual({option['slug'] for option in groups[0]['universo']},
                         {'alfa', 'beta'})
        cards = _choice_groups(character, {'escolhas': {}})
        card = next(card for card in cards if card['kind'] == 'auditoria')
        self.assertEqual(card['limite'], 1)
        self.assertEqual({option['valor'] for option in card['opcoes']},
                         {'alfa', 'beta'})

    def test_mystic_manifestation_list_is_a_real_choice(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        classe = TbClasse.objects.get(slug='mistico')
        feature = TbClassehabilidade.objects.get(
            id_classe=classe, nome='Manifestação Mística', niveladquirido=1)
        character = TbPersonagem.objects.create(dono=self.user, nome='Manifestação')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, nivel=1, principal=True)

        groups = [group for group in picks.resolve_personagem(character)
                  if group['kind'] == 'manifestacao']
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['origem'], feature.nome)
        self.assertEqual(groups[0]['pendentes'], 1)
        self.assertEqual({option['slug'] for option in groups[0]['universo']},
                         {'arma', 'contrato', 'livro', 'marca'})
        cards = [card for card in _choice_groups(character, {'escolhas': {}})
                 if card['kind'] == 'manifestacao']
        self.assertEqual(len(cards), 1)
        self.assertEqual({option['valor'] for option in cards[0]['opcoes']},
                         {'arma', 'contrato', 'livro', 'marca'})
        key = next(group['pathbuilder_key'] for group in _groups_with_keys(character)
                   if group['kind'] == 'manifestacao')
        _apply_choices(character, {'escolhas': {key: ['arma']}})
        self.assertTrue(character.escolhas.filter(tipo='manifestacao', valor='arma').exists())
        reopened = next(group for group in picks.resolve_personagem(character)
                        if group['kind'] == 'manifestacao')
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual(reopened['escolhidas'][0]['valor'], 'arma')

    def test_mystic_book_cantrips_follow_selected_manifestation_and_grant_spells(self):
        from home import picks
        from home.character_engine import magias_concedidas
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys
        from home.views import _sync_magias_concedidas

        mystic = TbClasse.objects.get(slug='mistico')
        feature = TbClassehabilidade.objects.get(pk=1429)
        character = TbPersonagem.objects.create(dono=self.user, nome='Livro Mistico')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=mystic, nivel=1, principal=True)
        groups = _groups_with_keys(character)
        self.assertFalse(any(g['kind'] in ('truque', 'familiar_form') for g in groups))
        manifestation = next(g for g in groups if g['kind'] == 'manifestacao')
        _apply_choices(character, {'escolhas': {
            manifestation['pathbuilder_key']: ['livro']}})
        groups = _groups_with_keys(character)
        cantrips = next(g for g in groups if g['kind'] == 'truque')
        self.assertFalse(any(g['kind'] == 'familiar_form' for g in groups))
        self.assertEqual(cantrips['n'], 3)
        universe = {o['slug'] for o in cantrips['universo']}
        self.assertEqual(universe, set(TbMagia.objects.filter(nivel=0)
                                       .values_list('slug', flat=True)))
        selected = sorted(universe)[:3]
        _apply_choices(character, {'escolhas': {
            cantrips['pathbuilder_key']: selected}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'truque')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']], selected)
        grants = magias_concedidas(character)['concedidas']
        self.assertTrue(set(selected) <= {g['slug'] for g in grants})
        extra = next(slug for slug in universe if slug not in selected)
        TbPersonagemEscolha.objects.create(
            id_personagem=character, tipo='truque', origem=feature.nome,
            slot=99, valor=extra)
        self.assertNotIn(extra, {g['slug'] for g in magias_concedidas(character)['concedidas']})
        _sync_magias_concedidas(character)
        self.assertEqual(set(character.magias.filter(
            sempre_preparada=True, origem=feature.nome)
            .values_list('id_magia__slug', flat=True)), set(selected))
        character.escolhas.filter(tipo='manifestacao').update(valor='arma')
        self.assertFalse(any(g['kind'] == 'truque'
                             for g in picks.resolve_personagem(character)))
        _sync_magias_concedidas(character)
        self.assertFalse(character.magias.filter(
            sempre_preparada=True, origem=feature.nome).exists())
        character.escolhas.filter(tipo='manifestacao').update(valor='contrato')
        groups = _groups_with_keys(character)
        self.assertFalse(any(g['kind'] == 'truque' for g in groups))
        familiar = next(g for g in groups if g['kind'] == 'familiar_form')
        self.assertEqual({o['slug'] for o in familiar['universo']},
                         {'convencional', 'espirito_familiar_mistico'})

    def test_sealed_arcane_hand_techniques_are_activation_choices(self):
        from home import picks
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        rogue = TbClasse.objects.get(slug='ladino')
        subclass = TbSubclasse.objects.get(pk=48)
        ruleset = CreatorPinnedCatalogTests.seal(self, rogue)
        character = TbPersonagem.objects.create(dono=self.user, nome='Mão Arcana selada')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=rogue, id_subclasse=subclass,
            ruleset=ruleset, nivel=3, principal=True)
        for level in (3, 9, 17):
            class_row.nivel = level
            class_row.save(update_fields=['nivel'])
            self.assertFalse(any(g['kind'] == 'tecnica_furtividade'
                                 and g['origem'] == 'Mão Mágica Ardilosa'
                                 for g in picks.resolve_personagem(character)), level)
        self.assertFalse(character.escolhas.filter(tipo='tecnica_furtividade').exists())

    def test_sealed_mystic_manifestation_opens_only_selected_branch(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        mystic = TbClasse.objects.get(slug='mistico')
        ruleset = CreatorPinnedCatalogTests.seal(self, mystic)
        character = TbPersonagem.objects.create(dono=self.user, nome='Manifestação selada')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=mystic, ruleset=ruleset,
            nivel=1, principal=True)
        groups = _groups_with_keys(character)
        self.assertFalse(any(g['kind'] in ('truque', 'familiar_form') for g in groups))
        manifestation = next(g for g in groups if g['kind'] == 'manifestacao')
        _apply_choices(character, {'escolhas': {
            manifestation['pathbuilder_key']: ['livro']}})
        groups = _groups_with_keys(character)
        self.assertEqual(next(g for g in groups if g['kind'] == 'truque')['n'], 3)
        self.assertFalse(any(g['kind'] == 'familiar_form' for g in groups))
        character.escolhas.filter(tipo='manifestacao').update(valor='contrato')
        groups = _groups_with_keys(character)
        self.assertFalse(any(g['kind'] == 'truque' for g in groups))
        familiar = next(g for g in groups if g['kind'] == 'familiar_form')
        self.assertEqual({o['slug'] for o in familiar['universo']},
                         {'convencional', 'espirito_familiar_mistico'})
        _apply_choices(character, {'escolhas': {
            familiar['pathbuilder_key']: ['convencional']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'familiar_form')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']], ['convencional'])

    def test_wizard_philosophers_stone_resistance_persists_and_swaps(self):
        from home import picks, views
        from home.character_engine import derive
        from home.pathbuilder import _apply_choices, _groups_with_keys

        wizard = TbClasse.objects.get(slug='mago')
        subclass = TbSubclasse.objects.get(slug='transmutador')
        feature = TbClassehabilidade.objects.get(pk=1413)
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'conteudo.json'),
                  encoding='utf-8') as fh:
            fixture = json.load(fh)
        source = next(row for row in fixture
                      if row['model'] == 'home.tbclassehabilidade' and row['pk'] == feature.pk)
        feature.tags_json = source['fields']['tags_json']
        feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Pedra Filosofal')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=wizard, id_subclasse=subclass,
            nivel=14, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'pedra_resistencia')
        self.assertEqual(group['n'], 1)
        self.assertEqual(group['swap'], 'long_rest')
        self.assertEqual({o['slug'] for o in group['universo']},
                         {'acido', 'frio', 'fogo', 'raio', 'trovejante'})
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['frio']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'pedra_resistencia')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']], ['frio'])
        # A posse/consumo da pedra ainda nao e representada na ficha: a escolha
        # nao pode conceder resistencia estatica sem esse estado.
        self.assertNotIn('frio', derive(character)['resistencias'])
        self.assertNotIn('fogo', derive(character)['resistencias'])
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'pedra_resistencia')
        self.assertTrue(card['trocavel'])
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'fogo'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual(character.escolhas.get(tipo='pedra_resistencia').valor, 'fogo')
        self.assertNotIn('fogo', derive(character)['resistencias'])
        self.assertNotIn('frio', derive(character)['resistencias'])
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'invalido'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(character.escolhas.get(tipo='pedra_resistencia').valor, 'fogo')
        class_row.nivel = 13
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'pedra_resistencia'
                             for g in picks.resolve_personagem(character)))
        self.assertNotIn('fogo', derive(character)['resistencias'])
        class_row.nivel = 14
        class_row.save(update_fields=['nivel'])
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'pedra_resistencia')
        self.assertEqual([e['valor'] for e in restored['escolhidas']], ['fogo'])

    def test_wizard_arcane_mastery_uses_owned_third_circle_spellbook(self):
        from home import picks, views
        from home.character_engine import magias_concedidas
        from home.pathbuilder import PathbuilderError, _apply_choices, _groups_with_keys

        wizard = TbClasse.objects.get(slug='mago')
        feature = TbClassehabilidade.objects.get(pk=1416)
        spells = list(TbMagia.objects.filter(nivel=3, classes__icontains='Mago')
                      .order_by('slug')[:4])
        self.assertEqual(len(spells), 4)
        character = TbPersonagem.objects.create(dono=self.user, nome='Maestria Arcana')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=wizard, nivel=20, principal=True)
        for spell in spells[:3]:
            TbPersonagemMagia.objects.create(
                id_personagem=character, id_magia=spell, nome=spell.nome,
                nivel=3, origem=wizard.nome)
        for level in range(1, 20):
            class_row.nivel = level
            class_row.save(update_fields=['nivel'])
            self.assertFalse(any(g['kind'] == 'spell'
                                 for g in _groups_with_keys(character)), level)
        class_row.nivel = 20
        class_row.save(update_fields=['nivel'])
        group = next(g for g in _groups_with_keys(character) if g['kind'] == 'spell')
        self.assertEqual(group['n'], 2)
        self.assertEqual({o['slug'] for o in group['universo']},
                         {spell.slug for spell in spells[:3]})
        with self.assertRaises(PathbuilderError):
            _apply_choices(character, {'escolhas': {
                group['pathbuilder_key']: [spells[0].slug, spells[3].slug]}})
        self.assertFalse(character.escolhas.filter(tipo='spell').exists())
        selected = [spell.slug for spell in spells[:2]]
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: selected}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'spell')
        self.assertEqual([row['valor'] for row in reopened['escolhidas']], selected)
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'spell')
        self.assertEqual({row['valor'] for row in card['escolhidas']}, set(selected))
        self.assertTrue(set(selected) <= {g['slug'] for g in
                                         magias_concedidas(character)['concedidas']})
        before = views._pendencias_magias(character)['spells_pend']
        views._sync_magias_concedidas(character)
        self.assertEqual(set(character.magias.filter(
            origem=feature.nome, sempre_preparada=True)
            .values_list('id_magia__slug', flat=True)), set(selected))
        self.assertEqual(views._pendencias_magias(character)['spells_pend'], before)
        stale_choice = character.escolhas.get(tipo='spell', valor=selected[0])
        character.magias.filter(origem=wizard.nome, id_magia=spells[0]).delete()
        pending = next(g for g in _groups_with_keys(character) if g['kind'] == 'spell')
        self.assertEqual(pending['pendentes'], 1)
        views._sync_magias_concedidas(character)
        self.assertEqual(list(character.magias.filter(
            origem=feature.nome, sempre_preparada=True)
            .values_list('id_magia__slug', flat=True)), [selected[1]])
        _apply_choices(character, {'escolhas': {
            pending['pathbuilder_key']: [spells[2].slug]}})
        stale_choice.refresh_from_db()
        self.assertEqual(stale_choice.valor, spells[2].slug)
        views._sync_magias_concedidas(character)
        self.assertEqual(set(character.magias.filter(
            origem=feature.nome, sempre_preparada=True)
            .values_list('id_magia__slug', flat=True)),
            {selected[1], spells[2].slug})
        class_row.nivel = 19
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'spell' for g in picks.resolve_personagem(character)))
        views._sync_magias_concedidas(character)
        self.assertFalse(character.magias.filter(origem=feature.nome).exists())
        self.assertEqual(character.magias.filter(
            origem=wizard.nome, sempre_preparada=False, nivel=3).count(), 2)

    def test_druid_elemental_pipe_menu_persists_and_reopens(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        classe = TbClasse.objects.get(slug='druida')
        subclasse = TbSubclasse.objects.get(slug='circulo-do-pastor-elemental')
        character = TbPersonagem.objects.create(dono=self.user, nome='Pastor elemental')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, id_subclasse=subclasse,
            nivel=3, principal=True)
        group = next(g for g in picks.resolve_personagem(character)
                     if g['kind'] == 'elemento')
        self.assertEqual(group['pendentes'], 1)
        self.assertEqual({o['slug'] for o in group['universo']},
                         {'agua', 'ar', 'fogo', 'terra'})
        card = next(c for c in _choice_groups(character, {'escolhas': {}})
                    if c['kind'] == 'elemento')
        self.assertEqual({o['valor'] for o in card['opcoes']},
                         {'agua', 'ar', 'fogo', 'terra'})
        key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                   if g['kind'] == 'elemento')
        _apply_choices(character, {'escolhas': {key: ['agua']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'elemento')
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual(reopened['escolhidas'][0]['valor'], 'agua')

    def test_artificer_replication_uses_owned_eligible_magic_items(self):
        from home import picks, views
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        artificer = TbClasse.objects.get(slug='artifice')
        character = TbPersonagem.objects.create(dono=self.user, nome='Artifice replicador')
        level = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=artificer, nivel=2, principal=True)
        self.assertFalse(any(g['tipo'] == 'item_magico'
                             for g in picks.resolve_personagem(character)))
        common = TbItemMagico.objects.get(pk=238)
        uncommon = TbItemMagico.objects.get(pk=42)
        rare = TbItemMagico.objects.get(pk=540)
        consumable = TbItemMagico.objects.filter(slot='pocao').first()
        self.assertIsNotNone(consumable)
        for item in (common, uncommon, rare, consumable):
            TbPersonagemItem.objects.create(
                id_personagem=character, id_item_magico=item,
                nome=item.nome, qtd=1)
        infusion_group = next(g for g in _groups_with_keys(character)
                              if g['tipo'] == 'infusao')
        _apply_choices(character, {'escolhas': {
            infusion_group['pathbuilder_key']:
                [o['slug'] for o in infusion_group['universo'][:4]]}})
        replaced = character.escolhas.filter(tipo='infusao').order_by('slot').first()
        live_group = next(g for g in picks.resolve_personagem(character)
                          if g['tipo'] == 'item_magico')
        self.assertEqual({o['slug'] for o in live_group['universo']}, {common.slug})
        live_key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                        if g['tipo'] == 'item_magico')
        _apply_choices(character, {'escolhas': {
            live_key: ['%s|%s' % (common.slug, replaced.pk)]}})
        replaced.refresh_from_db()
        self.assertEqual(replaced.valor, 'item_magico:' + common.slug)
        ruleset = CreatorPinnedCatalogTests.seal(self, artificer)
        level.ruleset = ruleset
        level.save(update_fields=['ruleset'])
        group = next(g for g in _groups_with_keys(character)
                     if g['tipo'] == 'item_magico')
        self.assertFalse(group['universo'])
        _apply_choices(character, {'escolhas': {
            group['pathbuilder_key']: ['%s|%s' % (common.slug, replaced.pk)]}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['tipo'] == 'item_magico')
        self.assertEqual(reopened['escolhidas'][0]['valor'],
                         '%s|%s' % (common.slug, replaced.pk))
        self.assertIsNone(replaced.id_opcao_id)
        level.nivel = 6
        level.save(update_fields=['nivel'])
        group = next(g for g in picks.resolve_personagem(character)
                     if g['tipo'] == 'item_magico')
        self.assertEqual({o['slug'] for o in group['universo']},
                         {uncommon.slug})
        card = next(g for g in views._opcoes_ficha(character)
                    if g['tipo'] == 'item_magico')
        for forbidden in (rare, consumable):
            rejected = self.client.post(
                reverse('personagem_trocar_opcao', args=[character.pk]),
                {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
                 'val': '%s|%s' % (forbidden.slug, replaced.pk)},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertEqual(rejected.status_code, 400)
            replaced.refresh_from_db()
            self.assertEqual(replaced.valor, 'item_magico:' + common.slug)
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': '%s|%s' % (uncommon.slug, replaced.pk)},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        replaced.refresh_from_db()
        self.assertEqual(replaced.valor, 'item_magico:' + uncommon.slug)
        level.nivel = 14
        level.save(update_fields=['nivel'])
        group = next(g for g in picks.resolve_personagem(character)
                     if g['tipo'] == 'item_magico')
        self.assertIn(rare.slug, {o['slug'] for o in group['universo']})
        self.assertNotIn(consumable.slug, {o['slug'] for o in group['universo']})
        level.nivel = 2
        level.save(update_fields=['nivel'])
        group = next(g for g in picks.resolve_personagem(character)
                     if g['tipo'] == 'item_magico')
        self.assertEqual({o['slug'] for o in group['universo']}, {common.slug})
        self.assertEqual(group['escolhidas'][0]['valor'],
                         '%s|%s' % (uncommon.slug, replaced.pk))
        level.nivel = 6
        level.save(update_fields=['nivel'])
        group = next(g for g in picks.resolve_personagem(character)
                     if g['tipo'] == 'item_magico')
        self.assertEqual(group['escolhidas'][0]['valor'],
                         '%s|%s' % (uncommon.slug, replaced.pk))

    def test_artificer_replication_replaces_selected_known_infusion(self):
        from home import picks, views
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        artificer = TbClasse.objects.get(slug='artifice')
        character = TbPersonagem.objects.create(dono=self.user, nome='Artifice infusor')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=artificer, nivel=2, principal=True)
        item = TbItemMagico.objects.get(pk=238)
        TbPersonagemItem.objects.create(
            id_personagem=character, id_item_magico=item, nome=item.nome, qtd=1)
        infusion = next(g for g in _groups_with_keys(character)
                        if g['tipo'] == 'infusao')
        initial = [o['slug'] for o in infusion['universo'][:4]]
        self.assertEqual(len(initial), 4)
        _apply_choices(character, {'escolhas': {infusion['pathbuilder_key']: initial}})
        before = list(character.escolhas.filter(tipo='infusao').order_by('slot'))
        self.assertEqual(len(before), 4)
        studied = next(g for g in _groups_with_keys(character)
                       if g['tipo'] == 'item_magico')
        choice = '%s|%s' % (item.slug, before[1].pk)
        self.assertIn(choice, [o['slug'] + '|' + sub['slug']
                               for o in studied['universo']
                               for sub in o.get('subopcoes', [])])
        builder_group = next(g for g in _choice_groups(character, {})
                             if g['key'] == studied['pathbuilder_key'])
        self.assertIn(choice, {o['valor'] for o in builder_group['opcoes']})
        card = next(g for g in views._opcoes_ficha(character)
                    if g['tipo'] == 'item_magico')
        self.assertTrue(card['dois_niveis'])
        self.assertIn(choice, {sub['val'] for option in card['disponiveis']
                               for sub in option['subs']})
        _apply_choices(character, {'escolhas': {studied['pathbuilder_key']: [choice]}})
        after = list(character.escolhas.filter(tipo='infusao').order_by('slot'))
        self.assertEqual(len(after), 4)
        self.assertEqual(after[1].pk, before[1].pk)
        self.assertEqual(after[1].valor, 'item_magico:' + item.slug)
        self.assertEqual(TbPersonagemEscolha.objects.filter(
            id_personagem=character, tipo='item_magico').count(), 0)
        self.assertEqual(next(g for g in picks.resolve_personagem(character)
                              if g['tipo'] == 'infusao')['pendentes'], 0)
        character.inventario.filter(id_item_magico=item).delete()
        learned = next(g for g in picks.resolve_personagem(character)
                       if g['tipo'] == 'item_magico')
        self.assertEqual(learned['escolhidas'][0]['valor'], choice)
        TbPersonagemItem.objects.create(
            id_personagem=character, id_item_magico=item, nome=item.nome, qtd=1)
        infusion_card = next(g for g in views._opcoes_ficha(character)
                             if g['tipo'] == 'infusao')
        self.assertEqual(infusion_card['usados'], 4)
        self.assertTrue(any(e['nome'].startswith('Replicar: ')
                            for e in infusion_card['escolhidas']))
        replacement = next(o['val'] for o in infusion_card['disponiveis']
                           if o['val'] not in initial)
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': infusion_card['chave'], 'escolha': before[1].pk,
             'val': replacement}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual(character.escolhas.filter(tipo='infusao').count(), 4)
        self.assertFalse(character.escolhas.get(pk=before[1].pk).valor.startswith(
            'item_magico:'))
        self.assertEqual(next(g for g in picks.resolve_personagem(character)
                              if g['tipo'] == 'item_magico')['pendentes'], 4)

    def test_artificer_replication_can_learn_multiple_items_without_extra_slots(self):
        from home import picks, views
        from home.pathbuilder import (PathbuilderError, _apply_choices,
                                      _choice_groups, _groups_with_keys)

        artificer = TbClasse.objects.get(slug='artifice')
        character = TbPersonagem.objects.create(dono=self.user, nome='Artifice multiplas replicas')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=artificer, nivel=2, principal=True)
        items = [TbItemMagico.objects.get(pk=238), TbItemMagico.objects.get(pk=237)]
        for item in items:
            TbPersonagemItem.objects.create(
                id_personagem=character, id_item_magico=item, nome=item.nome, qtd=1)
        infusion = next(g for g in _groups_with_keys(character)
                        if g['tipo'] == 'infusao')
        _apply_choices(character, {'escolhas': {infusion['pathbuilder_key']:
            [o['slug'] for o in infusion['universo'][:4]]}})
        rows = list(character.escolhas.filter(tipo='infusao').order_by('slot'))
        initial_group = next(g for g in _groups_with_keys(character)
                             if g['tipo'] == 'item_magico')
        with self.assertRaises(PathbuilderError):
            _apply_choices(character, {'escolhas': {initial_group['pathbuilder_key']: [
                '%s|%s' % (items[0].slug, rows[0].pk),
                '%s|%s' % (items[0].slug, rows[1].pk)]}})
        self.assertFalse(character.escolhas.filter(
            tipo='infusao', valor__startswith='item_magico:').exists())
        with self.assertRaises(ValueError):
            picks.registry_entry(initial_group['kind'])['persist'](
                character, initial_group, [
                    '%s|%s' % (items[0].slug, rows[0].pk),
                    '%s|%s' % (items[1].slug, rows[0].pk),
                ])
        self.assertFalse(character.escolhas.filter(
            tipo='infusao', valor__startswith='item_magico:').exists())
        for item, row in zip(items, rows[:2]):
            group = next(g for g in _groups_with_keys(character)
                         if g['tipo'] == 'item_magico')
            _apply_choices(character, {'escolhas': {
                group['pathbuilder_key']: ['%s|%s' % (item.slug, row.pk)]}})
        self.assertEqual(character.escolhas.filter(tipo='infusao').count(), 4)
        self.assertEqual(character.escolhas.filter(
            tipo='infusao', valor__startswith='item_magico:').count(), 2)
        learned = next(g for g in picks.resolve_personagem(character)
                       if g['tipo'] == 'item_magico')
        self.assertEqual(learned['usados'], 2)
        self.assertEqual(learned['n'], 4)
        item_key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                        if g['tipo'] == 'item_magico')
        preview = next(g for g in _choice_groups(character, {})
                       if g['key'] == item_key)
        self.assertEqual(preview['pendentes'], 0)
        third = TbItemMagico.objects.get(pk=55)
        TbPersonagemItem.objects.create(
            id_personagem=character, id_item_magico=third, nome=third.nome, qtd=1)
        card = next(g for g in views._opcoes_ficha(character)
                    if g['tipo'] == 'item_magico')
        first = next(e for e in card['escolhidas'] if e['id'] == rows[0].pk)
        self.assertTrue(all(sub['val'].endswith('|%s' % rows[0].pk)
                            for option in first['disponiveis']
                            for sub in option['subs']))
        rejected = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': rows[0].pk,
             'val': '%s|%s' % (third.slug, rows[2].pk)},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(character.escolhas.get(pk=rows[0].pk).valor,
                         'item_magico:' + items[0].slug)
        swapped = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': rows[0].pk,
             'val': '%s|%s' % (third.slug, rows[0].pk)},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(swapped.status_code, 200, swapped.content[:400])
        self.assertEqual(character.escolhas.get(pk=rows[0].pk).valor,
                         'item_magico:' + third.slug)
        self.assertEqual(character.escolhas.get(pk=rows[1].pk).valor,
                         'item_magico:' + items[1].slug)
        self.assertEqual(character.escolhas.filter(tipo='infusao').count(), 4)
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=TbClasse.objects.get(slug='guerreiro'),
            nivel=1, principal=False)
        multiclass = next(g for g in picks.resolve_personagem(character)
                          if g['tipo'] == 'item_magico')
        self.assertEqual(multiclass['n'], 4)
        self.assertEqual(multiclass['usados'], 2)
        self.assertEqual({e['valor'] for e in multiclass['escolhidas']}, {
            '%s|%s' % (third.slug, rows[0].pk),
            '%s|%s' % (items[1].slug, rows[1].pk),
        })

    def test_artificer_defender_core_fixture_offers_two_persistent_choices(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        classe = TbClasse.objects.get(slug='artifice')
        subclasse = TbSubclasse.objects.get(slug='engenheiro-de-construto')
        feature = TbClassehabilidade.objects.get(
            id_classe=classe, id_subclasse=subclasse,
            nome='Especialização de Núcleo', niveladquirido=15)
        self.assertIn('pick:nucleo_defensor:2 de [ofensivo, defensivo, batedor, arcano]',
                      feature.tags_json)
        character = TbPersonagem.objects.create(dono=self.user, nome='Núcleos do defensor')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, id_subclasse=subclasse,
            nivel=15, principal=True)
        group = next(g for g in picks.resolve_personagem(character)
                     if g['kind'] == 'nucleo_defensor')
        self.assertEqual(group['pendentes'], 2)
        self.assertEqual({o['slug'] for o in group['universo']},
                         {'ofensivo', 'defensivo', 'batedor', 'arcano'})
        card = next(c for c in _choice_groups(character, {'escolhas': {}})
                    if c['kind'] == 'nucleo_defensor')
        self.assertEqual(card['limite'], 2)
        key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                   if g['kind'] == 'nucleo_defensor')
        _apply_choices(character, {'escolhas': {key: ['ofensivo', 'arcano']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'nucleo_defensor')
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual({e['valor'] for e in reopened['escolhidas']},
                         {'ofensivo', 'arcano'})

    def test_bard_martial_colleges_offer_weapon_mastery_and_reopen(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        bard = TbClasse.objects.get(slug='bardo')
        for subclass_slug in ('colegio-das-laminas', 'colegio-skald'):
            with self.subTest(subclass=subclass_slug):
                subclasse = TbSubclasse.objects.get(slug=subclass_slug)
                character = TbPersonagem.objects.create(
                    dono=self.user, nome='Maestria ' + subclass_slug)
                TbPersonagemClasse.objects.create(
                    id_personagem=character, id_classe=bard,
                    id_subclasse=subclasse, nivel=3, principal=True)
                group = next(g for g in picks.resolve_personagem(character)
                             if g['kind'] == 'arma')
                self.assertEqual(group['n'], 1)
                card = next(g for g in _choice_groups(character, {'escolhas': {}})
                            if g['kind'] == 'arma')
                options = [o for o in card['opcoes'] if '|' in o['valor']]
                self.assertTrue(options)
                chosen = options[0]['valor']
                key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                           if g['kind'] == 'arma')
                _apply_choices(character, {'escolhas': {key: [chosen]}})
                reopened = next(g for g in picks.resolve_personagem(character)
                                if g['kind'] == 'arma')
                self.assertEqual(reopened['pendentes'], 0)
                self.assertEqual(reopened['escolhidas'][0]['valor'], chosen)
                self.assertTrue(character.escolhas.filter(
                    tipo='maestria', valor=chosen).exists())
                if subclass_slug == 'colegio-skald':
                    style = next(g for g in _groups_with_keys(character)
                                 if g['kind'] == 'opcao'
                                 and g['tipo'] == 'estilo_de_luta')
                    self.assertEqual(style['n'], 1)
                    self.assertTrue({o['slug'] for o in style['universo']}
                                    >= {'arquearia', 'defesa', 'duelo'})
                    _apply_choices(character, {
                        'escolhas': {style['pathbuilder_key']: ['duelo']}})
                    restored = next(g for g in picks.resolve_personagem(character)
                                    if g['kind'] == 'opcao'
                                    and g['tipo'] == 'estilo_de_luta')
                    self.assertEqual(restored['pendentes'], 0)
                    self.assertEqual(restored['escolhidas'][0]['valor'], 'duelo')

    def test_multiclass_weapon_mastery_slots_remain_separate(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        fighter = TbClasse.objects.get(slug='guerreiro')
        bard = TbClasse.objects.get(slug='bardo')
        blades = TbSubclasse.objects.get(slug='colegio-das-laminas')
        character = TbPersonagem.objects.create(
            dono=self.user, nome='Maestrias multiclasse')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=fighter, nivel=1, principal=True)
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=bard, id_subclasse=blades,
            nivel=3, principal=False)
        groups = [g for g in _groups_with_keys(character) if g['kind'] == 'arma']
        self.assertEqual({g['classe'] for g in groups}, {'Guerreiro', 'Bardo'})
        bard_group = next(g for g in groups if g['classe'] == 'Bardo')
        self.assertEqual(bard_group['n'], 1)
        card = next(g for g in _choice_groups(character, {'escolhas': {}})
                    if g['key'] == bard_group['pathbuilder_key'])
        chosen = next(o['valor'] for o in card['opcoes'] if '|' in o['valor'])
        _apply_choices(character, {
            'escolhas': {bard_group['pathbuilder_key']: [chosen]}})
        reopened = [g for g in picks.resolve_personagem(character)
                    if g['kind'] == 'arma']
        bard_after = next(g for g in reopened if g['classe'] == 'Bardo')
        fighter_after = next(g for g in reopened if g['classe'] == 'Guerreiro')
        self.assertEqual(bard_after['pendentes'], 0)
        self.assertEqual(fighter_after['usados'], 0)
        self.assertEqual(fighter_after['pendentes'], fighter_after['n'])

    def test_multiclass_fighting_styles_keep_each_class_choice(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        fighter = TbClasse.objects.get(slug='guerreiro')
        bard = TbClasse.objects.get(slug='bardo')
        skald = TbSubclasse.objects.get(slug='colegio-skald')
        character = TbPersonagem.objects.create(dono=self.user, nome='Estilos multiclasse')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=fighter, nivel=1, principal=True)
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=bard, id_subclasse=skald,
            nivel=3, principal=False)
        groups = [g for g in _groups_with_keys(character)
                  if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta']
        self.assertEqual({g['classe'] for g in groups}, {'Guerreiro', 'Bardo'})
        bard_group = next(g for g in groups if g['classe'] == 'Bardo')
        _apply_choices(character, {
            'escolhas': {bard_group['pathbuilder_key']: ['duelo']}})
        reopened = [g for g in picks.resolve_personagem(character)
                    if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta']
        bard_after = next(g for g in reopened if g['classe'] == 'Bardo')
        fighter_after = next(g for g in reopened if g['classe'] == 'Guerreiro')
        self.assertEqual([e['valor'] for e in bard_after['escolhidas']], ['duelo'])
        self.assertEqual(fighter_after['usados'], 0)
        fighter_group = next(g for g in _groups_with_keys(character)
                             if g['kind'] == 'opcao' and g['classe'] == 'Guerreiro'
                             and g['tipo'] == 'estilo_de_luta')
        _apply_choices(character, {
            'escolhas': {fighter_group['pathbuilder_key']: ['defesa']}})
        reopened = [g for g in picks.resolve_personagem(character)
                    if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta']
        self.assertEqual({g['classe']: [e['valor'] for e in g['escolhidas']]
                          for g in reopened},
                         {'Bardo': ['duelo'], 'Guerreiro': ['defesa']})
        cards = [g for g in _choice_groups(character, {'escolhas': {}})
                 if g['kind'] == 'opcao' and g['label'] == 'Estilo de Luta']
        self.assertEqual({g['classe']: [e['valor'] for e in g['resolvidas']]
                          for g in cards},
                         {'Bardo': ['duelo'], 'Guerreiro': ['defesa']})

    def test_single_class_legacy_style_origin_still_reopens(self):
        from home import picks

        fighter = TbClasse.objects.get(slug='guerreiro')
        duel = TbOpcaojogo.objects.get(slug='duelo', tipo='Estilo de Luta')
        character = TbPersonagem.objects.create(dono=self.user, nome='Estilo legado')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=fighter, nivel=1, principal=True)
        TbPersonagemEscolha.objects.create(
            id_personagem=character, origem='Estilo de Luta',
            tipo='estilo_de_luta', slot=0, valor='duelo', id_opcao=duel)
        group = next(g for g in picks.resolve_personagem(character)
                     if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta')
        self.assertEqual([e['valor'] for e in group['escolhidas']], ['duelo'])
        self.assertEqual(group['pendentes'], 0)

    def test_bard_blades_fighting_style_matches_page_and_reopens(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys

        bard = TbClasse.objects.get(slug='bardo')
        blades = TbSubclasse.objects.get(slug='colegio-das-laminas')
        feature = TbClassehabilidade.objects.get(
            id_classe=bard, id_subclasse=blades, nome='Estilo de Luta')
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'conteudo.json'),
                  encoding='utf-8') as fh:
            fixture = json.load(fh)
        source = next(row for row in fixture
                      if row['model'] == 'home.tbclassehabilidade' and row['pk'] == feature.pk)
        feature.tags_json = source['fields']['tags_json']
        feature.save(update_fields=['tags_json'])
        self.assertTrue(any('de:[defesa,duelo,combate-com-duas-armas,combate-com-armas-grandes]'
                            in tag for tag in feature.tags_json))
        character = TbPersonagem.objects.create(dono=self.user, nome='Estilo das Laminas')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=bard, id_subclasse=blades,
            nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta')
        expected = {'defesa', 'duelo', 'combate-com-duas-armas',
                    'combate-com-armas-grandes'}
        self.assertEqual({option['slug'] for option in group['universo']}, expected)
        self.assertEqual(group['n'], 1)
        self.assertEqual(group['swap'], 'level_up')
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['duelo']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta')
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual(reopened['escolhidas'][0]['valor'], 'duelo')
        class_row.nivel = 2
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta'
                             for g in picks.resolve_personagem(character)))
        class_row.nivel = 3
        class_row.save(update_fields=['nivel'])
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta')
        self.assertEqual(restored['escolhidas'][0]['valor'], 'duelo')

    def test_language_choices_from_features_persist_as_proficiency(self):
        from home import picks
        from home.character_engine import derive
        from home.models import TbIdioma
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        idiomas = list(TbIdioma.objects.order_by('pk')[:3])
        self.assertEqual(len(idiomas), 3)
        for classe_slug, subclasse_slug, nivel, limite in (
                ('ladino', 'trilha-do-assassino', 9, 2),
                ('monge', 'punho-do-dragao', 3, 1)):
            with self.subTest(classe=classe_slug):
                classe = TbClasse.objects.get(slug=classe_slug)
                subclasse = TbSubclasse.objects.get(slug=subclasse_slug)
                character = TbPersonagem.objects.create(
                    dono=self.user, nome='Idiomas %s' % classe_slug)
                TbPersonagemClasse.objects.create(
                    id_personagem=character, id_classe=classe,
                    id_subclasse=subclasse, nivel=nivel, principal=True)
                group = next(g for g in picks.resolve_personagem(character)
                             if g['kind'] == 'idioma')
                self.assertEqual(group['n'], limite)
                card = next(g for g in _choice_groups(character, {'escolhas': {}})
                            if g['kind'] == 'idioma')
                self.assertTrue({i.slug for i in idiomas}.issubset(
                    {o['valor'] for o in card['opcoes']}))
                key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                           if g['kind'] == 'idioma')
                chosen = idiomas[:limite]
                _apply_choices(character, {
                    'escolhas': {key: [item.slug for item in chosen]}})
                reopened = next(g for g in picks.resolve_personagem(character)
                                if g['kind'] == 'idioma')
                self.assertEqual(reopened['pendentes'], 0)
                self.assertEqual({e['valor'] for e in reopened['escolhidas']},
                                 {item.slug for item in chosen})
                self.assertEqual(character.proficiencias.filter(
                    tipo='idioma', nome__in=[item.nome for item in chosen]).count(),
                    limite)
                self.assertTrue({item.nome for item in chosen}.issubset(
                    set(derive(character)['idiomas'])))

    def test_language_choices_from_race_essence_and_talent_keep_origins(self):
        from home import picks
        from home.character_engine import derive
        from home.models import TbIdioma
        from home.pathbuilder import _apply_choices, _groups_with_keys

        human = TbRaca.objects.get(pk=35)
        essence = TbEssencia.objects.get(pk=29)
        linguist = TbTalento.objects.get(pk=136)
        classe = TbClasse.objects.get(slug='guerreiro')
        character = TbPersonagem.objects.create(
            dono=self.user, nome='Idiomas combinados', id_raca=human,
            id_essencia=essence)
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, nivel=1,
            principal=True)
        TbPersonagemTalento.objects.create(
            id_personagem=character, id_talento=linguist,
            nome=linguist.nome, categoria='geral', nivel=1)
        TbPersonagemTalento.objects.create(
            id_personagem=character, nome='Contratos e Decretos',
            categoria='racial', nivel=1)
        from home.character_engine import _talentos
        self.assertIn('Contratos e Decretos',
                      [source.nome for _, _, source, _ in _talentos(character)])
        groups = [g for g in _groups_with_keys(character)
                  if g['kind'] == 'idioma']
        self.assertEqual({g['origem']: g['n'] for g in groups},
                         {'Poliglota': 2, 'Contratos e Decretos': 1,
                          'Linguista': 3})
        languages = list(TbIdioma.objects.exclude(slug='comum').order_by('pk')[:6])
        self.assertEqual(len(languages), 6)
        selected = {}
        offset = 0
        for group in groups:
            count = group['n']
            selected[group['pathbuilder_key']] = [
                language.slug for language in languages[offset:offset + count]]
            offset += count
        _apply_choices(character, {'escolhas': selected})
        reopened = [g for g in picks.resolve_personagem(character)
                    if g['kind'] == 'idioma']
        self.assertEqual(len(reopened), 3)
        self.assertTrue(all(g['pendentes'] == 0 for g in reopened))
        self.assertEqual({e['valor'] for g in reopened for e in g['escolhidas']},
                         {language.slug for language in languages})
        self.assertEqual(character.proficiencias.filter(
            tipo='idioma', nome__in=[language.nome for language in languages]).count(), 6)
        self.assertTrue({language.nome for language in languages}.issubset(
            set(derive(character)['idiomas'])))

    def test_monk_elemental_choice_progresses_and_reopens(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys

        classe = TbClasse.objects.get(slug='monge')
        subclasse = TbSubclasse.objects.get(slug='elemental')
        character = TbPersonagem.objects.create(dono=self.user, nome='Monge elemental')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, id_subclasse=subclasse,
            nivel=3, principal=True)
        options = {'agua', 'ar', 'fogo', 'terra'}
        for level, count in ((3, 1), (6, 2), (11, 3), (17, 4)):
            row.nivel = level
            row.save(update_fields=['nivel'])
            group = next(g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'elemento')
            self.assertEqual(group['n'], count)
            self.assertEqual({o['slug'] for o in group['universo']}, options)
            key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                       if g['kind'] == 'elemento')
            _apply_choices(character, {'escolhas': {key: sorted(options)[:count]}})
            reopened = next(g for g in picks.resolve_personagem(character)
                            if g['kind'] == 'elemento')
            self.assertEqual(reopened['pendentes'], 0)
            self.assertEqual({e['valor'] for e in reopened['escolhidas']},
                             set(sorted(options)[:count]))
        row.nivel = 3
        row.save(update_fields=['nivel'])
        regressed = next(g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'elemento')
        self.assertEqual(regressed['n'], 1)
        self.assertEqual([e['valor'] for e in regressed['escolhidas']], ['agua'])
        self.assertEqual(TbPersonagemEscolha.objects.filter(
            id_personagem=character, tipo=regressed['persist_tipo'],
            origem=regressed['origem']).count(), 4)
        row.nivel = 17
        row.save(update_fields=['nivel'])
        self.assertEqual(next(g for g in picks.resolve_personagem(character)
                              if g['kind'] == 'elemento')['pendentes'], 0)

    def test_monk_dragon_pillar_choice_persists_and_reopens(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys

        classe = TbClasse.objects.get(slug='monge')
        subclasse = TbSubclasse.objects.get(slug='punho-do-dragao')
        character = TbPersonagem.objects.create(dono=self.user, nome='Pilar draconico')
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, id_subclasse=subclasse,
            nivel=3, principal=True)
        expected = {'fogo', 'agua', 'ar', 'terra', 'luz', 'escuridao'}
        group = next(g for g in picks.resolve_personagem(character)
                     if g['kind'] == 'pilar_draconico')
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']}, expected)
        card = next(g for g in _choice_groups(character, {'escolhas': {}})
                    if g['kind'] == 'pilar_draconico')
        self.assertEqual({o['valor'] for o in card['opcoes']}, expected)
        key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                   if g['kind'] == 'pilar_draconico')
        _apply_choices(character, {'escolhas': {key: ['fogo']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'pilar_draconico')
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual(reopened['escolhidas'][0]['valor'], 'fogo')

    def test_sealed_dragon_pillar_recovers_page_menu(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        monk = TbClasse.objects.get(slug='monge')
        subclass = TbSubclasse.objects.get(slug='punho-do-dragao')
        pillar = TbClassehabilidade.objects.get(pk=1530)
        live_tags = list(pillar.tags_json)
        pillar.tags_json = [tag.replace(
            ' de [fogo, agua, ar, terra, luz, escuridao]', '')
            for tag in live_tags]
        pillar.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, monk)
        finally:
            pillar.tags_json = live_tags
            pillar.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Pilar selado')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=monk, id_subclasse=subclass,
            ruleset=ruleset, nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'pilar_draconico')
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']},
                         {'fogo', 'agua', 'ar', 'terra', 'luz', 'escuridao'})
        _apply_choices(character, {'escolhas': {
            group['pathbuilder_key']: ['fogo']}})
        row.nivel = 2
        row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'pilar_draconico'
                             for g in picks.resolve_personagem(character)))
        row.nivel = 3
        row.save(update_fields=['nivel'])
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'pilar_draconico')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']], ['fogo'])

    def test_monk_dragon_avatar_aspect_persists_and_swaps_at_rest(self):
        from home import picks, views
        from home.pathbuilder import _apply_choices, _groups_with_keys

        classe = TbClasse.objects.get(slug='monge')
        subclasse = TbSubclasse.objects.get(slug='punho-do-dragao')
        feature = TbClassehabilidade.objects.get(pk=1529)
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'conteudo.json'),
                  encoding='utf-8') as fh:
            fixture = json.load(fh)
        source = next(row for row in fixture
                      if row['model'] == 'home.tbclassehabilidade' and row['pk'] == feature.pk)
        feature.tags_json = source['fields']['tags_json']
        feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Avatar draconico')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, id_subclasse=subclasse,
            nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'dragao_aspecto')
        self.assertEqual(group['n'], 1)
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']},
                         {'cromatico', 'metalico'})
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['cromatico']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'dragao_aspecto')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']], ['cromatico'])
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'dragao_aspecto')
        self.assertTrue(card['trocavel'])
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'metalico'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual(character.escolhas.get(tipo='dragao_aspecto').valor, 'metalico')
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'invalido'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(character.escolhas.get(tipo='dragao_aspecto').valor, 'metalico')
        class_row.nivel = 2
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'dragao_aspecto'
                             for g in picks.resolve_personagem(character)))
        class_row.nivel = 3
        class_row.save(update_fields=['nivel'])
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'dragao_aspecto')
        self.assertEqual([e['valor'] for e in restored['escolhidas']], ['metalico'])
        shenlong_source = next(row for row in fixture
                               if row['model'] == 'home.tbclassehabilidade' and row['pk'] == 1582)
        self.assertNotIn('pick:dragao_aspecto', ' '.join(shenlong_source['fields']['tags_json']))
        shenlong_feature = TbClassehabilidade.objects.get(pk=1582)
        shenlong_feature.tags_json = shenlong_source['fields']['tags_json']
        shenlong_feature.save(update_fields=['tags_json'])
        class_row.nivel = 17
        class_row.save(update_fields=['nivel'])
        aspect_groups = [g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'dragao_aspecto']
        self.assertEqual(len(aspect_groups), 1)
        self.assertEqual([e['valor'] for e in aspect_groups[0]['escolhidas']], ['metalico'])
        self.assertEqual(character.escolhas.filter(tipo='dragao_aspecto').count(), 1)

    def test_sealed_dragon_avatar_rest_attunement_survives_reopen(self):
        from home import picks, views
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        monk = TbClasse.objects.get(slug='monge')
        subclass = TbSubclasse.objects.get(slug='punho-do-dragao')
        avatar = TbClassehabilidade.objects.get(pk=1529)
        live_tags = list(avatar.tags_json)
        avatar.tags_json = [
            'trigger=short_rest, trigger=long_rest, instant{ pick:dragao_aspecto:1 }',
        ] + [tag for tag in live_tags if 'pick:dragao_aspecto:1' not in tag]
        avatar.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, monk)
        finally:
            avatar.tags_json = live_tags
            avatar.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Avatar selado')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=monk, id_subclasse=subclass,
            ruleset=ruleset, nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'dragao_aspecto')
        self.assertEqual(group['n'], 1)
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']},
                         {'cromatico', 'metalico'})
        _apply_choices(character, {'escolhas': {
            group['pathbuilder_key']: ['cromatico']}})
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'dragao_aspecto')
        self.assertTrue(card['trocavel'])
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'metalico'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual(character.escolhas.get(tipo='dragao_aspecto').valor, 'metalico')
        row.nivel = 2
        row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'dragao_aspecto'
                             for g in picks.resolve_personagem(character)))
        row.nivel = 3
        row.save(update_fields=['nivel'])
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'dragao_aspecto')
        self.assertEqual([e['valor'] for e in restored['escolhidas']], ['metalico'])
        self.assertEqual(character.escolhas.filter(tipo='dragao_aspecto').count(), 1)

    def test_sealed_shenlong_activation_does_not_repeat_attuned_aspect(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        monk = TbClasse.objects.get(slug='monge')
        subclass = TbSubclasse.objects.get(slug='punho-do-dragao')
        shenlong = TbClassehabilidade.objects.get(pk=1582)
        live_tags = list(shenlong.tags_json)
        shenlong.tags_json = live_tags + [
            'action=bonus_action, instant{ pick:dragao_aspecto:1(reset:long_rest) }',
            'swap:long_rest',
        ]
        shenlong.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, monk)
        finally:
            shenlong.tags_json = live_tags
            shenlong.save(update_fields=['tags_json'])
        character = TbPersonagem.objects.create(dono=self.user, nome='ShenLong legado')
        level = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=monk, id_subclasse=subclass,
            ruleset=ruleset, nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'dragao_aspecto')
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['cromatico']}})
        level.nivel = 17
        level.save(update_fields=['nivel'])
        aspect_groups = [g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'dragao_aspecto']
        self.assertEqual(len(aspect_groups), 1)
        self.assertEqual(aspect_groups[0]['n'], 1)
        self.assertEqual([e['valor'] for e in aspect_groups[0]['escolhidas']], ['cromatico'])
        self.assertEqual(character.escolhas.filter(tipo='dragao_aspecto').count(), 1)

    def test_druid_land_terrain_fixture_progresses_and_reopens(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys

        classe = TbClasse.objects.get(slug='druida')
        subclasse = TbSubclasse.objects.get(slug='circulo-da-terra')
        character = TbPersonagem.objects.create(dono=self.user, nome='Terrenos')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, id_subclasse=subclasse,
            nivel=3, principal=True)
        expected = {'costa', 'deserto', 'floresta', 'campina',
                    'montanha', 'pantano', 'tundra', 'subterraneo'}
        group = next(g for g in picks.resolve_personagem(character)
                     if g['kind'] == 'terreno')
        self.assertEqual(group['n'], 1)
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']}, expected)
        key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                   if g['kind'] == 'terreno')
        _apply_choices(character, {'escolhas': {key: ['costa']}})
        class_row.nivel = 18
        class_row.save(update_fields=['nivel'])
        advanced = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'terreno')
        self.assertEqual(advanced['n'], 2)
        self.assertEqual(advanced['pendentes'], 1)
        self.assertEqual({o['slug'] for o in advanced['universo']}, expected)
        key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                   if g['kind'] == 'terreno')
        _apply_choices(character, {'escolhas': {key: ['costa', 'tundra']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'terreno')
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual({e['valor'] for e in reopened['escolhidas']},
                         {'costa', 'tundra'})
        class_row.nivel = 3
        class_row.save(update_fields=['nivel'])
        regressed = next(g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'terreno')
        self.assertEqual(regressed['n'], 1)
        self.assertEqual({e['valor'] for e in regressed['escolhidas']},
                         {'costa'})
        self.assertEqual({e.valor for e in character.escolhas.filter(tipo='terreno')},
                         {'costa', 'tundra'})
        class_row.nivel = 18
        class_row.save(update_fields=['nivel'])
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'terreno')
        self.assertEqual(restored['n'], 2)
        self.assertEqual({e['valor'] for e in restored['escolhidas']},
                         {'costa', 'tundra'})

    def test_sealed_druid_land_terrain_uses_page_list_and_rest_swap(self):
        from home import picks, views
        from home.character_engine import magias_concedidas
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        druid = TbClasse.objects.get(slug='druida')
        subclass = TbSubclasse.objects.get(slug='circulo-da-terra')
        early = TbClassehabilidade.objects.get(pk=1200)
        late = TbClassehabilidade.objects.get(pk=1236)
        live_early, live_late = list(early.tags_json), list(late.tags_json)
        expected = {'costa', 'deserto', 'floresta', 'campina',
                    'montanha', 'pantano', 'tundra', 'subterraneo'}
        early.tags_json = [tag.split(' de [')[0] if tag.startswith('pick:terreno:')
                           else tag for tag in live_early if tag != 'swap:short_or_long']
        late.tags_json = [tag.split(' de [')[0] if tag.startswith('pick:terreno:')
                          else tag for tag in live_late if tag != 'swap:short_or_long']
        early.save(update_fields=['tags_json'])
        late.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, druid)
        finally:
            early.tags_json, late.tags_json = live_early, live_late
            early.save(update_fields=['tags_json'])
            late.save(update_fields=['tags_json'])
        checksum = ruleset.checksum
        character = TbPersonagem.objects.create(dono=self.user, nome='Druida terreno legado')
        level = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=druid, id_subclasse=subclass,
            ruleset=ruleset, nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character) if g['kind'] == 'terreno')
        self.assertEqual(group['n'], 1)
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']}, expected)
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['costa']}})
        granted = {row['slug'] for row in magias_concedidas(
            character, ruleset=ruleset)['concedidas']}
        self.assertTrue({'moldar-agua', 'nevoa-obscurecente', 'passo-nebuloso'} <= granted)
        level.nivel = 9
        level.save(update_fields=['nivel'])
        ninth_grants = {row['slug'] for row in magias_concedidas(
            character, ruleset=ruleset)['concedidas']}
        self.assertIn('voragem', ninth_grants)
        self.assertNotIn('redemoinho', ninth_grants)
        level.nivel = 18
        level.save(update_fields=['nivel'])
        group = next(g for g in _groups_with_keys(character) if g['kind'] == 'terreno')
        self.assertEqual(group['n'], 2)
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']}, expected)
        self.assertEqual([e['valor'] for e in group['escolhidas']], ['costa'])
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['tundra']}})
        card = next(g for g in views._opcoes_ficha(character) if g['kind'] == 'terreno')
        self.assertTrue(card['trocavel'])
        self.assertEqual({e['valor'] for e in card['escolhidas']}, {'costa', 'tundra'})
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'floresta'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual({e.valor for e in character.escolhas.filter(tipo='terreno')},
                         {'floresta', 'tundra'})
        prepared = set(character.magias.filter(
            sempre_preparada=True).values_list('id_magia__slug', flat=True))
        self.assertIn('chicote-de-espinhos', prepared)
        self.assertNotIn('moldar-agua', prepared)
        granted = {row['slug'] for row in magias_concedidas(
            character, ruleset=ruleset)['concedidas']}
        self.assertIn('chicote-de-espinhos', granted)
        self.assertNotIn('moldar-agua', granted)
        level.nivel = 3
        level.save(update_fields=['nivel'])
        self.assertEqual(next(g for g in picks.resolve_personagem(character)
                              if g['kind'] == 'terreno')['n'], 1)
        regressed_grants = {row['slug'] for row in magias_concedidas(
            character, ruleset=ruleset)['concedidas']}
        self.assertIn('chicote-de-espinhos', regressed_grants)
        self.assertNotIn('mordida-gelida', regressed_grants)
        level.nivel = 18
        level.save(update_fields=['nivel'])
        restored_grants = {row['slug'] for row in magias_concedidas(
            character, ruleset=ruleset)['concedidas']}
        self.assertIn('mordida-gelida', restored_grants)
        self.assertEqual({e['valor'] for e in next(g for g in picks.resolve_personagem(character)
                                                   if g['kind'] == 'terreno')['escolhidas']},
                         {'floresta', 'tundra'})
        self.assertEqual(ruleset.checksum, checksum)

    def test_terrain_uses_approved_catalog_circles(self):
        from home.character_engine import magias_concedidas
        from home.pathbuilder import _apply_choices, _groups_with_keys

        druid = TbClasse.objects.get(slug='druida')
        subclass = TbSubclasse.objects.get(slug='circulo-da-terra')
        character = TbPersonagem.objects.create(dono=self.user, nome='Terrenos corrigidos')
        level = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=druid, id_subclasse=subclass,
            nivel=5, principal=True)
        key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                   if g['kind'] == 'terreno')
        _apply_choices(character, {'escolhas': {key: ['floresta']}})

        def granted():
            return {row['slug'] for row in magias_concedidas(character)['concedidas']}

        self.assertNotIn('vinha-restritiva', granted())
        self.assertNotIn('muralha-de-espinhos', granted())
        level.nivel = 7
        level.save(update_fields=['nivel'])
        self.assertIn('vinha-restritiva', granted())
        self.assertNotIn('muralha-de-espinhos', granted())
        level.nivel = 11
        level.save(update_fields=['nivel'])
        self.assertIn('muralha-de-espinhos', granted())
        character.escolhas.filter(tipo='terreno').update(valor='montanha')
        level.nivel = 5
        level.save(update_fields=['nivel'])
        self.assertIn('terra-eruptiva', granted())
        self.assertNotIn('muralha-de-espinhos', granted())

    def test_infernal_rest_resistance_all_non_fire_types(self):
        from home.character_engine import derive
        from home.pathbuilder import _apply_choices, _groups_with_keys

        mystic = TbClasse.objects.get(slug='mistico')
        subclass = TbSubclasse.objects.get(slug='o-infero')
        character = TbPersonagem.objects.create(dono=self.user, nome='Ínfero corrigido')
        level = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=mystic, id_subclasse=subclass,
            nivel=10, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'resistencia_infera')
        options = {option['slug'] for option in group['universo']}
        self.assertEqual(options, {
            'acido', 'concussivo', 'cortante', 'perfurante', 'frio', 'energia',
            'eletrico', 'necrotico', 'veneno', 'psiquico', 'radiante', 'trovejante'})
        self.assertEqual(group['swap'], 'short_or_long')
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['concussivo']}})
        self.assertEqual(character.escolhas.get(tipo='resistencia_infera').valor,
                         'concussivo')
        self.assertTrue({'fogo', 'concussivo'} <= set(derive(character)['resistencias']))
        level.nivel = 9
        level.save(update_fields=['nivel'])
        self.assertNotIn('concussivo', derive(character)['resistencias'])
        level.nivel = 10
        level.save(update_fields=['nivel'])
        self.assertIn('concussivo', derive(character)['resistencias'])

    def test_sealed_editorial_corrections_leave_snapshot_unchanged(self):
        import json
        from pathlib import Path
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests
        from home.versioned_classes import VersionedClassCatalog

        supplements = json.loads((Path(__file__).parent / 'rules' /
                                  'legacy_choice_supplements.json').read_text(encoding='utf-8'))
        cases = ((6, 1200, 'descricao'), (11, 1469, 'tags_json'))
        for class_id, feature_pk, field in cases:
            with self.subTest(feature_pk=feature_pk):
                feature = TbClassehabilidade.objects.get(pk=feature_pk)
                current = getattr(feature, field)
                if field == 'descricao':
                    old = current
                    for before, after in reversed(
                            supplements['description_supplements'][0]['replacements']):
                        self.assertIn(after, old)
                        old = old.replace(after, before)
                else:
                    supplement = supplements['tag_supplements'][0]
                    old = [tag for tag in current if tag not in supplement['new_tags']]
                    old.insert(1, supplement['old_tag'])
                setattr(feature, field, old)
                feature.save(update_fields=[field])
                try:
                    ruleset = CreatorPinnedCatalogTests.seal(
                        self, TbClasse.objects.get(pk=class_id))
                finally:
                    setattr(feature, field, current)
                    feature.save(update_fields=[field])
                checksum = ruleset.checksum
                catalog = VersionedClassCatalog(ruleset, class_id)
                resolved = next(row for row in catalog.collections[TbClassehabilidade]
                                if row.pk == feature_pk)
                self.assertEqual(getattr(resolved, field), current)
                self.assertEqual(ruleset.checksum, checksum)
                if feature_pk == 1469:
                    from home.character_engine import derive
                    from home.pathbuilder import _apply_choices, _groups_with_keys
                    character = TbPersonagem.objects.create(
                        dono=self.user, nome='Ínfero selado corrigido')
                    TbPersonagemClasse.objects.create(
                        id_personagem=character, id_classe=TbClasse.objects.get(pk=class_id),
                        id_subclasse=TbSubclasse.objects.get(pk=139), ruleset=ruleset,
                        nivel=10, principal=True)
                    group = next(g for g in _groups_with_keys(character)
                                 if g['kind'] == 'resistencia_infera')
                    self.assertIn('concussivo', {o['slug'] for o in group['universo']})
                    _apply_choices(character, {'escolhas': {
                        group['pathbuilder_key']: ['concussivo']}})
                    self.assertTrue({'fogo', 'concussivo'} <= set(
                        derive(character, ruleset=ruleset)['resistencias']))

    def test_druid_terrain_spells_appear_in_builder_preview(self):
        base = self._payload('druida')
        build = self._build('druida', classes=[
            {'slug': 'druida', 'nivel': 3, 'subclasse': 'circulo-da-terra'}])
        initial = self._post_preview(base, build)
        self.assertEqual(initial.status_code, 200, initial.content[:400])
        terrain = next(group for group in initial.json()['build']['escolhas_grupos']
                       if group['kind'] == 'terreno')
        build['escolhas'][terrain['key']] = ['costa']
        count_before = TbPersonagem.objects.count()
        preview = self._post_preview(base, build)
        self.assertEqual(preview.status_code, 200, preview.content[:400])
        granted = {row['nome'] for row in preview.json()['build']['magias']}
        expected = set(TbMagia.objects.filter(slug__in={
            'moldar-agua', 'nevoa-obscurecente', 'passo-nebuloso',
        }).values_list('nome', flat=True))
        self.assertEqual(len(expected), 3)
        self.assertTrue(expected <= granted)
        self.assertEqual(TbPersonagem.objects.count(), count_before)

    def test_druid_terrain_fixture_distinguishes_maelstrom_from_whirlwind(self):
        from home.character_engine import _spells_from_choice_table

        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'conteudo.json'),
                  encoding='utf-8') as fh:
            fixture = json.load(fh)
        feature = next(row for row in fixture
                       if row['model'] == 'home.tbclassehabilidade' and row['pk'] == 1200)
        whirlwind = next(row for row in fixture
                         if row['model'] == 'home.tbmagia' and row['pk'] == 320)
        description = feature['fields']['descricao']
        self.assertEqual(description.count('[Voragem](tbMagia, voragem) [Maelstrom]'), 2)
        self.assertEqual(whirlwind['fields']['nome_ingles'], 'Whirlwind')
        catalog = dict(TbMagia.objects.values_list('slug', 'nivel'))
        for terrain in ('costa', 'deserto'):
            granted = _spells_from_choice_table(description, [terrain], 9, catalog, {})
            self.assertIn('voragem', granted)
            self.assertNotIn('redemoinho', granted)

    def test_rune_guardian_offers_four_known_runes_and_reopens(self):
        from home import picks, views
        from home.character_engine import derive
        from home.pathbuilder import _apply_choices, _groups_with_keys

        barbarian = TbClasse.objects.get(slug='barbaro')
        feature = TbClassehabilidade.objects.get(pk=969)
        subclass = TbSubclasse.objects.get(pk=feature.id_subclasse_id)
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'conteudo.json'),
                  encoding='utf-8') as fh:
            fixture = json.load(fh)
        source = next(row for row in fixture
                      if row['model'] == 'home.tbclassehabilidade' and row['pk'] == feature.pk)
        feature.tags_json = source['fields']['tags_json']
        feature.save(update_fields=['tags_json'])
        character = TbPersonagem.objects.create(dono=self.user, nome='Runa Guardia')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=barbarian, id_subclasse=subclass,
            nivel=6, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'runa_guardia')
        self.assertEqual(group['n'], 1)
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']},
                         {'chamas', 'tempestade', 'erosao', 'nevasca'})
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['erosao']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'runa_guardia')
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual([e['valor'] for e in reopened['escolhidas']], ['erosao'])
        self.assertIn('acido', derive(character)['resistencias'])
        self.assertNotIn('fogo', derive(character)['resistencias'])
        self.assertEqual(derive(character)['movimento_modos'].get('climb'), 'walk')
        class_row.nivel = 5
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'runa_guardia'
                             for g in picks.resolve_personagem(character)))
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'runa_guardia')
        self.assertEqual([e['valor'] for e in restored['escolhidas']], ['erosao'])
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'runa_guardia')
        self.assertTrue(card['trocavel'])
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'chamas'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual(response.json()['msg'], 'trocada')
        self.assertEqual(character.escolhas.filter(tipo='runa_guardia').count(), 1)
        self.assertIn('fogo', derive(character)['resistencias'])
        self.assertNotIn('acido', derive(character)['resistencias'])
        self.assertNotIn('climb', derive(character).get('movimento_modos', {}))
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'runa-inexistente'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['msg'], 'fora_do_universo')
        self.assertEqual(character.escolhas.get(tipo='runa_guardia').valor, 'chamas')
        storm = TbPersonagem.objects.create(dono=self.user, nome='Runa Tempestade')
        TbPersonagemClasse.objects.create(
            id_personagem=storm, id_classe=barbarian, id_subclasse=subclass,
            nivel=6, principal=True)
        storm_group = next(g for g in _groups_with_keys(storm)
                           if g['kind'] == 'runa_guardia')
        _apply_choices(storm, {'escolhas': {
            storm_group['pathbuilder_key']: ['tempestade']}})
        self.assertIn('raio', derive(storm)['resistencias'])
        self.assertIn('trovejante', derive(storm)['resistencias'])
        self.assertNotIn('acido', derive(storm)['resistencias'])
        for slug, resistance, movement in (
                ('chamas', 'fogo', None), ('nevasca', 'frio', 'swim')):
            other = TbPersonagem.objects.create(dono=self.user, nome='Runa ' + slug)
            TbPersonagemClasse.objects.create(
                id_personagem=other, id_classe=barbarian, id_subclasse=subclass,
                nivel=6, principal=True)
            other_group = next(g for g in _groups_with_keys(other)
                               if g['kind'] == 'runa_guardia')
            _apply_choices(other, {'escolhas': {
                other_group['pathbuilder_key']: [slug]}})
            result = derive(other)
            self.assertIn(resistance, result['resistencias'])
            if movement:
                self.assertEqual(result['movimento_modos'].get(movement), 'walk')
            else:
                self.assertTrue(any('darkvision' in sense
                                    for sense in result['sentidos']))

    def test_sealed_guardian_rune_recovers_rest_choice_from_frozen_page(self):
        from home import picks, views
        from home.character_engine import derive
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        barbarian = TbClasse.objects.get(slug='barbaro')
        feature = TbClassehabilidade.objects.get(pk=969)
        subclass = TbSubclasse.objects.get(pk=feature.id_subclasse_id)
        live_tags = list(feature.tags_json)
        feature.tags_json = [
            'always_active{pick:ability{runas_elementais, classe:barbaro}.runa:1(guard), '
            'resist:elemento{ability{runas_elementais, classe:barbaro}.runa.guard}}',
            'trigger=on{short_rest, long_rest}',
        ]
        feature.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, barbarian)
        finally:
            feature.tags_json = live_tags
            feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Guardia selada')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=barbarian, id_subclasse=subclass,
            nivel=6, principal=True, ruleset=ruleset)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'runa_guardia')
        self.assertEqual(group['n'], 1)
        self.assertEqual(group['swap'], 'short_or_long')
        self.assertEqual({o['slug'] for o in group['universo']},
                         {'chamas', 'tempestade', 'erosao', 'nevasca'})
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['erosao']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'runa_guardia')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']], ['erosao'])
        self.assertIn('acido', derive(character)['resistencias'])
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'runa_guardia')
        self.assertTrue(card['trocavel'])
        response = self.client.post(
            reverse('personagem_trocar_opcao', args=[character.pk]),
            {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
             'val': 'chamas'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual(character.escolhas.get(tipo='runa_guardia').valor, 'chamas')
        self.assertIn('fogo', derive(character)['resistencias'])
        row.nivel = 5
        row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'runa_guardia'
                             for g in picks.resolve_personagem(character)))
        row.nivel = 6
        row.save(update_fields=['nivel'])
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'runa_guardia')
        self.assertEqual([e['valor'] for e in restored['escolhidas']], ['chamas'])
        self.assertEqual(character.escolhas.filter(tipo='runa_guardia').count(), 1)

    def test_hunter_totemic_minor_breath_choice_persists(self):
        from home import picks
        from home.pathbuilder import PathbuilderError, _apply_choices, _groups_with_keys

        hunter = TbClasse.objects.get(slug='cacador')
        subclass = TbSubclasse.objects.get(slug='ordem-da-alianca-selvagem')
        feature = TbClassehabilidade.objects.get(pk=1024)
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'conteudo.json'),
                  encoding='utf-8') as fh:
            fixture = json.load(fh)
        source = next(row for row in fixture
                      if row['model'] == 'home.tbclassehabilidade' and row['pk'] == feature.pk)
        feature.tags_json = source['fields']['tags_json']
        feature.descricao = source['fields']['descricao']
        feature.save(update_fields=['tags_json', 'descricao'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Alianca Selvagem')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter, id_subclasse=subclass,
            nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'caracteristica_totemica')
        expected = {'audicao_olfato', 'camuflagem', 'escalada_aracnidea',
                    'prender_respiracao', 'taticas_de_matilha'} | {
                        'resistencia_elemental|' + damage for damage in
                        ('acido', 'raio', 'fogo', 'frio', 'trovejante')}
        self.assertEqual(group['n'], 1)
        self.assertEqual({o['slug'] for o in group['universo']}, expected)
        with self.assertRaises(PathbuilderError):
            _apply_choices(character, {'escolhas': {
                group['pathbuilder_key']: ['ecolocalizacao']}})
        self.assertFalse(character.escolhas.filter(tipo='caracteristica_totemica').exists())
        _apply_choices(character, {'escolhas': {
            group['pathbuilder_key']: ['prender_respiracao']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'caracteristica_totemica')
        self.assertEqual([e['valor'] for e in reopened['escolhidas']],
                         ['prender_respiracao'])
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        expanded = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'caracteristica_totemica')
        self.assertEqual(expanded['n'], 2)
        major = {'alcance_estendido', 'ecolocalizacao', 'forma_aumentada',
                 'investida', 'robustez_espiritual', 'sopro_elemental'}
        self.assertEqual({o['slug'] for o in expanded['universo']}, expected | major)
        _apply_choices(character, {'escolhas': {
            expanded['pathbuilder_key']: ['prender_respiracao', 'ecolocalizacao']}})
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'caracteristica_totemica')
        self.assertEqual({e['valor'] for e in restored['escolhidas']},
                         {'prender_respiracao', 'ecolocalizacao'})
        sheet = self.client.get(reverse('ficha_detail', args=[character.pk]))
        self.assertEqual(sheet.status_code, 200)
        self.assertContains(sheet, 'Características Maiores')
        self.assertEqual(next(o['nome'] for o in expanded['universo']
                              if o['slug'] == 'ecolocalizacao'), 'Ecolocalização')
        class_row.nivel = 3
        class_row.save(update_fields=['nivel'])
        regressed = next(g for g in _groups_with_keys(character)
                         if g['kind'] == 'caracteristica_totemica')
        self.assertEqual({o['slug'] for o in regressed['universo']}, expected)
        self.assertEqual([e['valor'] for e in regressed['escolhidas']],
                         ['prender_respiracao'])
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        reopened = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'caracteristica_totemica')
        self.assertEqual({e['valor'] for e in reopened['escolhidas']},
                         {'prender_respiracao', 'ecolocalizacao'})

    def test_hunter_totemic_elemental_resistances_keep_distinct_types(self):
        from home import picks, views
        from home.pathbuilder import PathbuilderError, _apply_choices, _choice_groups, _groups_with_keys

        hunter = TbClasse.objects.get(slug='cacador')
        subclass = TbSubclasse.objects.get(slug='ordem-da-alianca-selvagem')
        character = TbPersonagem.objects.create(dono=self.user, nome='Resistencias totemicas')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter, id_subclasse=subclass,
            nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'caracteristica_totemica')
        types = {'acido', 'raio', 'fogo', 'frio', 'trovejante'}
        self.assertEqual({option['slug'] for option in group['universo']
                          if option['slug'].startswith('resistencia_elemental|')},
                         {'resistencia_elemental|' + damage for damage in types})
        self.assertNotIn('resistencia_elemental',
                         {option['slug'] for option in group['universo']})
        labels = {option['slug']: option['nome'] for option in group['universo']}
        self.assertEqual(labels['resistencia_elemental|acido'],
                         'Resistência Elemental — Ácido')
        self.assertEqual(labels['resistencia_elemental|raio'],
                         'Resistência Elemental — Elétrico')
        self.assertEqual(labels['resistencia_elemental|trovejante'],
                         'Resistência Elemental — Trovão')
        first = 'resistencia_elemental|fogo'
        key = group['pathbuilder_key']
        _apply_choices(character, {'escolhas': {key: [first]}})
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        expanded = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'caracteristica_totemica')
        self.assertEqual(expanded['n'], 2)
        with self.assertRaises(PathbuilderError):
            _apply_choices(character, {'escolhas': {key: [first, first]}})
        second = 'resistencia_elemental|frio'
        _apply_choices(character, {'escolhas': {key: [first, second]}})
        self.assertEqual({e['valor'] for e in next(g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'caracteristica_totemica')['escolhidas']},
                         {first, second})
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'caracteristica_totemica')
        self.assertEqual(card['usados'], 2)
        class_row.nivel = 3
        class_row.save(update_fields=['nivel'])
        self.assertEqual(next(g for g in picks.resolve_personagem(character)
                              if g['kind'] == 'caracteristica_totemica')['usados'], 1)
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        reopened = next(g for g in _choice_groups(character, {})
                        if g['kind'] == 'caracteristica_totemica')
        self.assertEqual({e['valor'] for e in reopened['resolvidas']}, {first, second})

    def test_hunter_profile_ruleset_unlocks_frozen_subclass_without_class_row_ruleset(self):
        from home import picks
        from home.character_engine import _subclass_min_level
        from home.content_versions import create_revision, seal_ruleset
        from home.hunter_rework import catalog as hunter_catalog
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests
        from home.versioned_classes import EVALUATOR, VOCABULARY

        hunter = TbClasse.objects.get(slug='cacador')
        subclass = TbSubclasse.objects.get(slug='ordem-da-alianca-selvagem')
        base = CreatorPinnedCatalogTests.seal(self, hunter)
        sealed = seal_ruleset(
            [entry.revision for entry in base.entries.select_related('revision')] + [
                create_revision('hunter-rework', hunter_catalog())],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.assertEqual(_subclass_min_level(hunter, ruleset=sealed), 3)

        hunter.tags_json = [
            'subclass_choices{4}' if tag.startswith('subclass_choices{') else tag
            for tag in (hunter.tags_json or [])
        ]
        hunter.save(update_fields=['tags_json'])
        self.assertEqual(_subclass_min_level(hunter), 4, hunter.tags_json)

        character = TbPersonagem.objects.create(dono=self.user, nome='Cacador legado fixado')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter, id_subclasse=subclass,
            ruleset=None, nivel=3, principal=True)
        TbPersonagemCacador.objects.create(
            personagem_classe=class_row, ruleset=sealed, ability='wis', selected=[])

        groups = picks.resolve_personagem(character)
        self.assertTrue(any(g['kind'] == 'caracteristica_totemica' for g in groups))

    def test_sealed_hunter_totemic_major_options_recover_from_approved_page(self):
        from home.pathbuilder import PathbuilderError, _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests
        from home.versioned_classes import VersionedClassCatalog

        hunter = TbClasse.objects.get(slug='cacador')
        subclass = TbSubclasse.objects.get(slug='ordem-da-alianca-selvagem')
        feature = TbClassehabilidade.objects.get(pk=1024)
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'conteudo.json'),
                  encoding='utf-8') as fh:
            fixture = json.load(fh)
        source = next(row['fields'] for row in fixture
                      if row['model'] == 'home.tbclassehabilidade' and row['pk'] == 1024)
        major_heading = '\n#### Características Maiores'
        feature.descricao = source['descricao'].split(major_heading, 1)[0]
        feature.tags_json = [source['tags_json'][0],
                             source['tags_json'][1].split(', alcance_estendido:', 1)[0] + ' }}']
        feature.save(update_fields=['descricao', 'tags_json'])
        ruleset = CreatorPinnedCatalogTests.seal(self, hunter)
        frozen = next(row for row in VersionedClassCatalog(ruleset, hunter.pk)
                      .collections[TbClassehabilidade] if row.pk == 1024)
        self.assertNotIn('Alcance Estendido', frozen.descricao)
        self.assertFalse(any('alcance_estendido' in tag for tag in frozen.tags_json))
        feature.descricao = ''
        feature.tags_json = []
        feature.save(update_fields=['descricao', 'tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Totem selado')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter, id_subclasse=subclass,
            ruleset=ruleset, nivel=3, principal=True)
        minor = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'caracteristica_totemica')
        self.assertNotIn('ecolocalizacao', {o['slug'] for o in minor['universo']})
        with self.assertRaises(PathbuilderError):
            _apply_choices(character, {'escolhas': {
                minor['pathbuilder_key']: ['ecolocalizacao']}})
        _apply_choices(character, {'escolhas': {
            minor['pathbuilder_key']: ['camuflagem']}})
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        expanded = next(g for g in _groups_with_keys(character)
                        if g['kind'] == 'caracteristica_totemica')
        major = {'alcance_estendido', 'ecolocalizacao', 'forma_aumentada',
                 'investida', 'robustez_espiritual', 'sopro_elemental'}
        self.assertTrue(major <= {o['slug'] for o in expanded['universo']})
        self.assertEqual(next(o['nome'] for o in expanded['universo']
                              if o['slug'] == 'ecolocalizacao'), 'Ecolocalização')
        _apply_choices(character, {'escolhas': {
            expanded['pathbuilder_key']: ['camuflagem', 'ecolocalizacao']}})
        class_row.nivel = 3
        class_row.save(update_fields=['nivel'])
        self.assertEqual([e['valor'] for e in next(g for g in _groups_with_keys(character)
                           if g['kind'] == 'caracteristica_totemica')['escolhidas']],
                         ['camuflagem'])
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        self.assertEqual({e['valor'] for e in next(g for g in _groups_with_keys(character)
                          if g['kind'] == 'caracteristica_totemica')['escolhidas']},
                         {'camuflagem', 'ecolocalizacao'})
        sheet = self.client.get(reverse('ficha_detail', args=[character.pk]))
        self.assertEqual(sheet.status_code, 200, sheet.content[:500])
        self.assertContains(sheet, 'Ecolocalização')
        self.assertContains(sheet, 'data-opcao-toggle="caracteristica_totemica-')

    def test_sealed_hunter_totemic_resistances_use_frozen_page_after_live_edit(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        hunter = TbClasse.objects.get(slug='cacador')
        subclass = TbSubclasse.objects.get(slug='ordem-da-alianca-selvagem')
        feature = TbClassehabilidade.objects.get(pk=1024)
        feature.tags_json = [str(tag).replace(
            'prender_respiracao:{breath_hold:1h}, ', '')
            for tag in feature.tags_json]
        self.assertFalse(any('prender_respiracao' in tag for tag in feature.tags_json))
        feature.save(update_fields=['tags_json'])
        ruleset = CreatorPinnedCatalogTests.seal(self, hunter)
        TbClassehabilidade.objects.filter(pk=1024).update(tags_json=[])
        character = TbPersonagem.objects.create(dono=self.user, nome='Totem antigo selado')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter, id_subclasse=subclass,
            ruleset=ruleset, nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'caracteristica_totemica')
        self.assertIn('resistencia_elemental|fogo',
                      {option['slug'] for option in group['universo']})
        self.assertIn('prender_respiracao',
                      {option['slug'] for option in group['universo']})
        self.assertIn('Resistência Elemental — Elétrico',
                      {option['nome'] for option in group['universo']})
        _apply_choices(character, {'escolhas': {
            group['pathbuilder_key']: ['prender_respiracao']}})
        breathing = next(g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'caracteristica_totemica')
        self.assertEqual(next(o['nome'] for o in breathing['universo']
                              if o['slug'] == 'prender_respiracao'),
                         'Prender a Respiração')
        self.assertEqual(next(o['descricao'] for o in breathing['universo']
                              if o['slug'] == 'prender_respiracao'),
                         'O espírito pode prender a respiração por 1 hora.')
        self.assertEqual([e['valor'] for e in breathing['escolhidas']],
                         ['prender_respiracao'])
        self.assertEqual([e['nome'] for e in breathing['escolhidas']],
                         ['Prender a Respiração'])
        sheet = self.client.get(reverse('ficha_detail', args=[character.pk]))
        self.assertEqual(sheet.status_code, 200, sheet.content[:500])
        self.assertContains(sheet, 'data-opcao-toggle="caracteristica_totemica-')
        self.assertContains(sheet, 'O espírito pode prender a respiração por 1 hora.')
        first = 'prender_respiracao'
        class_row.nivel = 6
        class_row.save(update_fields=['nivel'])
        second = 'resistencia_elemental|fogo'
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: [first, second]}})
        sealed = next(g for g in picks.resolve_personagem(character)
                      if g['kind'] == 'caracteristica_totemica')
        self.assertEqual({e['valor'] for e in sealed['escolhidas']}, {first, second})
        card = next(g for g in _choice_groups(character, {})
                    if g['kind'] == 'caracteristica_totemica')
        self.assertEqual({e['valor'] for e in card['resolvidas']}, {first, second})

    def test_hunter_final_path_prepared_spells_match_page_and_reopen(self):
        from home import picks, views
        from home.pathbuilder import _apply_choices, _groups_with_keys

        hunter = TbClasse.objects.get(slug='cacador')
        feature = TbClassehabilidade.objects.get(pk=1072)
        subclass = TbSubclasse.objects.get(pk=feature.id_subclasse_id)
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'conteudo.json'),
                  encoding='utf-8') as fh:
            fixture = json.load(fh)
        source = next(row for row in fixture
                      if row['model'] == 'home.tbclassehabilidade' and row['pk'] == feature.pk)
        feature.tags_json = source['fields']['tags_json']
        feature.save(update_fields=['tags_json'])
        expected = {'portal-arcano', 'palavra-de-retorno', 'etereidade',
                    'magnifica-mansao', 'teletransporte', 'viagem-planar'}
        character = TbPersonagem.objects.create(dono=self.user, nome='Caminho Final')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter, id_subclasse=subclass,
            nivel=18, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'caminho_final_preparada')
        self.assertEqual(group['n'], 2)
        self.assertEqual({o['slug'] for o in group['universo']}, expected)
        _apply_choices(character, {'escolhas': {
            group['pathbuilder_key']: ['portal-arcano', 'viagem-planar']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'caminho_final_preparada')
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual([e['valor'] for e in reopened['escolhidas']],
                         ['portal-arcano', 'viagem-planar'])
        class_row.nivel = 17
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'caminho_final_preparada'
                             for g in picks.resolve_personagem(character)))
        class_row.nivel = 18
        class_row.save(update_fields=['nivel'])
        restored = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'caminho_final_preparada')
        self.assertEqual([e['valor'] for e in restored['escolhidas']],
                         ['portal-arcano', 'viagem-planar'])
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'caminho_final_preparada')
        self.assertTrue(card['trocavel'])
        first_id = card['escolhidas'][0]['id']
        url = reverse('personagem_trocar_opcao', args=[character.pk])
        response = self.client.post(
            url, {'grupo': card['chave'], 'escolha': first_id,
                  'val': 'teletransporte'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual(response.json()['msg'], 'trocada')
        self.assertEqual([e['valor'] for e in next(
            g for g in picks.resolve_personagem(character)
            if g['kind'] == 'caminho_final_preparada')['escolhidas']],
            ['teletransporte', 'viagem-planar'])
        self.assertEqual(character.escolhas.filter(tipo='caminho_final_preparada').count(), 2)
        response = self.client.post(
            url, {'grupo': card['chave'], 'escolha': first_id,
                  'val': 'viagem-planar'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['msg'], 'duplicada')

    def test_sealed_hunter_final_path_uses_its_own_spell_list(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        hunter = TbClasse.objects.get(slug='cacador')
        feature = TbClassehabilidade.objects.get(pk=1072)
        subclass = TbSubclasse.objects.get(pk=feature.id_subclasse_id)
        current_tags = list(feature.tags_json)
        old_tags = [tag.split(' de [')[0] if tag.startswith('pick:caminho_final_preparada:')
                    else tag for tag in current_tags]
        self.assertNotEqual(old_tags, current_tags)
        feature.tags_json = old_tags
        feature.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, hunter)
        finally:
            feature.tags_json = current_tags
            feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Caminho Final legado')
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=hunter, id_subclasse=subclass,
            ruleset=ruleset, nivel=18, principal=True)
        expected = {'portal-arcano', 'palavra-de-retorno', 'etereidade',
                    'magnifica-mansao', 'teletransporte', 'viagem-planar'}
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'caminho_final_preparada')
        self.assertEqual(group['n'], 2)
        self.assertEqual({option['slug'] for option in group['universo']}, expected)
        _apply_choices(character, {'escolhas': {
            group['pathbuilder_key']: ['portal-arcano', 'viagem-planar']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'caminho_final_preparada')
        self.assertEqual([item['valor'] for item in reopened['escolhidas']],
                         ['portal-arcano', 'viagem-planar'])
        row.nivel = 17
        row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'caminho_final_preparada'
                             for g in picks.resolve_personagem(character)))
        row.nivel = 18
        row.save(update_fields=['nivel'])
        self.assertEqual([item['valor'] for item in next(
            g for g in picks.resolve_personagem(character)
            if g['kind'] == 'caminho_final_preparada')['escolhidas']],
            ['portal-arcano', 'viagem-planar'])

    def test_sealed_artificer_defender_core_uses_published_page_choices(self):
        from home import picks
        from home import views
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        artificer = TbClasse.objects.get(slug='artifice')
        feature = TbClassehabilidade.objects.get(pk=934)
        subclass = TbSubclasse.objects.get(pk=feature.id_subclasse_id)
        live_tags = list(feature.tags_json)
        sealed_tags = [tag.split(' de [')[0] if tag.startswith('pick:nucleo_defensor:')
                       else tag for tag in live_tags]
        self.assertNotEqual(sealed_tags, live_tags)
        feature.tags_json = sealed_tags
        feature.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, artificer)
        finally:
            feature.tags_json = live_tags
            feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Defensor legado')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=artificer, id_subclasse=subclass,
            ruleset=ruleset, nivel=15, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'nucleo_defensor')
        self.assertEqual(group['n'], 2)
        self.assertEqual({item['slug'] for item in group['universo']},
                         {'ofensivo', 'defensivo', 'batedor', 'arcano'})
        _apply_choices(character, {'escolhas': {
            group['pathbuilder_key']: ['ofensivo', 'arcano']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'nucleo_defensor')
        self.assertEqual([item['valor'] for item in reopened['escolhidas']],
                         ['ofensivo', 'arcano'])
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'nucleo_defensor')
        self.assertEqual({item['valor'] for item in card['escolhidas']},
                         {'ofensivo', 'arcano'})
        class_row.nivel = 14
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'nucleo_defensor'
                             for g in picks.resolve_personagem(character)))
        class_row.nivel = 15
        class_row.save(update_fields=['nivel'])
        self.assertEqual([item['valor'] for item in next(
            g for g in picks.resolve_personagem(character)
            if g['kind'] == 'nucleo_defensor')['escolhidas']],
            ['ofensivo', 'arcano'])

    def test_sealed_skald_fighting_style_uses_published_fighter_source(self):
        from home import picks, views
        from home.pathbuilder import _apply_choices, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        bard = TbClasse.objects.get(slug='bardo')
        feature = TbClassehabilidade.objects.get(pk=1977)
        subclass = TbSubclasse.objects.get(pk=feature.id_subclasse_id)
        live_tags = list(feature.tags_json)
        old_tags = [tag.replace(':1(from:classe{guerreiro})', ':1')
                    for tag in live_tags]
        self.assertNotEqual(old_tags, live_tags)
        feature.tags_json = old_tags
        feature.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, bard)
        finally:
            feature.tags_json = live_tags
            feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Skald legado')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=bard, id_subclasse=subclass,
            ruleset=ruleset, nivel=3, principal=True)
        group = next(g for g in _groups_with_keys(character)
                     if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta')
        expected = {'arquearia', 'combate-as-cegas', 'defesa', 'duelo',
                    'combate-com-armas-grandes', 'interceptacao', 'protecao',
                    'combate-com-armas-de-arremesso', 'combate-com-duas-armas',
                    'combate-desarmado'}
        self.assertEqual({option['slug'] for option in group['universo']}, expected)
        _apply_choices(character, {'escolhas': {group['pathbuilder_key']: ['duelo']}})
        reopened = next(g for g in picks.resolve_personagem(character)
                        if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta')
        self.assertEqual([item['valor'] for item in reopened['escolhidas']], ['duelo'])
        card = next(g for g in views._opcoes_ficha(character)
                    if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta')
        self.assertEqual([item['valor'] for item in card['escolhidas']], ['duelo'])
        class_row.nivel = 2
        class_row.save(update_fields=['nivel'])
        self.assertFalse(any(g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta'
                             for g in picks.resolve_personagem(character)))
        class_row.nivel = 3
        class_row.save(update_fields=['nivel'])
        self.assertEqual([item['valor'] for item in next(
            g for g in picks.resolve_personagem(character)
            if g['kind'] == 'opcao' and g['tipo'] == 'estilo_de_luta')['escolhidas']],
            ['duelo'])

    def test_hunter_page_embedded_fighting_styles_reopen_live_and_sealed(self):
        from home import picks, views
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        hunter = TbClasse.objects.get(slug='cacador')
        sealed = CreatorPinnedCatalogTests.seal(self, hunter)
        expected = {'arquearia', 'duelo', 'defesa', 'combate-com-duas-armas'}
        for ruleset in (None, sealed):
            with self.subTest(version='live' if ruleset is None else ruleset.pk):
                character = TbPersonagem.objects.create(
                    dono=self.user, nome='Preparos de Caçada')
                TbPersonagemClasse.objects.create(
                    id_personagem=character, id_classe=hunter,
                    ruleset=ruleset, nivel=1, principal=True)
                group = next(g for g in _groups_with_keys(character)
                             if g['kind'] == 'opcao'
                             and g['tipo'] == 'estilo_de_luta')
                self.assertTrue(expected <= {o['slug'] for o in group['universo']})
                self.assertEqual(group['n'], 1)
                self.assertEqual(group['swap'], 'long_rest')
                card = next(g for g in _choice_groups(character, {'escolhas': {}})
                            if g['key'] == group['pathbuilder_key'])
                self.assertTrue(expected <= {o['valor'] for o in card['opcoes']})
                _apply_choices(character, {
                    'escolhas': {group['pathbuilder_key']: ['duelo']}})
                reopened = next(g for g in picks.resolve_personagem(character)
                                if g['kind'] == 'opcao'
                                and g['tipo'] == 'estilo_de_luta')
                self.assertEqual([o['valor'] for o in reopened['escolhidas']],
                                 ['duelo'])
                ficha = next(g for g in views._opcoes_ficha(character)
                             if g['kind'] == 'opcao'
                             and g['tipo'] == 'estilo_de_luta')
                self.assertEqual([o['valor'] for o in ficha['escolhidas']], ['duelo'])
                sheet = self.client.get(reverse('ficha_detail', args=[character.pk]))
                self.assertEqual(sheet.status_code, 200, sheet.content[:500])
                self.assertContains(sheet, 'Duelo')
                response = self.client.post(
                    reverse('personagem_trocar_opcao', args=[character.pk]),
                    {'grupo': ficha['chave'],
                     'escolha': ficha['escolhidas'][0]['id'],
                     'val': next(option['val'] for option in
                                 ficha['escolhidas'][0]['disponiveis']
                                 if option['nome'] == 'Defesa')},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertEqual(response.status_code, 200, response.content[:400])
                changed = next(g for g in picks.resolve_personagem(character)
                               if g['kind'] == 'opcao'
                               and g['tipo'] == 'estilo_de_luta')
                self.assertEqual([o['valor'] for o in changed['escolhidas']],
                                 ['defesa'])
                self.assertEqual(character.escolhas.filter(
                    tipo='estilo_de_luta').count(), 1)

    def test_sealed_bard_weapon_mastery_alias_persists_and_swaps(self):
        from home import picks, views
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        bard = TbClasse.objects.get(slug='bardo')
        for feature_id in (1974, 1977):
            with self.subTest(feature_id=feature_id):
                feature = TbClassehabilidade.objects.get(pk=feature_id)
                subclass = TbSubclasse.objects.get(pk=feature.id_subclasse_id)
                live_tags = list(feature.tags_json)
                old_tags = [tag.replace('pick:arma:1', 'pick:arma_mastery:1')
                            for tag in live_tags]
                self.assertNotEqual(old_tags, live_tags)
                feature.tags_json = old_tags
                feature.save(update_fields=['tags_json'])
                try:
                    ruleset = CreatorPinnedCatalogTests.seal(self, bard)
                finally:
                    feature.tags_json = live_tags
                    feature.save(update_fields=['tags_json'])
                checksum = ruleset.checksum
                character = TbPersonagem.objects.create(
                    dono=self.user, nome='Maestria legada %d' % feature_id)
                class_row = TbPersonagemClasse.objects.create(
                    id_personagem=character, id_classe=bard, id_subclasse=subclass,
                    ruleset=ruleset, nivel=3, principal=True)
                group = next(g for g in _groups_with_keys(character)
                             if g['kind'] == 'arma')
                self.assertEqual(group['n'], 1)
                self.assertEqual(group['swap'], 'long_rest')
                card = next(g for g in _choice_groups(character, {'escolhas': {}})
                            if g['kind'] == 'arma')
                options = [o['valor'] for o in card['opcoes'] if '|' in o['valor']]
                self.assertGreaterEqual(len(options), 2)
                selected = options[0]
                _apply_choices(character, {
                    'escolhas': {group['pathbuilder_key']: [selected]}})
                self.assertTrue(character.escolhas.filter(
                    tipo='maestria', valor=selected).exists())
                reopened = next(g for g in picks.resolve_personagem(character)
                                if g['kind'] == 'arma')
                self.assertEqual(reopened['pendentes'], 0)
                self.assertEqual(reopened['escolhidas'][0]['valor'], selected)
                card = next(g for g in views._opcoes_ficha(character)
                            if g['kind'] == 'arma')
                self.assertTrue(card['trocavel'])
                self.assertEqual(card['escolhidas'][0]['valor'], selected)
                response = self.client.post(
                    reverse('personagem_trocar_opcao', args=[character.pk]),
                    {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
                     'val': options[1]}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertEqual(response.status_code, 200, response.content[:400])
                self.assertEqual(character.escolhas.get(tipo='maestria').valor, options[1])
                response = self.client.post(
                    reverse('personagem_trocar_opcao', args=[character.pk]),
                    {'grupo': card['chave'], 'escolha': card['escolhidas'][0]['id'],
                     'val': 'arma-inexistente|maestria-inexistente'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertEqual(response.status_code, 400)
                self.assertEqual(character.escolhas.get(tipo='maestria').valor, options[1])
                class_row.nivel = 2
                class_row.save(update_fields=['nivel'])
                self.assertFalse(any(g['kind'] == 'arma'
                                     for g in picks.resolve_personagem(character)))
                class_row.nivel = 3
                class_row.save(update_fields=['nivel'])
                self.assertEqual(next(g for g in picks.resolve_personagem(character)
                                      if g['kind'] == 'arma')['escolhidas'][0]['valor'],
                                 options[1])
                self.assertEqual(ruleset.checksum, checksum)

    def test_hunter_favored_enemy_fixture_progresses_and_reopens(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _groups_with_keys

        classe = TbClasse.objects.get(slug='cacador')
        feature = TbClassehabilidade.objects.get(
            id_classe=classe, id_subclasse__isnull=True,
            nome='Inimigo Favorito', niveladquirido=2)
        self.assertTrue(any('de [aberracoes, bestas, celestiais' in tag
                            for tag in feature.tags_json))
        character = TbPersonagem.objects.create(dono=self.user, nome='Inimigos favoritos')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe, nivel=2, principal=True)
        expected = {'aberracoes', 'bestas', 'celestiais', 'construtos',
                    'corruptores', 'dragoes', 'elementais', 'fadas', 'gigantes',
                    'humanoides', 'monstruosidades', 'mortos-vivos'}
        for level, selected in ((2, ['bestas']),
                                (6, ['bestas', 'dragoes']),
                                (14, ['bestas', 'dragoes', 'mortos-vivos'])):
            class_row.nivel = level
            class_row.save(update_fields=['nivel'])
            group = next(g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'inimigo_favorito')
            self.assertEqual(group['n'], len(selected))
            self.assertEqual({o['slug'] for o in group['universo']}, expected)
            key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                       if g['kind'] == 'inimigo_favorito')
            _apply_choices(character, {'escolhas': {key: selected}})
            reopened = next(g for g in picks.resolve_personagem(character)
                            if g['kind'] == 'inimigo_favorito')
            self.assertEqual(reopened['pendentes'], 0)
            self.assertEqual({e['valor'] for e in reopened['escolhidas']}, set(selected))

    def test_sealed_hunter_favored_enemy_recovers_explicit_page_list(self):
        from home import picks
        from home.pathbuilder import _apply_choices, _choice_groups, _groups_with_keys
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        classe = TbClasse.objects.get(slug='cacador')
        feature = TbClassehabilidade.objects.get(
            id_classe=classe, id_subclasse__isnull=True,
            nome='Inimigo Favorito', niveladquirido=2)
        current_tags = list(feature.tags_json)
        old_tag = current_tags[0].split(' de [')[0]
        self.assertNotEqual(old_tag, current_tags[0])
        feature.tags_json = [old_tag, *current_tags[1:]]
        feature.save(update_fields=['tags_json'])
        try:
            ruleset = CreatorPinnedCatalogTests.seal(self, classe)
        finally:
            feature.tags_json = current_tags
            feature.save(update_fields=['tags_json'])

        character = TbPersonagem.objects.create(dono=self.user, nome='Caçador legado')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=classe,
            ruleset=ruleset, nivel=2, principal=True)
        expected = {'aberracoes', 'bestas', 'celestiais', 'constructos',
                    'corruptores', 'dragoes', 'elementais', 'fadas', 'gigantes',
                    'humanoides', 'monstruosidades', 'mortos-vivos'}
        for level, selected in ((2, ['bestas']),
                                (6, ['bestas', 'constructos']),
                                (14, ['bestas', 'constructos', 'mortos-vivos'])):
            class_row.nivel = level
            class_row.save(update_fields=['nivel'])
            group = next(g for g in picks.resolve_personagem(character)
                         if g['kind'] == 'inimigo_favorito')
            self.assertEqual(group['n'], len(selected))
            self.assertEqual({o['slug'] for o in group['universo']}, expected)
            card = next(g for g in _choice_groups(character, {'escolhas': {}})
                        if g['kind'] == 'inimigo_favorito')
            self.assertEqual({o['valor'] for o in card['opcoes']}, expected)
            key = next(g['pathbuilder_key'] for g in _groups_with_keys(character)
                       if g['kind'] == 'inimigo_favorito')
            _apply_choices(character, {'escolhas': {key: selected}})
            reopened = next(g for g in picks.resolve_personagem(character)
                            if g['kind'] == 'inimigo_favorito')
            self.assertEqual(reopened['pendentes'], 0)
            self.assertEqual({e['valor'] for e in reopened['escolhidas']}, set(selected))

    def test_legacy_page_list_does_not_turn_unrelated_or_runtime_text_into_choice(self):
        from types import SimpleNamespace
        from home import picks

        classe = TbClasse.objects.get(slug='cacador')
        old_tag = 'pick:inimigo_favorito:{classlvl=2:1, classlvl=6:1}'
        source = SimpleNamespace(
            pk=99999, nome='Inimigo Favorito', niveladquirido=2,
            tags_json=[old_tag],
            descricao='- **Escolha de Aliado:** Escolha entre: Bestas, Dragões ou Fadas.',
        )
        self.assertEqual(picks.resolve_groups([source], classe=classe, nivel=2), [])
        source.descricao = '- **Escolha de Inimigo:** Escolha entre: Bestas ou Dragões.'
        self.assertEqual(picks.resolve_groups([source], classe=classe, nivel=2), [])
        source.descricao = '- **Escolha de Inimigo:** Escolha entre: Bestas, Dragões ou Fadas.'
        source.tags_json = ['instant{' + old_tag + '}']
        self.assertEqual(picks.resolve_groups([source], classe=classe, nivel=2), [])

        source.tags_json = [
            'spell_selection:fonte:outro_segredo{list:[portal-arcano, teletransporte]}',
            'pick:caminho_final_preparada:2',
        ]
        self.assertEqual(picks.resolve_groups([source], classe=classe, nivel=2), [])
        source.descricao = ('Pode escolher **dois núcleos** dentre: '
                            '**Ofensivo**, **Defensivo** ou **Arcano**.')
        source.tags_json = ['pick:nucleo_defensor:1']
        self.assertEqual(picks.resolve_groups([source], classe=classe, nivel=2), [])
        source.tags_json = ['pick:nucleo_defensor:2', 'pick:outro:1']
        self.assertEqual(picks.resolve_groups([source], classe=classe, nivel=2), [])
        source.descricao = ('Você adota um **Estilo de Luta** à sua escolha '
                            'entre as opções disponíveis para o Guerreiro.')
        token = next(picks.iter_pick_tokens('pick:opcao:manobra:1'))
        self.assertIsNone(picks._page_option_source(source, token))
        source.descricao = ('Você adota um **Estilo de Luta** à sua escolha '
                            'entre as opções disponíveis para o Ca�ador.')
        token = next(picks.iter_pick_tokens('pick:opcao:estilo_de_luta:1'))
        self.assertIsNone(picks._page_option_source(source, token))

    def test_published_class_preview_uses_frozen_feature_after_live_edit(self):
        from home.class_revision_editor import create_class_revision
        from home.models import TbClassPublication
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        fighter = TbClasse.objects.get(slug='guerreiro')
        feature = TbClassehabilidade.objects.filter(
            id_classe=fighter, id_subclasse__isnull=True,
            niveladquirido__lte=1, table_only=False).first()
        self.assertIsNotNone(feature)
        base = CreatorPinnedCatalogTests.seal(self, fighter)
        published = create_class_revision(base.checksum, fighter.pk, [
            {'model': 'home.tbclassehabilidade', 'action': 'update',
             'pk': feature.pk, 'fields': {'descricao': '## Revisao publicada da habilidade'}}
        ], presentation_source='catalog')
        TbClassPublication.objects.create(id_classe=fighter, ruleset=published)
        payload = self._payload('guerreiro')
        before = TbPersonagem.objects.count()
        TbClassehabilidade.objects.filter(pk=feature.pk).update(
            nome='Alteracao ainda nao publicada')
        subclass = TbSubclasse.objects.filter(id_classe=fighter).first()
        original_subclass_name = subclass.nome
        TbSubclasse.objects.filter(pk=subclass.pk).update(nome='Subclasse ainda nao publicada')
        TbClasse.objects.filter(pk=fighter.pk).update(tags_json=[])

        catalog = self.client.get(reverse('pathbuilder_laboratorio'))
        self.assertEqual(catalog.status_code, 200, catalog.content[:500])
        fighter_options = next(row for row in catalog.context['catalogos']['classes']
                               if row['slug'] == 'guerreiro')
        self.assertEqual(fighter_options['ruleset_checksum'], published.checksum)
        self.assertIn(original_subclass_name,
                      [row['nome'] for row in fighter_options['subclasses']])
        self.assertNotIn('Subclasse ainda nao publicada',
                         [row['nome'] for row in fighter_options['subclasses']])

        start = self.client.post(reverse('pathbuilder_iniciar'),
            data=json.dumps(payload), content_type='application/json')
        self.assertEqual(start.status_code, 200, start.content)
        preview = self._post_preview(payload, self._build('guerreiro'))
        self.assertEqual(preview.status_code, 200, preview.content)
        names = [row['nome'] for row in preview.json()['build']['features']]
        self.assertIn(feature.nome, names)
        self.assertNotIn('Alteracao ainda nao publicada', names)
        level_four = self._post_preview(payload, self._build('guerreiro', classes=[{
            'slug': 'guerreiro', 'nivel': 4, 'subclasse': '',
        }]))
        self.assertEqual(level_four.status_code, 200, level_four.content[:500])
        self.assertEqual(level_four.json()['build']['orcamento']['asi_slots'], 1)
        self.assertIn('Escolha a subclasse',
                      ' '.join(level_four.json()['build']['validacao']['problemas']))
        new_subclass = TbSubclasse.objects.create(
            id_classe=fighter, slug='subclasse-ainda-nao-publicada',
            nome='Subclasse ainda nao publicada')
        unsupported = self._post_preview(payload, self._build('guerreiro', classes=[{
            'slug': 'guerreiro', 'nivel': 3, 'subclasse': new_subclass.slug,
        }]))
        self.assertEqual(unsupported.status_code, 400, unsupported.content)
        self.assertIn('fora da revisao publicada', ' '.join(unsupported.json()['erros']))
        incompatible = self._post_preview(payload, self._build('guerreiro', classes=[
            {'slug': 'guerreiro', 'nivel': 1, 'subclasse': ''},
            {'slug': 'paladino', 'nivel': 1, 'subclasse': ''},
        ]))
        self.assertEqual(incompatible.status_code, 400, incompatible.content)
        self.assertIn('indisponivel nesta revisao',
                      ' '.join(incompatible.json()['erros']))
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_start_pages_require_login_and_render_catalog(self):
        self.client.logout()
        response = self.client.get(reverse("pathbuilder"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(reverse("pathbuilder_laboratorio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pathbuilder")
        self.assertContains(response, "pb-catalogs")

    def test_personagens_existentes_nao_entram_na_simulacao(self):
        existing = TbPersonagem.objects.create(dono=self.user, nome='Ficha existente privada')
        other = self._novo_usuario('pathbuilder-other')
        foreign = TbPersonagem.objects.create(dono=other, nome='Ficha de outra pessoa')
        before = list(TbPersonagem.objects.order_by('pk').values_list('pk', 'nome'))

        page = self.client.get(reverse('pathbuilder_laboratorio'))
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(existing.nome, page.content.decode('utf-8'))
        self.assertNotIn(foreign.nome, page.content.decode('utf-8'))

        response = self._post_preview(self._payload('guerreiro'), self._build('guerreiro'))
        self.assertEqual(response.status_code, 200, response.content[:300])
        sheet = response.json()['build']['ficha_html']
        self.assertNotIn(existing.nome, sheet)
        self.assertNotIn(foreign.nome, sheet)
        self.assertEqual(list(TbPersonagem.objects.order_by('pk').values_list('pk', 'nome')), before)

    def test_q10_magia_incompativel_mantem_previa_e_impede_validacao(self):
        base = self._payload('mago')
        spell = TbMagia.objects.filter(nivel=9).first()
        before = TbPersonagem.objects.count()
        build = self._build('mago', modo='regras',
                            magias=[{'slug': spell.slug, 'preparada': True}])
        response = self._post_preview(base, build)
        self.assertEqual(response.status_code, 200)
        result = response.json()['build']
        self.assertFalse(result['validacao']['valida'])
        self.assertIn(spell.nome, ' '.join(result['validacao']['problemas']))
        self.assertIn(spell.nome, ' '.join(result['validacao']['magias']))
        self.assertTrue(any(row['nome'] == spell.nome for row in result['magias']))
        self.assertEqual(build['magias'][0]['slug'], spell.slug)
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_q10_magia_conhecida_nao_duplica_nem_bloqueia_revisao(self):
        base = self._payload('mago')
        build = self._build('mago', modo='regras',
                            magias=[{'slug': base['truques'][0], 'preparada': True}])
        result = self._post_preview(base, build).json()['build']
        for group in result['escolhas_grupos']:
            if group['pendentes']:
                build['escolhas'][group['key']] = [
                    row['valor'] for row in group['opcoes']
                    if not row.get('ja_proficiente')
                ][:group['pendentes']]
        result = self._post_preview(base, build).json()['build']
        self.assertTrue(result['validacao']['valida'], result['validacao']['problemas'])
        selected = TbMagia.objects.get(slug=base['truques'][0])
        self.assertEqual(sum(row['nome'] == selected.nome for row in result['magias']), 1)

    def test_laboratorio_usa_stepper_e_nao_tem_mais_os_selects_de_adicionar(self):
        """O fluxo velho era `busca -> <select> -> botao Adicionar` em cada secao.

        O redesenho usa o padrao do criador: stepper de etapas + cartao clicavel. Este
        teste amarra as duas pontas — o stepper existe e os selects sumiram."""
        response = self.client.get(reverse("pathbuilder_laboratorio"))
        html = response.content.decode("utf-8")
        for marker in ('id="pb-stepper"', 'data-step-tab="0"', 'data-step="0"',
                       'data-picker="talento"', 'data-picker-list', 'id="pb-folha"'):
            self.assertIn(marker, html, marker)
        for gone in ('id="pb-talent-select"', 'id="pb-item-select"', 'id="pb-spell-select"',
                     'id="pb-add-talent"', 'id="pb-add-item"', 'id="pb-add-spell"',
                     'data-detail-tab'):
            self.assertNotIn(gone, html, gone)
        # a previa e a ficha: o CSS da ficha vem inteiro, sem copia no pathbuilder.css
        self.assertIn("css/pages/ficha.css", html)

    def test_iniciar_valida_sem_criar_personagem(self):
        payload = self._payload("guerreiro")
        before = TbPersonagem.objects.count()
        response = self.client.post(
            reverse("pathbuilder_iniciar"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_fluxo_iniciar_laboratorio_preview(self):
        """O caminho que o jogador percorre: valida a base, abre o laboratorio no redirect
        que o servidor manda, e o primeiro preview ja devolve ficha."""
        payload = self._payload("guerreiro")
        iniciar = self.client.post(
            reverse("pathbuilder_iniciar"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(iniciar.status_code, 200, iniciar.content)
        destino = iniciar.json()["redirect"]
        self.assertEqual(destino, reverse("pathbuilder_laboratorio"))
        self.assertEqual(self.client.get(destino).status_code, 200)

        preview = self._post_preview(payload, self._build("guerreiro"))
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertIn("data-pb-folha", preview.json()["build"]["ficha_html"])

    def test_preview_echoes_request_id_in_success_and_validation_error(self):
        base = self._payload('guerreiro')
        request_id = 'build-A:42'
        for build, expected_status in ((self._build('guerreiro'), 200),
                                       ({'classes': []}, 400)):
            with self.subTest(expected_status=expected_status):
                response = self.client.post(
                    reverse('pathbuilder_preview'),
                    data=json.dumps({'base': base, 'build': build,
                                     'request_id': request_id}),
                    content_type='application/json')
                self.assertEqual(response.status_code, expected_status, response.content)
                self.assertEqual(response.json()['request_id'], request_id)
        invalid = self.client.post(
            reverse('pathbuilder_preview'),
            data=json.dumps({'base': base, 'build': self._build('guerreiro'),
                             'request_id': ['not-a-scalar']}),
            content_type='application/json')
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.json()['ok'])

    def test_laboratorio_rejeita_payload_malformado_sem_salvar_e_aceita_correcao(self):
        base = self._payload('guerreiro')
        valid_build = self._build('guerreiro')
        before = TbPersonagem.objects.count()
        requests = [
            (reverse('pathbuilder_iniciar'), []),
            (reverse('pathbuilder_preview'), []),
            (reverse('pathbuilder_preview'), {'base': [], 'build': valid_build}),
            (reverse('pathbuilder_preview'), {'base': base, 'build': []}),
            (reverse('pathbuilder_preview'), {'base': base, 'build': {
                **valid_build, 'classes': [valid_build['classes'][0], 7],
            }}),
        ]
        for url, payload in requests:
            with self.subTest(url=url, payload=payload):
                response = self.client.post(url, data=json.dumps(payload),
                                            content_type='application/json')
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(response.json()['ok'])
                self.assertTrue(response.json()['erros'])
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, valid_build)
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertIn('data-pb-folha', corrected.json()['build']['ficha_html'])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_rejeita_numeros_truncaveis_e_aceita_correcao(self):
        base = self._payload('guerreiro')
        valid_build = self._build('guerreiro')
        item = TbItemMundano.objects.first()
        self.assertIsNotNone(item)
        before = TbPersonagem.objects.count()
        invalid_builds = [
            (self._build('guerreiro', classes=[
                {'slug': 'guerreiro', 'nivel': 1.9, 'subclasse': ''},
            ]), 'Nivel de classe'),
            (self._build('guerreiro', classes=[
                {'slug': 'guerreiro', 'nivel': True, 'subclasse': ''},
            ]), 'Nivel de classe'),
            (self._build('guerreiro', atributos_bonus={'FOR': 2.5}), 'Bonus de FOR'),
            (self._build('guerreiro', itens=[
                {'tipo': 'mundano', 'slug': item.slug, 'qtd': 1.5},
            ]), 'Quantidade do item'),
        ]
        for build, label in invalid_builds:
            with self.subTest(label=label, build=build):
                response = self._post_preview(base, build)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(label, ' '.join(response.json()['erros']))
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, valid_build)
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertIn('data-pb-folha', corrected.json()['build']['ficha_html'])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_rejeita_bonus_de_atributo_desconhecido_sem_perder_correcao(self):
        base = self._payload('guerreiro')
        before = TbPersonagem.objects.count()
        for bonus in ({'AGI': 2}, {'FOR': 1, 'AGI': 2}, None, []):
            with self.subTest(bonus=bonus):
                response = self._post_preview(base, self._build(
                    'guerreiro', atributos_bonus=bonus))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn('Bonus de atributos invalidos',
                              ' '.join(response.json()['erros']))
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, self._build(
            'guerreiro', atributos_bonus={'FOR': 1}))
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_rejeita_itens_malformados_sem_ativar_equipamento(self):
        base = self._payload('guerreiro')
        item = TbItemMundano.objects.first()
        self.assertIsNotNone(item)
        before = TbPersonagem.objects.count()
        row = {'tipo': 'mundano', 'slug': item.slug, 'qtd': 1}
        invalid = [None, [None], [{**row, 'tipo': []}],
                   [{**row, 'equipado': 'false'}],
                   [{**row, 'sintonizado': 'false'}],
                   [{**row, 'sintonizado': True}],
                   [{**row, 'slug': 123}]]
        for items in invalid:
            with self.subTest(items=items):
                response = self._post_preview(base, self._build('guerreiro', itens=items))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(response.json()['ok'])
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, self._build('guerreiro', itens=[
            {**row, 'equipado': False, 'sintonizado': False}]))
        self.assertEqual(corrected.status_code, 200, corrected.content)
        inventory = corrected.json()['build']['inventario']
        self.assertTrue(any(entry['nome'] == item.nome for entry in inventory))
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_devolve_o_markup_da_ficha_real(self):
        """A visualizacao do resultado E A FICHA: o preview devolve o HTML dos partials da
        aba Ficha (banner, atributos, selos de CA/PV, ataques, caracteristicas), nao um
        resumo em tabela generica."""
        payload = self._payload("guerreiro")
        response = self._post_preview(payload, self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 5, "subclasse": ""}],
        }))
        self.assertEqual(response.status_code, 200, response.content)
        html = response.json()["build"]["ficha_html"]

        # marcadores REAIS da folha (ficha.css / ficha_detail), nao inventados aqui
        for marker in ('data-pb-folha', 'class="ficha-header ficha-banner"', 'ficha-name',
                       'ficha-columns', 'attr-stack', 'attr-box', 'attr-score',
                       'data-ficha-ca', 'data-ficha-pv', 'seal seal-ca', 'hp-track',
                       'Testes de Resistência', 'Perícias', 'Ataques',
                       'Características &amp; Habilidades', 'feat-card', 'feat-head',
                       'Defesas &amp; Sentidos', 'ficha-feat-desc'):
            self.assertIn(marker, html, marker)

        # ... e a MESMA folha e a que a ficha salva usa: um partial so, zero drift
        self.assertIn("home/partials/_ficha_folha.html",
                      [t.name for t in response.templates])
        self.assertIn("home/partials/_ficha_banner.html",
                      [t.name for t in response.templates])

    def test_preview_da_ficha_e_somente_leitura(self):
        """Nada de acao de ficha salva dentro da previa: sem POST de recurso/descanso, sem
        atalho de aba, sem botoes do banner."""
        payload = self._payload("guerreiro")
        response = self._post_preview(payload, self._build("guerreiro"))
        html = response.json()["build"]["ficha_html"]
        for gone in ('personagem_usar_recurso', 'personagem_descansar', 'csrfmiddlewaretoken',
                     'data-tab-jump', 'banner-actions', 'data-notas-form',
                     'data-pers-form', 'Painel da staff'):
            self.assertNotIn(gone, html, gone)
        # e o selo de simulacao deixa claro que nada foi salvo
        self.assertIn("Simulação", html)
        self.assertIn("Nenhum personagem foi salvo", html)

    def test_ficha_salva_usa_os_mesmos_partials_da_previa(self):
        """Guarda de drift pelo outro lado: a aba Ficha renderiza os partials extraidos."""
        criar = self.client.post(reverse("criar_personagem"),
                                 data=json.dumps(self._payload("guerreiro")),
                                 content_type="application/json")
        self.assertEqual(criar.status_code, 200, criar.content)
        personagem = TbPersonagem.objects.filter(dono=self.user).order_by("-pk").first()
        self.assertIsNotNone(personagem)
        response = self.client.get(reverse("ficha_detail", args=[personagem.id_personagem]))
        self.assertEqual(response.status_code, 200)
        nomes = [t.name for t in response.templates]
        for partial in ("home/partials/_ficha_banner.html",
                        "home/partials/_ficha_folha.html",
                        "home/partials/_ficha_folha_defesas.html"):
            self.assertIn(partial, nomes, partial)
        # na ficha salva o que a previa esconde volta a aparecer
        html = response.content.decode("utf-8")
        self.assertIn("banner-actions", html)
        self.assertIn("data-tab-jump", html)

    def test_preview_expoe_orcamento_de_asi_para_a_ui_gastar(self):
        """O editor GASTA o orcamento em vez de reclamar depois: o servidor diz quantos
        slots de ASI existem, quantos foram para talento e quantos pontos sobram."""
        payload = self._payload("guerreiro")
        talento = TbTalento.objects.exclude(tipo__iexact="origem").first()
        build = self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
        })
        response = self._post_preview(payload, build)
        self.assertEqual(response.status_code, 200, response.content)
        orc = response.json()["build"]["orcamento"]
        self.assertGreaterEqual(orc["asi_slots"], 1)
        self.assertEqual(orc["asi_em_talento"], 0)
        self.assertEqual(orc["pontos_disponiveis"], orc["asi_slots"] * 2)
        self.assertEqual(orc["pontos_usados"], 0)
        self.assertEqual(orc["pontos_restantes"], orc["pontos_disponiveis"])

        # gastar 1 slot em talento tira 2 pontos do saldo
        build["talentos"] = [talento.slug]
        orc2 = self._post_preview(payload, build).json()["build"]["orcamento"]
        self.assertEqual(orc2["asi_em_talento"], 1)
        self.assertEqual(orc2["pontos_disponiveis"], orc["pontos_disponiveis"] - 2)

        # distribuir o que resta zera o saldo e a build fica valida pelas regras
        build["talentos"] = []
        build["modo"] = "regras"
        build["atributos_bonus"] = {"FOR": orc["pontos_disponiveis"]}
        result = self._post_preview(payload, build).json()["build"]
        self.assertEqual(result["orcamento"]["pontos_restantes"], 0)
        self.assertNotIn("distribuiu", " ".join(result["validacao"]["problemas"]))

    def test_guerreiro_asi_milestones_match_class_catalog_without_persistence(self):
        catalog = self.client.get(reverse('pathbuilder_laboratorio'))
        self.assertEqual(catalog.status_code, 200)
        fighter = next(row for row in catalog.context['catalogos']['classes']
                       if row['slug'] == 'guerreiro')
        self.assertEqual(fighter['asi_nome'], 'Aprimoramento de Atributo ou Talento')
        baseline = TbPersonagem.objects.count()
        base = self._payload('guerreiro')
        for level, expected_slots in ((1, 0), (4, 1), (6, 2), (8, 3),
                                      (12, 4), (14, 5), (16, 6), (19, 7)):
            with self.subTest(level=level):
                build = self._build('guerreiro', classes=[
                    {'slug': 'guerreiro', 'nivel': level, 'subclasse': ''},
                ])
                response = self._post_preview(base, build)
                self.assertEqual(response.status_code, 200)
                budget = response.json()['build']['orcamento']
                self.assertEqual(budget['asi_slots'], expected_slots)
                self.assertEqual(budget['pontos_disponiveis'], expected_slots * 2)
        self.assertEqual(TbPersonagem.objects.count(), baseline)

    def test_catalogo_asi_cobre_classes_e_subclasses_sem_criar_marcos(self):
        from home.pathbuilder import catalogos
        from home.views import _eh_feature_asi, _tag_levels

        rows = {row['slug']: row for row in catalogos()['classes']}
        self.assertEqual(set(rows), set(TbClasse.objects.values_list('slug', flat=True)))
        with_asi = 0
        for classe in TbClasse.objects.all():
            with self.subTest(classe=classe.slug):
                row = rows[classe.slug]
                levels = sorted(_tag_levels(classe.tags_json, 'asi-choices'))
                self.assertEqual(row['asi_niveis'], levels)
                if not levels:
                    self.assertFalse(row['asi_nome'])
                    continue
                with_asi += 1
                feature = TbClassehabilidade.objects.filter(
                    id_classe=classe, id_subclasse__isnull=True,
                    niveladquirido=levels[0], table_only=False,
                ).filter(nome__icontains='Atributo').first()
                self.assertIsNotNone(feature)
                self.assertTrue(_eh_feature_asi(feature.nome))
                self.assertEqual(row['asi_nome'], feature.nome)
                self.assertEqual(
                    {sub['slug'] for sub in row['subclasses']},
                    set(TbSubclasse.objects.filter(id_classe=classe).values_list('slug', flat=True)),
                )
        self.assertGreater(with_asi, 1)

    def test_matriz_real_de_classes_subclasses_e_progressao_sem_persistencia(self):
        """Exercita cada subclasse no desbloqueio e os extremos de cada classe."""
        from home.pathbuilder import catalogos

        rows = catalogos()['classes']
        self.assertEqual(len(rows), 13)
        self.assertEqual(sum(len(row['subclasses']) for row in rows), 111)
        before = TbPersonagem.objects.count()
        for row in rows:
            if row['slug'] == 'cacador' and not row['ruleset_checksum']:
                continue  # Depende da publicação do Caçador, fora desta frente.
            base = self._payload(row['slug'])
            for level in (1, 20):
                with self.subTest(classe=row['slug'], nivel=level):
                    response = self._post_preview(base, self._build(row['slug'], classes=[{
                        'slug': row['slug'], 'nivel': level, 'subclasse': '',
                    }]))
                    self.assertEqual(response.status_code, 200, response.content[:300])
                    self.assertEqual(response.json()['build']['nivel'], level)
            unlock = row['subclasse_nivel']
            for subclass in row['subclasses']:
                with self.subTest(classe=row['slug'], subclasse=subclass['slug']):
                    self.assertIsNotNone(unlock)
                    response = self._post_preview(base, self._build(row['slug'], classes=[{
                        'slug': row['slug'], 'nivel': unlock, 'subclasse': subclass['slug'],
                    }]))
                    self.assertEqual(response.status_code, 200, response.content[:300])
                    result = response.json()['build']
                    self.assertEqual(result['nivel'], unlock)
                    self.assertEqual(result['classes'][0]['subclasse'], subclass['nome'])
                    self.assertIn(subclass['nome'], result['ficha_html'])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_primeiro_asi_de_cada_classe_com_subclasse_nao_duplica_orcamento(self):
        from home.pathbuilder import catalogos

        baseline = TbPersonagem.objects.count()
        for row in catalogos()['classes']:
            if 4 not in row['asi_niveis']:
                continue
            if row['slug'] == 'cacador' and not row['ruleset_checksum']:
                continue  # O Caçador exige publicação; coberto no teste do catálogo publicado.
            with self.subTest(classe=row['slug']):
                subclass = (row['subclasses'][0]['slug']
                            if row['subclasses'] and row['subclasse_nivel'] <= 4 else '')
                build = self._build(row['slug'], classes=[{
                    'slug': row['slug'], 'nivel': 4, 'subclasse': subclass,
                }])
                response = self._post_preview(self._payload(row['slug']), build)
                self.assertEqual(response.status_code, 200, response.content[:500])
                budget = response.json()['build']['orcamento']
                self.assertEqual(budget['asi_slots'], 1)
                self.assertEqual(budget['pontos_disponiveis'], 2)
        self.assertEqual(TbPersonagem.objects.count(), baseline)

    def test_ultimo_asi_de_cada_classe_com_subclasse_mantem_orcamento(self):
        from home.pathbuilder import catalogos

        classes = {row['slug']: row for row in catalogos()['classes'] if row['asi_niveis']}
        self.assertEqual(len(classes), 13)
        self.assertEqual(classes['guerreiro']['asi_niveis'], [4, 6, 8, 12, 14, 16, 19])
        self.assertEqual(classes['ladino']['asi_niveis'], [4, 8, 10, 12, 16, 19])
        baseline = TbPersonagem.objects.count()
        for slug, row in classes.items():
            if slug == 'cacador' and not row['ruleset_checksum']:
                continue  # O Caçador exige publicação; coberto no teste do catálogo publicado.
            with self.subTest(classe=slug):
                self.assertEqual(row['asi_niveis'][-1], 19)
                expected_slots = 7 if slug == 'guerreiro' else 6 if slug == 'ladino' else 5
                self.assertEqual(len(row['asi_niveis']), expected_slots)
                subclass = (row['subclasses'][0]['slug']
                            if row['subclasses'] and row['subclasse_nivel'] <= 19 else '')
                build = self._build(slug, classes=[{
                    'slug': slug, 'nivel': 19, 'subclasse': subclass,
                }])
                response = self._post_preview(self._payload(slug), build)
                self.assertEqual(response.status_code, 200, response.content[:500])
                budget = response.json()['build']['orcamento']
                self.assertEqual(budget['asi_slots'], expected_slots)
                self.assertEqual(budget['pontos_disponiveis'], expected_slots * 2)
                self.assertEqual(budget['pontos_restantes'], expected_slots * 2)
        self.assertEqual(TbPersonagem.objects.count(), baseline)

    def test_subir_nivel_mostra_nome_asi_da_habilidade_da_classe(self):
        from home.test_creator_pinned_catalog import CreatorPinnedCatalogTests

        criar = self._post_criar(self.user, self._payload('guerreiro'))
        self.assertEqual(criar.status_code, 200, criar.content)
        personagem = TbPersonagem.objects.get(pk=criar.json()['id'])
        TbPersonagemClasse.objects.filter(id_personagem=personagem).update(nivel=4)
        personagem.nivel = 4
        personagem.save(update_fields=['nivel'])

        habilidade = TbClassehabilidade.objects.get(
            id_classe__slug='guerreiro', id_subclasse__isnull=True,
            niveladquirido=4, table_only=False, nome__icontains='Atributo',
        )
        nome_original = habilidade.nome
        snapshot = CreatorPinnedCatalogTests.seal(self, habilidade.id_classe)
        habilidade.nome = 'Aumento de Atributo ou Talento'
        habilidade.save(update_fields=['nome'])
        response = self.client.get(reverse('personagem_subir_nivel', args=[personagem.pk]))
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.assertGreater(response.context['pend']['asi_pendentes'], 0)
        self.assertEqual(response.context['asi_nome'], habilidade.nome)
        self.assertContains(response, '<h2 class="sn-step-title">Aumento de Atributo ou Talento</h2>', html=False)

        pc = personagem.classes.get(id_classe=habilidade.id_classe)
        pc.ruleset = snapshot
        pc.save(update_fields=['ruleset'])
        pinned = self.client.get(reverse('personagem_subir_nivel', args=[personagem.pk]))
        self.assertEqual(pinned.status_code, 200, pinned.content[:500])
        self.assertEqual(pinned.context['asi_nome'], nome_original)

    def test_detalhe_devolve_descricao_sob_demanda(self):
        """Cartao expansivel: a descricao nao vem no catalogo (seria 1 MB), vem aqui."""
        talento = TbTalento.objects.exclude(descricao="").first()
        magia = TbMagia.objects.exclude(descricao="").first()
        response = self.client.get(reverse("pathbuilder_detalhe"),
                                   {"tipo": "talento", "slug": talento.slug})
        self.assertEqual(response.status_code, 200, response.content)
        detalhe = response.json()["detalhe"]
        self.assertEqual(detalhe["nome"], talento.nome)
        self.assertTrue(detalhe["descricao"])

        response = self.client.get(reverse("pathbuilder_detalhe"),
                                   {"tipo": "magia", "slug": magia.slug})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["detalhe"]["linhas"])

        self.assertEqual(self.client.get(
            reverse("pathbuilder_detalhe"),
            {"tipo": "talento", "slug": "nao-existe-mesmo"}).status_code, 404)
        self.assertEqual(self.client.get(
            reverse("pathbuilder_detalhe"),
            {"tipo": "tabela_secreta", "slug": "x"}).status_code, 404)

    def test_catalogo_do_laboratorio_e_enxuto_e_tem_meta_para_o_cartao(self):
        from home.pathbuilder import catalogos

        cat = catalogos()
        self.assertTrue(cat["talentos"] and cat["magias"] and cat["itens_magicos"])
        for chave in ("talentos", "magias", "itens_mundanos", "itens_magicos"):
            linha = cat[chave][0]
            self.assertIn("grupo", linha, chave)   # cabecalho de grupo do picker
            self.assertIn("meta", linha, chave)    # subtitulo do cartao
            self.assertNotIn("descricao", linha, chave)  # texto so sob demanda
        self.assertTrue(cat["classes"][0]["subclasses"] is not None)
        self.assertTrue(all(row["grupo"].lower() == "geral" for row in cat["talentos"]))
        self.assertTrue(all(row["atributos"] for row in cat["talentos"]))

    def test_catalogo_de_magias_inclui_nome_ingles_sem_alterar_o_nome_exibido(self):
        from home.pathbuilder import catalogos

        magia = TbMagia.objects.first()
        magia.nome_ingles = "Example Spell"
        magia.save(update_fields=["nome_ingles"])
        row = next(row for row in catalogos()["magias"] if row["slug"] == magia.slug)
        self.assertEqual(row["nome"], magia.nome)
        self.assertEqual(row["nome_ingles"], "Example Spell")

    def test_fighter_martial_and_medium_armor_talent_prerequisites(self):
        from home.character_engine import derive
        from home.views import _talentos_asi_catalogo

        fighter = TbClasse.objects.get(slug='guerreiro')
        character = TbPersonagem.objects.create(dono=self.user, nome='Pré-requisitos marciais')
        class_row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=fighter, nivel=3, principal=True)
        talent_ids = dict(TbTalento.objects.filter(slug__in=[
            'adepto-marcial', 'maestria-em-armaduras-medias', 'mestre-de-escudo',
            'duelista-defensivo',
        ]).values_list('slug', 'pk'))
        eligibility = {row['id']: row['elegivel'] for row in
                       _talentos_asi_catalogo(character, derive(character))}
        for slug in talent_ids:
            self.assertFalse(eligibility[talent_ids[slug]], slug)
        class_row.nivel = 4
        class_row.save(update_fields=['nivel'])
        eligible = {row['id'] for row in _talentos_asi_catalogo(
            character, derive(character)) if row['elegivel']}
        for slug in ('adepto-marcial', 'maestria-em-armaduras-medias',
                     'mestre-de-escudo'):
            self.assertIn(talent_ids[slug], eligible, slug)
        self.assertNotIn(talent_ids['duelista-defensivo'], eligible)

    def test_talento_livre_aplica_seu_mais_um_no_atributo_escolhido(self):
        payload = self._payload("guerreiro")
        talento = TbTalento.objects.filter(tipo__iexact="geral").first()
        from home.views import _talento_attr_options
        atributo = _talento_attr_options(talento)[0]
        classes = [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}]
        base = self._post_preview(payload, self._build("guerreiro", classes=classes)).json()["build"]
        response = self._post_preview(payload, self._build("guerreiro", **{
            "classes": classes,
            "talentos": [{"slug": talento.slug, "atributo": atributo}],
        }))
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["build"]
        before = next(row["valor"] for row in base["atributos"] if row["sig"] == atributo)
        after = next(row["valor"] for row in result["atributos"] if row["sig"] == atributo)
        self.assertEqual(after, before + 1)
        self.assertNotIn("Escolha o atributo", " ".join(result["validacao"]["problemas"]))
        self.assertEqual(result["orcamento"]["asi_em_talento"], 1)
        removed = self._post_preview(payload, self._build("guerreiro", classes=classes))
        reverted = removed.json()["build"]
        self.assertEqual(next(row["valor"] for row in reverted["atributos"]
                              if row["sig"] == atributo), before)
        self.assertEqual(reverted["orcamento"]["asi_em_talento"], 0)
        invalid = self._post_preview(payload, self._build("guerreiro", **{
            "classes": classes,
            "talentos": [{"slug": talento.slug, "atributo": "INVALID"}],
        })).json()["build"]
        self.assertIn("nao pode aumentar", " ".join(invalid["validacao"]["problemas"]))
        self.assertEqual(next(row["valor"] for row in invalid["atributos"]
                              if row["sig"] == atributo), before)

    def test_talento_legado_sem_atributo_continua_editavel_mas_e_sinalizado(self):
        payload = self._payload("guerreiro")
        talento = TbTalento.objects.filter(tipo__iexact="geral").first()
        response = self._post_preview(payload, self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
            "talentos": [talento.slug],
        }))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("Escolha o atributo", " ".join(
            response.json()["build"]["validacao"]["problemas"]))

    def test_preview_sinaliza_payload_de_sessenta_pontos_para_quatro_em_ambos_os_modos(self):
        """Sandbox deriva a ficha, mas nunca considera valido burlar o orcamento de ASI."""
        payload = self._payload("guerreiro")
        base_build = self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 6, "subclasse": ""}],
            "atributos_bonus": {
                "FOR": 10, "DES": 10, "CON": 10,
                "INT": 10, "SAB": 10, "CAR": 10,
            },
        })
        before = TbPersonagem.objects.count()
        for modo in ("regras", "sandbox"):
            build = dict(base_build, modo=modo)
            response = self._post_preview(payload, build)
            self.assertEqual(response.status_code, 200, response.content)
            result = response.json()["build"]
            self.assertFalse(result["validacao"]["valida"])
            self.assertEqual(result["orcamento"]["pontos_usados"], 60)
            self.assertEqual(result["orcamento"]["pontos_disponiveis"], 4)
            self.assertIn("distribuiu 60", " ".join(result["validacao"]["problemas"]))
            self.assertEqual(TbPersonagem.objects.count(), before)

    def test_resiliente_repetido_nao_cria_duas_salvaguardas(self):
        """Duplicar o cartao no payload nao pode gastar dois slots nem abrir dois picks."""
        payload = self._payload("guerreiro")
        resiliente = TbTalento.objects.get(slug="resiliente")
        build = self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
            "talentos": [
                {"slug": resiliente.slug, "atributo": "DES"},
                {"slug": resiliente.slug, "atributo": "DES"},
            ],
        })
        first = self._post_preview(payload, build)
        self.assertEqual(first.status_code, 400, first.content)
        self.assertIn("repetido", first.json()["erros"][0])
        build["talentos"].pop()
        corrected = self._post_preview(payload, build)
        self.assertEqual(corrected.status_code, 200, corrected.content)
        first_build = corrected.json()["build"]
        self.assertEqual(first_build["orcamento"]["asi_em_talento"], 1)
        self.assertEqual(sum(row["nome"] == resiliente.nome
                             for row in first_build["features"]), 1)
        groups = [row for row in first_build["escolhas_grupos"]
                  if row["origem"] == resiliente.nome]
        self.assertEqual(len(groups), 1)

        # O unico pick concedido pelo talento aceita uma unica salvaguarda.
        group = groups[0]
        options = [row["valor"] for row in group["opcoes"]]
        self.assertGreaterEqual(len(options), 2)
        build["escolhas"] = {group["key"]: options[:2]}
        second = self._post_preview(payload, build)
        self.assertEqual(second.status_code, 400)
        self.assertIn("somente 1", second.json()["erros"][0])

    def test_talento_malformado_nao_e_descartado_da_previa(self):
        payload = self._payload("guerreiro")
        build = self._build("guerreiro", classes=[
            {"slug": "guerreiro", "nivel": 4, "subclasse": ""}])
        before = TbPersonagem.objects.count()
        for talents in (None, {}, [None], [True], [5], [""],
                        [{"slug": "resiliente", "atributo": True}]):
            with self.subTest(talents=talents):
                response = self._post_preview(payload, {**build, "talentos": talents})
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(TbPersonagem.objects.count(), before)
        legacy = self._post_preview(payload, {**build, "talentos": ["resiliente"]})
        self.assertEqual(legacy.status_code, 200, legacy.content)
        self.assertIn("Escolha o atributo", " ".join(
            legacy.json()["build"]["validacao"]["problemas"]))

    def test_subescolha_de_resiliente_fica_inerte_sem_talento(self):
        """Uma chave antiga nao concede salvaguarda sem a fonte que a declarou."""
        payload = self._payload("guerreiro")
        resiliente = TbTalento.objects.get(slug="resiliente")
        active = self._build("guerreiro", **{
            "classes": [{"slug": "guerreiro", "nivel": 4, "subclasse": ""}],
            "talentos": [{"slug": resiliente.slug, "atributo": "DES"}],
        })
        first = self._post_preview(payload, active)
        self.assertEqual(first.status_code, 200, first.content)
        group = next(row for row in first.json()["build"]["escolhas_grupos"]
                     if row["origem"] == resiliente.nome)
        chosen = group["opcoes"][0]["valor"]
        active["escolhas"] = {group["key"]: [chosen]}

        resolved = self._post_preview(payload, active)
        self.assertEqual(resolved.status_code, 200, resolved.content)
        resolved_group = next(row for row in resolved.json()["build"]["escolhas_grupos"]
                              if row["key"] == group["key"])
        self.assertEqual([row["valor"] for row in resolved_group["resolvidas"]], [chosen])

        # A chave permanece no cliente, mas sem Resiliente nao existe grupo que a persista.
        removed = self._build("guerreiro", **{
            "classes": active["classes"],
            "escolhas": active["escolhas"],
        })
        without_talent = self._post_preview(payload, removed)
        self.assertEqual(without_talent.status_code, 200, without_talent.content)
        without_build = without_talent.json()["build"]
        self.assertFalse(any(row["origem"] == resiliente.nome
                             for row in without_build["escolhas_grupos"]))

        # O cliente limpa a chave ao retirar a fonte; recolocar exige nova escolha.
        restored = self._post_preview(payload, self._build("guerreiro", **{
            "classes": active["classes"],
            "talentos": [{"slug": resiliente.slug, "atributo": "DES"}],
        }))
        self.assertEqual(restored.status_code, 200, restored.content)
        restored_build = restored.json()["build"]
        restored_groups = [row for row in restored_build["escolhas_grupos"]
                           if row["origem"] == resiliente.nome]
        self.assertEqual(len(restored_groups), 1)
        self.assertEqual(restored_groups[0]["resolvidas"], [])
        self.assertEqual(restored_groups[0]["pendentes"], 1)

    def test_escolhas_malformadas_nao_sao_reduzidas_em_silencio(self):
        base = self._payload('guerreiro')
        build = self._build('guerreiro', classes=[
            {'slug': 'guerreiro', 'nivel': 4, 'subclasse': ''}],
            talentos=[{'slug': 'resiliente', 'atributo': 'DES'}])
        first = self._post_preview(base, build)
        self.assertEqual(first.status_code, 200, first.content)
        group = next(row for row in first.json()['build']['escolhas_grupos']
                     if row['origem'] == TbTalento.objects.get(slug='resiliente').nome)
        selected = group['opcoes'][0]['valor']
        before = TbPersonagem.objects.count()
        for choices in (None, [], {group['key']: 'invalido'},
                        {group['key']: [selected, selected]},
                        {group['key']: [selected, None]},
                        {group['key']: [True]}):
            with self.subTest(choices=choices):
                response = self._post_preview(base, {**build, 'escolhas': choices})
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(response.json()['ok'])
                self.assertEqual(TbPersonagem.objects.count(), before)

        corrected = self._post_preview(base, {**build, 'escolhas': {
            group['key']: [selected]}})
        self.assertEqual(corrected.status_code, 200, corrected.content)
        resolved = next(row for row in corrected.json()['build']['escolhas_grupos']
                        if row['key'] == group['key'])
        self.assertEqual([row['valor'] for row in resolved['resolvidas']], [selected])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_marcos_de_talento_racial_usam_o_resolvedor_do_levelup(self):
        payload = self._payload("guerreiro")
        classes = [{"slug": "guerreiro", "nivel": 17, "subclasse": ""}]
        first = self._post_preview(payload, self._build("guerreiro", classes=classes))
        self.assertEqual(first.status_code, 200, first.content)
        groups = first.json()["build"]["talentos_raciais_grupos"]
        self.assertTrue(groups, "a raca da fixture deve possuir marco racial acima do nivel 1")
        group = groups[0]
        choice = group["opcoes"][0]["nome"]
        second = self._post_preview(payload, self._build("guerreiro", **{
            "classes": classes,
            "talentos_raciais": [{"nivel": group["nivel"], "nome": choice}],
        }))
        self.assertEqual(second.status_code, 200, second.content)
        resolved = next(row for row in second.json()["build"]["talentos_raciais_grupos"]
                        if row["nivel"] == group["nivel"])
        self.assertEqual(resolved["selecionado"], choice)

    def test_talentos_raciais_ambiguos_nao_sao_descartados_silenciosamente(self):
        payload = self._payload("guerreiro")
        classes = [{"slug": "guerreiro", "nivel": 17, "subclasse": ""}]
        first = self._post_preview(payload, self._build("guerreiro", classes=classes))
        self.assertEqual(first.status_code, 200, first.content)
        group = first.json()["build"]["talentos_raciais_grupos"][0]
        choice = {"nivel": group["nivel"], "nome": group["opcoes"][0]["nome"]}
        before = TbPersonagem.objects.count()
        for rows in ([choice, dict(choice)], [None], None,
                     [{"nivel": group["nivel"], "nome": ""}]):
            with self.subTest(rows=rows):
                response = self._post_preview(payload, self._build(
                    "guerreiro", classes=classes, talentos_raciais=rows))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(response.json()["ok"])
                self.assertEqual(TbPersonagem.objects.count(), before)
        corrected = self._post_preview(payload, self._build(
            "guerreiro", classes=classes, talentos_raciais=[choice]))
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertEqual(corrected.json()["build"]["talentos_raciais_grupos"][0]["selecionado"],
                         choice["nome"])

    def test_talento_racial_obsoleto_permanece_visivel_para_correcao(self):
        payload = self._payload("guerreiro")
        classes = [{"slug": "guerreiro", "nivel": 17, "subclasse": ""}]
        first = self._post_preview(payload, self._build("guerreiro", classes=classes))
        self.assertEqual(first.status_code, 200, first.content)
        group = next(row for row in first.json()["build"]["talentos_raciais_grupos"]
                     if row["nivel"] >= 5)
        before = TbPersonagem.objects.count()
        stale = self._post_preview(payload, self._build("guerreiro", **{
            "classes": classes,
            "talentos_raciais": [{"nivel": group["nivel"], "nome": "Escolha obsoleta"}],
        }))
        self.assertEqual(stale.status_code, 200, stale.content)
        result = stale.json()["build"]
        stale_group = next(row for row in result["talentos_raciais_grupos"]
                           if row["nivel"] == group["nivel"])
        self.assertEqual(stale_group["selecionado"], "Escolha obsoleta")
        self.assertNotIn("Escolha obsoleta", [row["nome"] for row in stale_group["opcoes"]])
        self.assertFalse(result["validacao"]["valida"])
        self.assertTrue(any("Talento racial invalido" in issue
                            for issue in result["validacao"]["problemas"]))
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_marcos_raciais_5_a_17_concordam_com_criacao_laboratorio_e_ficha(self):
        from home import views

        expected_levels = [5, 9, 13, 17]
        classes = [{"slug": "guerreiro", "nivel": 17, "subclasse": ""}]
        variants = (
            ("anao-linhagem", "anao", {"linhagem_slug": "montanha"}),
            ("anao-essencia", "anao", {"essencia_slug": "draconica", "vertente": "Vermelho"}),
            ("elfo", "elfo", {}),
            ("orc", "orc", {}),
            ("humano", "humano", {}),
        )
        for label, race_slug, identity in variants:
            with self.subTest(origem=label):
                owner = self._novo_usuario("marcos-raciais-" + label)
                payload = self._payload("guerreiro", raca_slug=race_slug, **identity)
                if label == "anao-essencia":
                    payload.setdefault("escolhas_raca", {})["menus"] = [{
                        "tipo": "alento_elemental", "fonte": "Alento Elemental",
                        "valores": ["fogo"],
                    }]
                created = self._post_criar(owner, payload)
                self.assertTrue(created.json()["ok"], created.content)
                character = TbPersonagem.objects.get(pk=created.json()["id"])
                primary = character.classes.get(principal=True)
                primary.nivel = 17
                primary.save(update_fields=["nivel"])
                character.nivel = 17
                character.save(update_fields=["nivel", "atualizado_em"])
                levelup_groups = views._pendencias_talento_racial(character)
                self.assertEqual([row["nivel"] for row in levelup_groups], expected_levels)

                selections = []
                count_before_preview = TbPersonagem.objects.count()
                for level in expected_levels:
                    response = self._post_preview(payload, self._build("guerreiro", **{
                        "classes": classes, "talentos_raciais": selections,
                    }))
                    self.assertEqual(response.status_code, 200, response.content)
                    groups = response.json()["build"]["talentos_raciais_grupos"]
                    self.assertEqual([row["nivel"] for row in groups], expected_levels)
                    group = next(row for row in groups if row["nivel"] == level)
                    self.assertTrue(group["opcoes"], f"Sem escolha disponível no nível {level}")
                    selections.append({"nivel": level, "nome": group["opcoes"][0]["nome"]})

                completed = self._post_preview(payload, self._build("guerreiro", **{
                    "classes": classes, "talentos_raciais": selections,
                }))
                self.assertEqual(completed.status_code, 200, completed.content)
                result = completed.json()["build"]
                self.assertEqual(
                    [(row["nivel"], row["selecionado"])
                     for row in result["talentos_raciais_grupos"]],
                    [(row["nivel"], row["nome"]) for row in selections])
                self.assertFalse(any("Talento racial invalido" in issue
                                     for issue in result["validacao"]["problemas"]))
                self.assertEqual(TbPersonagem.objects.count(), count_before_preview)
                for selection in selections:
                    saved = self.client.post(
                        reverse("personagem_escolher_talento_racial", args=[character.pk]),
                        data={"nivel": selection["nivel"], "talento": selection["nome"]})
                    self.assertEqual(saved.status_code, 302)
                    self.assertEqual(character.talentos.filter(
                        categoria="racial", nivel=selection["nivel"],
                        nome=selection["nome"]).count(), 1)
                self.assertEqual(views._pendencias_talento_racial(character), [])

    def test_marcos_raciais_cobrem_todas_linhagens_e_essencias_do_catalogo(self):
        from home import views
        from django.db import transaction

        races = list(TbRaca.objects.order_by('slug'))
        lineages = list(TbLinhagem.objects.select_related('id_raca').order_by('id_linhagem'))
        essences = list(TbEssencia.objects.order_by('slug'))
        self.assertEqual(len(lineages), 16)
        self.assertEqual(len(essences), 4)
        variants = [
            (f'linhagem:{lineage.id_raca.slug}:{lineage.slug}', lineage.id_raca.slug,
             {'linhagem_slug': lineage.slug})
            for lineage in lineages
        ] + [
            (f'essencia:{race.slug}:{essence.slug}', race.slug,
             {'essencia_slug': essence.slug})
            for race in races if race.permite_essencia for essence in essences
        ]
        self.assertEqual(len(variants), 32)

        for index, (label, race_slug, identity) in enumerate(variants):
            with self.subTest(identity=label):
                owner = self._novo_usuario(f'matriz-racial-{index}')
                if identity.get('essencia_slug') == 'draconica':
                    identity = {**identity, 'vertente': 'Vermelho'}
                elif identity.get('essencia_slug') in ('elemental', 'vampirismo'):
                    essence = TbEssencia.objects.get(slug=identity['essencia_slug'])
                    identity = {**identity,
                                'vertente': views._essencia_subescolha(essence)['opcoes'][0]['slug']}
                payload = self._payload('guerreiro', raca_slug=race_slug, **identity)
                if identity.get('essencia_slug') == 'draconica':
                    payload.setdefault('escolhas_raca', {}).setdefault('menus', []).append({
                        'tipo': 'alento_elemental', 'fonte': 'Alento Elemental',
                        'valores': ['fogo'],
                    })
                if identity.get('essencia_slug') == 'nephilim':
                    essence = TbEssencia.objects.get(slug='nephilim')
                    sources = TbTracoracial.objects.filter(
                        id_essencia=essence, talento_racial=False, nivel_requisito__lte=1)
                    payload.setdefault('escolhas_raca', {}).setdefault('menus', []).extend({
                        'tipo': group['kind'], 'fonte': group['origem'],
                        'valores': [group['universo'][0]['slug']],
                    } for group in views._racial_menu_groups(sources))
                if (identity.get('linhagem_slug') == 'sálarin'
                        or identity.get('essencia_slug') == 'nephilim'):
                    resolved, errors = views._criador_resolver(payload)
                    self.assertFalse(errors, errors)
                    with transaction.atomic():
                        temporary = views._criador_persistir(owner, payload, resolved)
                        payload['magias_concedidas'] = [{
                            'fonte': group['fonte'], 'slot': group['slot'],
                            'magias': [group['opcoes'][0]['slug']],
                        } for group in temporary._criador_spell_groups]
                        transaction.set_rollback(True)
                created = self._post_criar(owner, payload)
                self.assertTrue(created.json().get('ok'), created.content)
                character = TbPersonagem.objects.get(pk=created.json()['id'])
                character.classes.filter(principal=True).update(nivel=17)
                character.nivel = 17
                character.save(update_fields=['nivel', 'atualizado_em'])
                groups = views._pendencias_talento_racial(character)
                self.assertEqual([group['nivel'] for group in groups], [5, 9, 13, 17])
                expected = [(group['nivel'], {option['nome'] for option in group['opcoes']})
                            for group in groups]
                self.assertTrue(all(options for _, options in expected), label)

                count_before = TbPersonagem.objects.count()
                preview = self._post_preview(payload, self._build(
                    'guerreiro', classes=[{'slug': 'guerreiro', 'nivel': 17, 'subclasse': ''}]))
                self.assertEqual(preview.status_code, 200, preview.content)
                actual = [(group['nivel'], {option['nome'] for option in group['opcoes']})
                          for group in preview.json()['build']['talentos_raciais_grupos']]
                self.assertEqual(actual, expected)
                self.assertEqual(TbPersonagem.objects.count(), count_before)

    def test_preview_deriva_niveis_subclasse_itens_talentos_e_magias_sem_persistir(self):
        payload = self._payload("guerreiro")
        classe = TbClasse.objects.get(slug="guerreiro")
        subclasse = TbSubclasse.objects.filter(id_classe=classe).first()
        talento = TbTalento.objects.exclude(tipo__iexact="origem").first()
        mundano = TbItemMundano.objects.first()
        magico = TbItemMagico.objects.first()
        magia = TbMagia.objects.first()
        self.assertIsNotNone(subclasse)
        self.assertIsNotNone(talento)
        self.assertIsNotNone(mundano)
        self.assertIsNotNone(magico)
        self.assertIsNotNone(magia)

        tracked_models = (
            TbPersonagem,
            TbPersonagemClasse,
            TbPersonagemAtributoBonus,
            TbPersonagemTalento,
            TbPersonagemItem,
            TbPersonagemMagia,
        )
        before = {model: model.objects.count() for model in tracked_models}
        build = {
            "classes": [{
                "slug": "guerreiro",
                "nivel": 5,
                "subclasse": subclasse.slug,
            }],
            "atributos_bonus": {"FOR": 2},
            "talentos": [talento.slug],
            "itens": [
                {"tipo": "mundano", "slug": mundano.slug, "qtd": 2, "equipado": True},
                {"tipo": "magico", "slug": magico.slug, "qtd": 1,
                 "equipado": True, "sintonizado": True},
            ],
            "magias": [{"slug": magia.slug, "preparada": True}],
        }

        response = self._post_preview(payload, build)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["build"]
        self.assertEqual(result["nivel"], 5)
        self.assertEqual(result["classes"][0]["subclasse"], subclasse.nome)
        self.assertEqual(
            next(row for row in result["atributos"] if row["sig"] == "FOR")["valor"],
            payload["scores"]["FOR"] + 2,
        )
        self.assertTrue(any(row["nome"] == talento.nome for row in result["features"]))
        self.assertTrue(any(row["nome"] == mundano.nome for row in result["inventario"]))
        self.assertTrue(any(row["nome"] == magia.nome for row in result["magias"]))
        # e tudo isso aparece na FOLHA, nao so no JSON
        html = result["ficha_html"]
        self.assertIn(subclasse.nome, html)
        self.assertIn(talento.nome, html)
        self.assertIn(mundano.nome, html)
        for model in tracked_models:
            self.assertEqual(model.objects.count(), before[model], model.__name__)

    def test_preview_rejeita_nivel_total_acima_de_vinte_sem_persistir(self):
        payload = self._payload("guerreiro")
        outra = TbClasse.objects.exclude(slug="guerreiro").first()
        before = TbPersonagem.objects.count()
        response = self._post_preview(payload, {
            "classes": [
                {"slug": "guerreiro", "nivel": 20, "subclasse": ""},
                {"slug": outra.slug, "nivel": 1, "subclasse": ""},
            ],
            "atributos_bonus": {},
            "talentos": [],
            "itens": [],
            "magias": [],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("20", response.json()["erros"][0])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_preview_resolve_pick_novo_pelo_registry_sem_persistir(self):
        classe = TbClasse.objects.get(slug="mago")
        TbClassehabilidade.objects.create(
            id_classe=classe,
            nome="Escolha do Laboratorio",
            descricao="Escolha sintetica.",
            niveladquirido=2,
            tags_json=["pick:opcao:teste_pathbuilder:1"],
        )
        option = TbOpcaojogo.objects.create(
            nome="Opcao do Laboratorio",
            slug="opcao-pathbuilder",
            tipo="Teste Pathbuilder",
            descricao="Efeito sintetico.",
            tags_json=[],
        )
        payload = self._payload("mago")
        build = self._build("mago", **{
            "classes": [{"slug": "mago", "nivel": 2, "subclasse": ""}],
        })
        before = TbPersonagemEscolha.objects.count()
        first = self._post_preview(payload, build)
        self.assertEqual(first.status_code, 200, first.content)
        group = next(
            row for row in first.json()["build"]["escolhas_grupos"]
            if row["label"] == "Teste Pathbuilder"
        )
        self.assertEqual(group["pendentes"], 1)
        self.assertEqual(group["opcoes"][0]["valor"], option.slug)
        # o cartao da escolha mostra o efeito no lugar — a descricao viaja com a opcao
        self.assertEqual(group["opcoes"][0]["descricao"], "Efeito sintetico.")

        build["escolhas"] = {group["key"]: [option.slug]}
        second = self._post_preview(payload, build)
        self.assertEqual(second.status_code, 200, second.content)
        resolved = next(
            row for row in second.json()["build"]["escolhas_grupos"]
            if row["key"] == group["key"]
        )
        self.assertEqual(resolved["pendentes"], 0)
        self.assertEqual(resolved["selecionadas"], [option.slug])
        self.assertEqual([row["valor"] for row in resolved["resolvidas"]], [option.slug])
        self.assertEqual(TbPersonagemEscolha.objects.count(), before)

    def test_modo_regras_e_conjuracao_usam_estado_derivado(self):
        payload = self._payload("mago")
        build = self._build("mago", modo="regras")
        response = self._post_preview(payload, build)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["build"]
        self.assertEqual(result["validacao"]["modo"], "regras")
        self.assertFalse(result["validacao"]["valida"])
        self.assertTrue(result["validacao"]["problemas"])
        self.assertTrue(result["conjuracao"]["spellcasters"])
        # conjuracao aparece na folha (CD e ataque de magia), nao numa aba paralela
        self.assertIn("CD ", result["ficha_html"])
