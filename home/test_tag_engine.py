from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from home.character_engine import _apply_attr_asi, _dado_de_vida_classe, apply_tags
from home.tag_engine import evaluate_tags, parse_tags
from home.tag_engine.evaluator import Evaluator
from home.tag_engine.library import Library
from home.tag_engine.parser import ParseError, parse_tag
from home.tag_engine.validator import (ERROR, _check_innate_casting_tags,
                                      validate_tag_line)


class TagParserTests(SimpleTestCase):
    def test_preserva_ordem_e_escopo_lexico(self):
        program = parse_tags([
            "action:bonus_action",
            "always_active{restriction{equiped{armor}},ca=10+dex_mod}",
            "resist:fogo",
        ])

        self.assertEqual(
            [node.name for node in program.nodes],
            ["action", "always_active", "resist"],
        )
        always = program.nodes[1]
        self.assertEqual(
            [(node.name, node.scope) for node in always.children],
            [
                ("restriction", ("always_active",)),
                ("ca", ("always_active",)),
            ],
        )

    def test_head_so_de_pontos_levanta_parseerror_e_nao_indexerror(self):
        # Um head só-de-pontos ("...", ".") não tem identificador para ancorar a cláusula.
        # Antes isso dava IndexError não-tratado em parser.py (`head = bits[-1]`) que escapava
        # por parse_tag/evaluate_tags e derrubava validate_tags E derive. Agora vira ParseError
        # (capturado a montante). Cobre entrada malformada mesmo com o dado saneado.
        for malformada in ("...", "foo{...}", "block{a, .}", "."):
            with self.assertRaises(ParseError):
                parse_tag(malformada)
        # e não pode ser IndexError: parse_tags (usado por evaluate_tags/derive) idem.
        with self.assertRaises(ParseError):
            parse_tags(["foo{...}"])

    def test_ponto_e_virgula_separa_statements_legados(self):
        program = parse_tags([
            "resist:fogo; speed:+10; instant{dmg:+1d6; push:5ft}",
        ])

        self.assertEqual(
            [node.name for node in program.nodes],
            ["resist", "speed", "instant"],
        )
        self.assertEqual(
            [node.name for node in program.nodes[2].children],
            ["dmg", "push"],
        )


