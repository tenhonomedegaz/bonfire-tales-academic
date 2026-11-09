"""Lineage presentation exposes actual starting traits, not its lore as a skill."""
from .models import TbLinhagem, TbTracoracial
from .test_criador import _CriadorBase
from .views import _criador_catalogos


class CreatorLineageTraitsTests(_CriadorBase):
    def test_lunareth_exposes_only_its_starting_non_talent_traits(self):
        lineage = TbLinhagem.objects.get(slug='lunareth')
        trait = TbTracoracial.objects.get(id_linhagem=lineage, nome='Bruma Serenante')
        trait.descricao += '\n\n**Regra completa** ' + 'Texto. ' * 70 + 'FINAL_DO_TRACO'
        trait.save(update_fields=['descricao'])
        for name, level, talent in [('Later trait', 5, False), ('Racial talent', 1, True)]:
            TbTracoracial.objects.create(id_linhagem=lineage, nome=name,
                descricao='Not a starting trait', nivel_requisito=level,
                talento_racial=talent, tags_json=[])
        catalog = _criador_catalogos()
        race = next(r for r in catalog['racas'] if r['slug'] == 'elfo')
        entry = next(l for l in race['linhagens'] if l['slug'] == 'lunareth')
        self.assertEqual({t['nome'] for t in entry['tracos']},
                         {'Sinal Lunar', 'Bruma Serenante', 'Sopro Selênico'})
        self.assertTrue(entry['desc'])
        self.assertTrue(race['tracos'])
        self.assertFalse(any(t['nome'].startswith('Linhagem:') for t in entry['tracos']))
        self.assertTrue(all(t['desc'] for t in entry['tracos']))
        self.assertTrue(next(t for t in entry['tracos'] if t['nome'] == 'Bruma Serenante')['desc'].endswith('FINAL_DO_TRACO'))
