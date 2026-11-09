"""Level-up carries complete source text to the shared safe Markdown reader."""
from .models import TbClassehabilidade
from .test_criador import _CriadorBase
from . import test_levelup_multiclass_flow as multiclass_flow


class LevelupPresentationTests(_CriadorBase):
    setUp = multiclass_flow.MulticlassFlowTests.setUp

    def test_complete_markdown_is_escaped_and_not_truncated_in_target_features(self):
        description = '**Regra completa**\n\n- Primeiro ponto\n- Segundo ponto\n\n'
        description += 'Texto extenso. ' * 60 + 'FINAL_DA_REGRA'
        description += '<img src="x" onerror="alert(1)">'
        TbClassehabilidade.objects.create(
            id_classe=self.fighter, nome='Apresentacao de teste',
            niveladquirido=4, descricao=description, tags_json=[])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sn-choice-description" data-markdown-source')
        self.assertContains(response, 'FINAL_DA_REGRA')
        self.assertContains(response, '**Regra completa**')
        self.assertContains(response, '&lt;img src=&quot;x&quot; onerror=&quot;alert(1)&quot;&gt;')
        self.assertNotContains(response, '<img src="x" onerror="alert(1)">')