class GenericEvaluatorTests(SimpleTestCase):
    def test_avalia_primitivas_pela_biblioteca(self):
        result = evaluate_tags(
            ["always_active{ca=10+dex_mod,resist:fogo}"],
            {"dex_mod": 3},
        )

        self.assertFalse(result.blocked)
        self.assertEqual(result.state["ca"], 13)
        self.assertEqual(result.state["resistencias"], ["fogo"])

    def test_nova_primitiva_com_operacao_existente_nao_exige_codigo(self):
        library = Library()
        library.raw["primitives"]["bonus_teste"] = {
            "forma": "key_value",
            "op": "add_modifier",
            "target": "testes",
        }
        library._index()

        result = Evaluator(library).evaluate(
            ["bonus_teste:+pb"],
            {"pb": 4},
        )

        self.assertEqual(result.state["testes"][0]["value"], 4)
        self.assertEqual(result.operations[0].verb, "bonus_teste")

    def test_set_property_materializa_propriedades_sem_verbo_especifico(self):
        result = evaluate_tags([
            "need:air=false",
            "need:food=false",
            "need:sleep=false",
        ])

        self.assertEqual(
            result.state["corpo"]["necessidades"],
            {"air": False, "food": False, "sleep": False},
        )

    def test_suppress_e_operacao_distinta_de_condicao(self):
        result = evaluate_tags(["suppress{adv:attack{vs:self}}"])

        self.assertEqual(result.operations[0].op, "suppress")
        self.assertEqual(result.operations[0].target, "efeitos.suprimidos")

    def test_operando_expoe_argumentos_tipados_sem_perder_valor_legado(self):
        result = evaluate_tags(
            [
                "prof:armor{light}",
                "sense:darkvision(range:+60ft, if_present)",
                "check_bonus:religiao=max(wis_mod,1)",
            ],
            {"wis_mod": 3},
        )

        prof, sense, check = result.operations
        self.assertEqual(prof.value, "armor{light}")
        self.assertEqual(prof.params["name"], "armor")
        self.assertEqual(prof.params["args"], ["light"])
        self.assertEqual(sense.params["name"], "darkvision")
        self.assertEqual(sense.params["kwargs"]["range"], 60)
        self.assertEqual(sense.params["raw_kwargs"]["range"], "+60ft")
        self.assertIn("if_present", sense.params["flags"])
        self.assertEqual(check.params["name"], "religiao")
        self.assertEqual(check.params["binding"]["value"], 3)

    def test_operador_distingue_atribuicao_de_modificador(self):
        result = evaluate_tags(["ca=10+dex_mod", "ca:+2"], {"dex_mod": 3})

        self.assertEqual(
            [(operation.op, operation.target, operation.value)
             for operation in result.operations],
            [
                ("set_value", "ca", 13),
                ("add_modifier", "ca", 2),
            ],
        )
        self.assertEqual(result.state["ca"]["_value"], 13)
        self.assertEqual(result.state["ca"]["_values"][0]["value"], 2)

    def test_formula_suporta_comparacao_sem_executar_codigo_arbitrario(self):
        allowed = evaluate_tags(
            ["ca:+1(requires:dex_score>=16)"],
            {"dex_score": 16},
        )
        blocked = evaluate_tags(
            ["ca:+1(requires:dex_score>=16)"],
            {"dex_score": 15},
        )

        self.assertIs(allowed.operations[0].params["kwargs"]["requires"], True)
        self.assertIs(blocked.operations[0].params["kwargs"]["requires"], False)

    def test_dado_de_vida_mecanico_vem_do_target_e_nao_do_texto(self):
        classe = SimpleNamespace(
            tags_json=["hit_dice:1d8"],
            dado_vida="1d6 (texto desatualizado)",
        )

        self.assertEqual(_dado_de_vida_classe(classe), 8)

    def test_restriction_no_topo_bloqueia_habilidade_inteira(self):
        result = evaluate_tags(
            ["restriction{equiped{heavy_armor}}", "ca=13", "resist:fogo"],
            {"equipped": {"heavy_armor"}},
        )

        self.assertTrue(result.blocked)
        self.assertEqual(result.state, {})

    def test_restriction_de_equipamento_aceita_conjunto(self):
        result = evaluate_tags(
            ["restriction{equiped{armor,shield}}", "ca=13"],
            {"equipped": {"shield"}},
        )

        self.assertTrue(result.blocked)

    def test_restriction_de_equipamento_acumula_predicados(self):
        result = evaluate_tags(
            [
                "always_active{restriction{equiped{armadura},"
                " equiped{escudo}}, speed:+10}"
            ],
            {"equipped": {"shield"}},
        )

        self.assertFalse(result.blocked)
        self.assertNotIn("speed", {op.verb for op in result.operations})
        self.assertEqual(
            result.state["blocked_scopes"][0]["scope"],
            "always_active",
        )

    def test_restriction_aninhada_bloqueia_apenas_bloco_pai(self):
        result = evaluate_tags(
            [
                "always_active{restriction{equiped{armor}},ca=10+dex_mod}",
                "resist:fogo",
            ],
            {"equipped": {"armor"}, "dex_mod": 3},
        )

        self.assertFalse(result.blocked)
        self.assertNotIn("ca", result.state)
        self.assertEqual(result.state["resistencias"], ["fogo"])
        self.assertEqual(
            result.state["blocked_scopes"][0]["scope"],
            "always_active",
        )

    def test_condicao_relacional_usa_argumento_source(self):
        tag = "requires:condition{amedrontado, source:self}"

        allowed = evaluate_tags(
            [tag, "adv:atk"],
            {"conditions": {"amedrontado": {"self"}}},
        )
        blocked = evaluate_tags(
            [tag, "adv:atk"],
            {"conditions": {"amedrontado": {"enemy"}}},
        )

        self.assertFalse(allowed.blocked)
        self.assertTrue(blocked.blocked)

    def test_condicao_do_proprio_alvo_usa_argumento_target(self):
        result = evaluate_tags(
            ["restriction:condition{incapacitado, target:self}", "ca:+1"],
            {"conditions": {"incapacitado": None}},
        )

        self.assertTrue(result.blocked)

    def test_requires_de_nivel_aceita_forma_compacta(self):
        self.assertTrue(evaluate_tags(
            ["requires:lvl{5}", "initiative:+pb"],
            {"lvl": 4, "pb": 3},
        ).blocked)
        self.assertFalse(evaluate_tags(
            ["requires:lvl{5}", "initiative:+pb"],
            {"lvl": 5, "pb": 3},
        ).blocked)

    def test_efeito_condicional_de_tamanho_preserva_ataque_base(self):
        tag = (
            "instant{attack:melee, dmg:1d6+2(perfurante), "
            "instant{trigger=hit, requires:target{size<=medio}, apply:caido}}"
        )
        for size in ("miudo", "medium", "Médio", "M"):
            result = evaluate_tags([tag], {"target_size": size})
            self.assertEqual([op.verb for op in result.operations].count("apply"), 1)
        blocked = evaluate_tags([tag], {"target_size": "grande"})
        self.assertNotIn("apply", [op.verb for op in blocked.operations])
        self.assertIn("dmg", [op.verb for op in blocked.operations])
        self.assertNotIn("apply", [op.verb for op in
                         evaluate_tags([tag], {"target_size": "Colossal"}).operations])
        self.assertTrue(evaluate_tags(
            ["restriction{target{size>grande}}", "ca:+1"],
            {"target_size": "enorme"},
        ).blocked)
        unknown = evaluate_tags([tag])
        self.assertEqual([op.active for op in unknown.operations if op.verb == "apply"], [False])
        self.assertFalse([d for d in validate_tag_line(tag, Library()) if d.level == ERROR])
        bad = tag.replace("size<=medio", "size<=banana")
        self.assertIn("tamanho-alvo-invalido", [d.code for d in
                      validate_tag_line(bad, Library()) if d.level == ERROR])

    def test_not_inverte_predicado_de_condition(self):
        tag = "requires:not{condition{incapacitado, target:self}}"

        allowed = evaluate_tags([tag, "ca:+1"], {"conditions": {}})
        blocked = evaluate_tags(
            [tag, "ca:+1"],
            {"conditions": {"incapacitado": None}},
        )

        self.assertFalse(allowed.blocked)
        self.assertTrue(blocked.blocked)

    def test_not_inverte_predicado_de_equipamento(self):
        tag = "restriction{not{equipped{mascara_da_piedade}}}"

        blocked = evaluate_tags([tag, "ca:+1"], {"equipped": set()})
        allowed = evaluate_tags(
            [tag, "ca:+1"],
            {"equipped": {"mascara_da_piedade"}},
        )

        self.assertTrue(blocked.blocked)
        self.assertFalse(allowed.blocked)

    def test_escopo_runtime_e_preservado_sem_materializar_bonus(self):
        result = evaluate_tags(
            ["while_active{restricts{spellcasting,concentration},resist:fogo}"],
        )

        self.assertNotIn("resistencias", result.state)
        self.assertTrue(result.state["runtime"])
        self.assertTrue(all(not operation.active for operation in result.operations))

    def test_declaracoes_e_ramos_nao_vazam_efeitos_estaticos(self):
        result = evaluate_tags([
            "define{escolha:list{a:{resist:fogo},b:{immune:frio}}}",
            "match(tipo){a:{sense:darkvision(range:60ft)}}",
            "if(alvo):{speed:+10}",
        ])

        self.assertNotIn("resistencias", result.state)
        self.assertNotIn("imunidades", result.state)
        self.assertNotIn("sentidos", result.state)
        self.assertNotIn("movimento", result.state)
        self.assertTrue(result.state["runtime"])

    @patch("home.character_engine._cond_nomes", return_value={})
    def test_ficha_consumindo_operacoes_nao_duplica_fallback(self, _conditions):
        feature = SimpleNamespace(
            nome="Feature sintética",
            tags_json=[
                "initiative:+pb",
                "save_prof:wis",
                "prof:atletismo",
                "always_active{buff:max_hp:+lvl}",
                "always_active{ca=10+dex_mod}",
                "ca:+2",
            ],
        )
        state = {
            "_ctx": {
                "lvl": 5,
                "classlvl": 5,
                "pb": 3,
                "dex_mod": 2,
            },
            "pv": {"maximo_calculado": 30},
            "ca": 10,
            "velocidade": "9 m / 30 ft",
            "recursos": {},
        }

        result = apply_tags(
            state,
            [("classe", "Feature sintética", feature, 5)],
        )

        self.assertEqual(result["pv"]["maximo_calculado"], 35)
        self.assertEqual(result["ca"], 14)
        self.assertEqual(result["_tag"]["initiative"], 3)
        self.assertEqual(result["_tag"]["save_prof"], {"wis"})
        self.assertEqual(result["_tag"]["skill_prof"], {"atletismo"})

    @patch("home.character_engine._cond_nomes", return_value={})
    def test_ficha_materializa_targets_estaticos_sem_regex_de_feature(self, _conditions):
        feature = SimpleNamespace(
            nome="Feature sintética",
            tags_json=[
                "resist:fogo",
                "immune:frio",
                "cond_immune:envenenado",
                "sense:darkvision(range:120ft)",
                "speed:+10",
                "move:climb(=speed)",
                "check_bonus:atletismo=pb",
                "check_attr:persuasao:=forca",
                "prof:armor{light}",
                "attacks:=2",
            ],
        )
        state = {
            "_ctx": {
                "lvl": 5,
                "classlvl": 5,
                "pb": 3,
                "dex_mod": 2,
            },
            "pv": {"maximo_calculado": 30},
            "ca": 10,
            "velocidade": "9 m / 30 ft",
            "recursos": {},
        }

        result = apply_tags(
            state,
            [("classe", "Feature sintética", feature, 5)],
        )

        self.assertEqual(result["resistencias"], ["fogo"])
        self.assertEqual(result["imunidades"], ["frio", "Envenenado (condição)"])
        self.assertEqual(result["sentidos"], ["darkvision 120ft"])
        self.assertEqual(result["velocidade"], "12 m / 40 ft")
        self.assertEqual(result["movimento_modos"], {"climb": "walk"})
        self.assertEqual(result["_tag"]["check_bonus"], {"atletismo": 3})
        self.assertEqual(result["_tag"]["check_attr"], {"persuasao": "FOR"})
        self.assertEqual(result["_tag"]["armaduras"], ["light"])
        self.assertEqual(result["_tag"]["n_ataques"], 2)

    @patch("home.character_engine._cond_nomes", return_value={})
    def test_ficha_materializa_bonus_de_magia_por_escopo(self, _conditions):
        feature = SimpleNamespace(
            nome="Foco Arcano",
            tags_json=["spell.atk:+2", "spell.cd:+2"],
        )
        state = {
            "_ctx": {"lvl": 1, "classlvl": 1, "pb": 2, "dex_mod": 0},
            "pv": {"maximo_calculado": 10},
            "ca": 10,
            "velocidade": "9 m / 30 ft",
            "recursos": {},
        }

        result = apply_tags(
            state,
            [("item", feature.nome, feature, 1)],
        )

        self.assertEqual(result["_tag"]["spell_attack_bonus"], 2)
        self.assertEqual(result["_tag"]["spell_save_dc_bonus"], 2)

    def test_piso_de_atributo_usa_formula_generica_max(self):
        feature = SimpleNamespace(
            nome="Manoplas",
            tags_json=["attr:str_score:=max(str_score,19)"],
        )
        attributes = {
            key: {"valor": 10, "bonus": 0, "breakdown": []}
            for key in ("FOR", "DES", "CON", "INT", "SAB", "CAR")
        }

        _apply_attr_asi(
            [("item", feature.nome, feature, 1)],
            {},
            attributes,
        )

        self.assertEqual(attributes["FOR"]["valor"], 19)
        self.assertEqual(attributes["FOR"]["bonus"], 9)

    @patch("home.character_engine._cond_nomes", return_value={})
    def test_ficha_exibe_vantagem_condicional_sem_mostrar_dsl(self, _conditions):
        feature = SimpleNamespace(
            nome="Presenca da Noite",
            tags_json=[
                "adv:death_save",
                "adv:check{percepcao}"
                "(requires:target{sangrando}, in_dim_light)",
            ],
        )
        state = {
            "_ctx": {"lvl": 1, "classlvl": 1, "pb": 2, "dex_mod": 0},
            "pv": {"maximo_calculado": 10},
            "ca": 10,
            "velocidade": "9 m / 30 ft",
            "recursos": {},
        }

        result = apply_tags(
            state,
            [("traco", feature.nome, feature, 1)],
        )
        rendered = " ".join(result["vantagens"])

        self.assertIn("Vantagem em salvaguardas contra a morte", rendered)
        self.assertIn("Vantagem em testes de Percepcao", rendered)
        self.assertIn("alvo: Sangrando", rendered)
        self.assertIn("em penumbra", rendered)
        self.assertNotIn("requires:", rendered)
        self.assertNotIn("check{", rendered)

    @patch("home.character_engine._cond_nomes", return_value={})
    def test_fallback_nao_e_silenciado_quando_alvo_tem_operacao_dinamica(
            self, _conditions):
        feature = SimpleNamespace(
            nome="Resistência mista",
            tags_json=[
                "resist:fogo",
                "resist:source{magical_effect}",
            ],
        )
        state = {
            "_ctx": {"lvl": 1, "classlvl": 1, "pb": 2, "dex_mod": 0},
            "pv": {"maximo_calculado": 10},
            "ca": 10,
            "velocidade": "9 m / 30 ft",
            "recursos": {},
        }

        result = apply_tags(
            state,
            [("classe", "Resistência mista", feature, 1)],
        )

        self.assertEqual(result["resistencias"], ["fogo"])
        self.assertTrue(any(
            "magical effect" in note for note in result["notas_passivas"]
        ))

    @patch("home.character_engine._cond_nomes", return_value={})
    def test_ficha_resolve_gate_inline_por_contexto(self, _conditions):
        feature = SimpleNamespace(
            nome="Defesa condicionada",
            tags_json=["ca:+1(requires:dex_score>=16)"],
        )

        def derive(dex_score):
            return apply_tags(
                {
                    "_ctx": {
                        "lvl": 1, "classlvl": 1, "pb": 2,
                        "dex_mod": 3, "dex_score": dex_score,
                    },
                    "pv": {"maximo_calculado": 10},
                    "ca": 10,
                    "velocidade": "9 m / 30 ft",
                    "recursos": {},
                },
                [("talento", feature.nome, feature, 1)],
            )

        self.assertEqual(derive(15)["ca"], 13)
        self.assertEqual(derive(16)["ca"], 14)


