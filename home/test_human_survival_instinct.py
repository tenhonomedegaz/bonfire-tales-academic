"""An absent racial option may be an intentional lineage prerequisite."""
from .models import TbEssencia, TbLinhagem, TbPersonagem, TbRaca, TbTracoracial
from .test_criador import _CriadorBase
from .views import _criador_catalogos, _pendencias_talento_racial, _talentos_raciais_criador


class HumanSurvivalInstinctTests(_CriadorBase):
    def test_human_lineage_offers_instinct_but_essence_does_not_replace_its_requirement(self):
        human = TbRaca.objects.get(slug='humano')
        lineage = TbLinhagem.objects.filter(id_raca=human).order_by('pk').first()
        essence = TbEssencia.objects.get(slug='nephilim')
        trait = TbTracoracial.objects.get(nome='Instinto de Sobrevivência')
        self.assertIn('character_prereq:any{lineage:*}', trait.tags_json)
        self.assertIn(trait, _talentos_raciais_criador(human, lineage))
        self.assertNotIn(trait, _talentos_raciais_criador(human, essencia=essence))
        catalog = _criador_catalogos()
        metadata = next(t for t in catalog['talentos_raca']['humano'] if t['nome_chave'] == trait.nome)
        self.assertIn(lineage.slug, metadata['linhagens'])
        self.assertFalse(metadata['aceita_essencia'])
        person = TbPersonagem.objects.create(nome='Human eligibility', nivel=5,
                                             dono=self._novo_usuario('human-eligibility'),
                                             id_raca=human, id_linhagem=lineage)
        def offered():
            return {option['nome'] for block in _pendencias_talento_racial(person)
                    for option in block['opcoes']}
        self.assertIn(trait.nome, offered())
        person.id_linhagem = None
        person.id_essencia = essence
        person.save(update_fields=['id_linhagem', 'id_essencia'])
        self.assertNotIn(trait.nome, offered())
