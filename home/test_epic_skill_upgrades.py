"""Existing skill sources determine an epic talent's proficiency upgrade."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from home.character_engine import derive
from home.picks import resolve_personagem
from home.epic_talent_catalog import ATTRIBUTE_TAGS, PARTIAL_EFFECTS, epic_candidates
from home.models import (TbPersonagem, TbPersonagemEscolha, TbPersonagemPericia,
                         TbPersonagemTalento, TbTalento)
from home.tag_engine.library import Library
from home.tag_engine.validator import ERROR, validate_tags_json


CASES = (
    ("dadiva-da-memoria-arcana", "Arcanismo"),
    ("dadiva-da-folia", "Atuação"),
    ("dadiva-do-horror", "Intimidação"),
)


class EpicSkillUpgradeTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="epic-skill-upgrade")
        self.character = TbPersonagem.objects.create(dono=owner, nome="Skills")

    def skill(self, name):
        return next(row for row in derive(self.character)["pericias"]
                    if row["nome"] == name)

    def grant(self, slug, *, choice="talent_attr:INT"):
        ready = {row["slug"]: row for row in epic_candidates()}
        tags = (ready[slug]["tags_json"] if slug in ready
                else ATTRIBUTE_TAGS + PARTIAL_EFFECTS[slug])
        talent = TbTalento.objects.create(
            nome=slug, slug=slug, tipo="geral", etiquetas_adicionais="epico",
            tags_json=tags,
        )
        owned = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=talent, categoria="epico",
            nome=talent.nome, detalhes=choice,
        )
        return owned

    def test_no_prior_proficiency_then_external_proficiency_and_removal(self):
        for slug, name in CASES:
            with self.subTest(slug=slug):
                owned = self.grant(slug)
                first = self.skill(name)
                self.assertTrue(first["proficiente"])
                self.assertFalse(first["expertise"])

                other = TbTalento.objects.create(
                    nome="Fonte externa " + slug, slug="external-" + slug,
                    tags_json=["prof:" + {
                        "Arcanismo": "arcanismo", "Atuação": "atuacao",
                        "Intimidação": "intimidacao",
                    }[name]],
                )
                external = TbPersonagemTalento.objects.create(
                    id_personagem=self.character, id_talento=other,
                    nome=other.nome,
                )
                for _ in range(2):
                    self.assertTrue(self.skill(name)["expertise"])
                external.delete()
                self.assertFalse(self.skill(name)["expertise"])
                owned.delete()
                self.assertFalse(self.skill(name)["proficiente"])

    def test_prior_proficiency_promotes_without_duplicating_other_skills(self):
        TbPersonagemPericia.objects.create(
            id_personagem=self.character, nome="Arcanismo", atributo="INT",
            proficiente=True,
        )
        owned = self.grant("dadiva-da-memoria-arcana")
        self.assertTrue(self.skill("Arcanismo")["expertise"])
        self.assertFalse(self.skill("Atuação")["expertise"])
        owned.detalhes = ""
        owned.save(update_fields=["detalhes"])
        self.assertFalse(self.skill("Arcanismo")["expertise"])
        owned.delete()
        self.assertTrue(self.skill("Arcanismo")["proficiente"])

    def test_existing_expertise_opens_validated_alternative_and_removal_disables_it(self):
        from home.views import _lvl_aplicar_opcao, _opcoes_ficha

        for slug, name in CASES[:2]:
            with self.subTest(slug=slug):
                TbPersonagemPericia.objects.create(
                    id_personagem=self.character, nome=name,
                    proficiente=True, expertise=True,
                )
                TbPersonagemPericia.objects.create(
                    id_personagem=self.character, nome="Atletismo", proficiente=True,
                )
                owned = self.grant(slug)
                groups = [g for g in resolve_personagem(self.character)
                          if g['kind'] == 'pericia_expertise'
                          and g['origem'] == owned.nome]
                self.assertEqual(len(groups), 1)
                group = groups[0]
                self.assertIn("atletismo", {row['slug'] for row in group['universo']})
                self.assertNotIn("arcanismo", {row['slug'] for row in group['universo']}
                                 if name == "Arcanismo" else set())
                self.assertTrue(_lvl_aplicar_opcao(self.character, {
                    'slug': 'pericia_expertise', 'val': 'religiao', 'classe': '',
                }))
                self.assertFalse(self.skill("Religião")["expertise"])
                self.assertEqual(_lvl_aplicar_opcao(self.character, {
                    'slug': 'pericia_expertise', 'val': 'atletismo', 'classe': '',
                }), [])
                self.assertTrue(self.skill("Atletismo")["expertise"])
                self.assertTrue(self.skill(name)["expertise"])
                selected = [g for g in resolve_personagem(self.character)
                            if g['kind'] == 'pericia_expertise'
                            and g['origem'] == owned.nome]
                self.assertEqual(len(selected), 1)
                self.assertEqual([row['valor'] for row in selected[0]['escolhidas']],
                                 ['atletismo'])
                card = next(row for row in _opcoes_ficha(self.character)
                            if row['origem'] == owned.nome
                            and row['kind'] == 'pericia_expertise')
                self.assertEqual(card['escolhidas'][0]['valor'], 'atletismo')
                owned.detalhes = ''
                owned.save(update_fields=['detalhes'])
                self.assertFalse(self.skill("Atletismo")["expertise"])
                self.assertFalse(any(g['kind'] == 'pericia_expertise'
                                     and g['origem'] == owned.nome
                                     for g in resolve_personagem(self.character)))
                owned.detalhes = 'talent_attr:INT'
                owned.save(update_fields=['detalhes'])
                self.assertTrue(self.skill("Atletismo")["expertise"])
                original_tags = list(owned.id_talento.tags_json)
                owned.id_talento.tags_json = [tag for tag in original_tags
                                                if 'pick:pericia_expertise:' not in tag]
                owned.id_talento.save(update_fields=['tags_json'])
                self.assertFalse(self.skill("Atletismo")["expertise"])
                owned.id_talento.tags_json = original_tags
                owned.id_talento.save(update_fields=['tags_json'])
                self.assertTrue(self.skill("Atletismo")["expertise"])
                owned.delete()
                self.assertFalse(self.skill("Atletismo")["expertise"])
                self.assertTrue(self.skill(name)["expertise"])
                TbPersonagemPericia.objects.filter(id_personagem=self.character).delete()
        self.assertEqual(TbPersonagemEscolha.objects.filter(
            id_personagem=self.character, tipo='pericia_expertise').count(), 2)

    def test_horror_existing_expertise_does_not_grant_another_skill(self):
        TbPersonagemPericia.objects.create(
            id_personagem=self.character, nome='Intimidação',
            proficiente=True, expertise=True,
        )
        owned = self.grant('dadiva-do-horror')
        self.assertFalse(any(
            group['kind'] == 'pericia_expertise' and group['origem'] == owned.nome
            for group in resolve_personagem(self.character)))

    def test_alternative_requires_prior_expertise_and_attribute_choice(self):
        owned = self.grant("dadiva-da-memoria-arcana")
        self.assertFalse(any(g['kind'] == 'pericia_expertise'
                             for g in resolve_personagem(self.character)))
        TbPersonagemPericia.objects.create(
            id_personagem=self.character, nome="Arcanismo",
            proficiente=True, expertise=True,
        )
        TbPersonagemPericia.objects.create(
            id_personagem=self.character, nome="Atletismo", proficiente=True,
        )
        owned.detalhes = ''
        owned.save(update_fields=['detalhes'])
        self.assertFalse(any(g['kind'] == 'pericia_expertise'
                             for g in resolve_personagem(self.character)))
        owned.detalhes = 'talent_attr:INT'
        owned.save(update_fields=['detalhes'])
        self.assertEqual(sum(g['kind'] == 'pericia_expertise'
                             for g in resolve_personagem(self.character)), 1)

    def test_expertise_tag_from_another_source_opens_alternative(self):
        owned = self.grant('dadiva-da-memoria-arcana')
        source = TbTalento.objects.create(
            nome='Aptidão anterior', slug='aptidao-anterior', tipo='geral',
            tags_json=['expertise:arcanismo', 'prof:atletismo'],
        )
        external = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=source, nome=source.nome,
        )
        self.assertEqual(sum(g['kind'] == 'pericia_expertise'
                             for g in resolve_personagem(self.character)), 1)
        external.delete()
        self.assertFalse(any(g['kind'] == 'pericia_expertise'
                             for g in resolve_personagem(self.character)))
        owned.delete()

    def test_original_proficiency_expertise_from_other_source_opens_alternative(self):
        TbPersonagemPericia.objects.create(
            id_personagem=self.character, nome='Arcanismo', proficiente=True,
        )
        TbPersonagemPericia.objects.create(
            id_personagem=self.character, nome='Atletismo', proficiente=True,
        )
        owned = self.grant('dadiva-da-memoria-arcana')
        source = TbTalento.objects.create(
            nome='Aptidão de origem', slug='aptidao-de-origem', tipo='geral',
            tags_json=['expertise:original_prof'],
        )
        external = TbPersonagemTalento.objects.create(
            id_personagem=self.character, id_talento=source, nome=source.nome,
        )
        self.assertTrue(any(g['kind'] == 'pericia_expertise'
                            for g in resolve_personagem(self.character)))
        external.delete()
        self.assertFalse(any(g['kind'] == 'pericia_expertise'
                             for g in resolve_personagem(self.character)))
        owned.delete()

    def test_horror_fear_immunity_follows_source_and_attribute_choice(self):
        owned = self.grant("dadiva-do-horror", choice="")
        self.assertFalse(self.skill("Intimidação")["proficiente"])
        self.assertNotIn("Amedrontado (condição)", derive(self.character)["imunidades"])
        owned.detalhes = "talent_attr:CAR"
        owned.save(update_fields=["detalhes"])
        self.assertIn("Amedrontado (condição)", derive(self.character)["imunidades"])
        owned.delete()
        self.assertNotIn("Amedrontado (condição)", derive(self.character)["imunidades"])

    def test_skill_tags_validate_and_complete_candidates_are_importable(self):
        ready = {row["slug"]: row for row in epic_candidates()}
        for slug, _ in CASES:
            if slug in {"dadiva-da-memoria-arcana", "dadiva-do-horror"}:
                self.assertIn(slug, ready)
            else:
                self.assertNotIn(slug, ready)
            tags = (ready[slug]["tags_json"] if slug in ready
                    else ATTRIBUTE_TAGS + PARTIAL_EFFECTS[slug])
            diagnostics = validate_tags_json(tags, Library())
            self.assertEqual([d for d in diagnostics if d.level == ERROR], [], slug)