class TagNamingTests(SimpleTestCase):
    def test_contexto_de_rp_em_vantagem_e_rejeitado(self):
        diagnostics = validate_tag_line(
            "adv:check{persuasao}(for:conversar_com_nobres)",
            Library(),
            strict_names=True,
        )
        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "contexto-rp-nao-executavel"
            for diagnostic in diagnostics
        ))

    def test_primitiva_narrativa_removida_e_rejeitada(self):
        diagnostics = validate_tag_line(
            "always_active{rede:contatos_criminais}",
            Library(),
            strict_names=True,
        )
        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "primitiva-nao-mecanica"
            for diagnostic in diagnostics
        ))

    def test_operando_narrativo_removido_e_rejeitado(self):
        diagnostics = validate_tag_line(
            "adv:int_check(scope:recall_info)",
            Library(),
            strict_names=True,
        )
        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "operando-nao-mecanico"
            for diagnostic in diagnostics
        ))

    def test_negacao_especifica_demais_e_rejeitada(self):
        diagnostics = validate_tag_line(
            "no_stealth_disadvantage",
            Library(),
            strict_names=True,
        )
        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "prefixo-legado"
            for diagnostic in diagnostics
        ))

    def test_ponto_e_virgula_e_separador_valido(self):
        diagnostics = validate_tag_line(
            "resist:fogo; without{dadv:check{furtividade}}",
            Library(),
            strict_names=True,
        )
        self.assertFalse(any(
            diagnostic.code == "char-inesperado"
            for diagnostic in diagnostics
        ))

    def test_prefixo_no_e_rejeitado_em_qualquer_mecanica(self):
        diagnostics = validate_tag_line(
            "cast{spell:comando, no_slot}",
            Library(),
            strict_names=True,
        )
        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "prefixo-legado"
            for diagnostic in diagnostics
        ))

    def test_without_e_omissao_de_execucao(self):
        diagnostics = validate_tag_line(
            "cast{spell:comando, without{slot}}",
            Library(),
            strict_names=True,
        )
        self.assertFalse(any(
            diagnostic.level in (ERROR, WARN)
            for diagnostic in diagnostics
        ))

    def test_without_nao_substitui_restricts(self):
        diagnostics = validate_tag_line(
            "while_active{without{teleport}}",
            Library(),
            strict_names=True,
        )

        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "without-sem-execucao"
            for diagnostic in diagnostics
        ))

    def test_without_nao_e_predicado_dentro_de_requires(self):
        diagnostics = validate_tag_line(
            "requires:{target and without{dadv}}",
            Library(),
            strict_names=True,
        )

        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "without-como-predicado"
            for diagnostic in diagnostics
        ))

    def test_without_nao_substitui_suppress(self):
        diagnostics = validate_tag_line(
            "while_active{without{adv:attack{vs:self}}}",
            Library(),
            strict_names=True,
        )

        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "without-sem-execucao"
            for diagnostic in diagnostics
        ))

    def test_not_e_a_negacao_de_predicado(self):
        diagnostics = validate_tag_line(
            "requires:not{condition{incapacitado, target:self}}",
            Library(),
            strict_names=True,
        )

        self.assertFalse(any(
            diagnostic.level in (ERROR, WARN)
            for diagnostic in diagnostics
        ))

    def test_prefixo_not_e_rejeitado(self):
        diagnostics = validate_tag_line(
            "requires:not_incapacitated",
            Library(),
            strict_names=True,
        )

        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "prefixo-legado"
            for diagnostic in diagnostics
        ))

    def test_darkvision_magica_exige_devilsight_separado(self):
        diagnostics = validate_tag_line(
            "sense:darkvision(range:120ft, magical)",
            Library(),
            strict_names=True,
        )

        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "darkvision-magica-agregada"
            for diagnostic in diagnostics
        ))

    def test_darkvision_e_devilsight_separados_sao_validos(self):
        diagnostics = validate_tag_line(
            "sense:darkvision(range:120ft), "
            "sense:devilsight(range:120ft)",
            Library(),
            strict_names=True,
        )

        self.assertFalse(any(
            diagnostic.level in (ERROR, WARN)
            for diagnostic in diagnostics
        ))

    def test_condicao_especifica_por_relacao_e_rejeitada(self):
        diagnostics = validate_tag_line(
            "requires:amedrontado_by_self",
            Library(),
            strict_names=True,
        )

        self.assertTrue(any(
            diagnostic.level == ERROR
            and diagnostic.code == "condicao-relacional-especifica"
            for diagnostic in diagnostics
        ))

    def test_condicao_generica_com_source_e_aceita(self):
        diagnostics = validate_tag_line(
            "requires:condition{amedrontado, source:self}",
            Library(),
            strict_names=True,
        )

        self.assertFalse(any(
            diagnostic.level == ERROR
            and diagnostic.code == "condicao-relacional-especifica"
            for diagnostic in diagnostics
        ))

    def test_condicao_especifica_em_portugues_ou_por_alvo_e_rejeitada(self):
        for tag in (
                "requires:agarrado_por_self",
                "end:incapacitado_self"):
            diagnostics = validate_tag_line(
                tag,
                Library(),
                strict_names=True,
            )
            self.assertTrue(any(
                diagnostic.level == ERROR
                and diagnostic.code == "condicao-relacional-especifica"
                for diagnostic in diagnostics
            ), tag)


class InnateCastUsesTests(SimpleTestCase):
    """Rastreabilidade de conjuração inata: `cast{… without{slot} …}` precisa dizer
    QUANTAS vezes (at_will / uses{N, reset:R} / N/reset), senão a ficha não mete o uso."""

    def _codes(self, tags):
        return [d.code for d in _check_innate_casting_tags(tags)]

    def test_conjuracao_permanente_sem_limite_avisa(self):
        self.assertEqual(
            self._codes(["always_active{cast{spell:voo, modifiers{without{slot}}}}"]),
            ["innate-cast-uses"],
        )

    def test_at_will_satisfaz_o_limite(self):
        self.assertEqual(
            self._codes(["always_active{cast{spell:voo, modifiers{without{slot}, at_will}}}"]),
            [],
        )

    def test_uses_com_formula_entre_parenteses_satisfaz_o_limite(self):
        # `max(wis_mod,1)` tem vírgula DENTRO dos parênteses (Mapa Estelar, Clarão de
        # Guarda…): o N de uses{} é fórmula, não átomo.
        self.assertEqual(
            self._codes([
                "cast{ spell:raio-guiador, modifiers{ without{slot} } }",
                "uses{ max(wis_mod,1), reset:long_rest }",
            ]),
            [],
        )

    def test_uses_sem_reset_nao_conta_como_limite(self):
        self.assertEqual(
            self._codes([
                "cast{spell:voo, without{slot}}",
                "uses{ max(wis_mod,1) }",
            ]),
            ["innate-cast-uses"],
        )

    def test_cast_dentro_de_instant_e_efeito_roteirizado_e_nao_avisa(self):
        # Quem mede o uso é o gate da feature (trigger=/resource_cost:), não o cast.
        self.assertEqual(
            self._codes([
                "trigger=ability{magias_do_terreno, classe:druida}",
                "instant{ cast{ spell:comunhao-com-a-natureza, modifiers{ without{slot} } } }",
            ]),
            [],
        )

    def test_instant_na_linha_nao_isenta_cast_irmao_fora_dele(self):
        self.assertEqual(
            self._codes(["instant{ dmg:1d6 }, cast{ spell:voo, modifiers{ without{slot} } }"]),
            ["innate-cast-uses"],
        )

    def test_limite_generico_com_duas_magias_e_ambiguo(self):
        self.assertEqual(
            self._codes([
                "cast{spell:fome-de-umbral, without{slot}}",
                "cast{spell:manto-das-sombras, without{slot}}",
                "uses{1, reset:long_rest}",
            ]),
            ["innate-cast-ambiguous-uses"],
        )

    def test_uses_por_magia_desfaz_a_ambiguidade(self):
        self.assertEqual(
            self._codes([
                "cast{spell:fome-de-umbral, without{slot}, uses{1, reset:long_rest}}",
                "cast{spell:manto-das-sombras, without{slot}, uses{1, reset:long_rest}}",
            ]),
            [],
        )
