# -*- coding: utf-8 -*-
"""LINT PERMANENTE de templates: comentário Django `{# ... #}` NÃO suporta múltiplas linhas —
o `{#` e o `#}` precisam estar na MESMA linha. Um comentário `{#` cujo `#}` cai numa linha
seguinte NÃO é reconhecido como comentário: o texto VAZA cru na página (bug reportado no passo
'Visão geral' de subir_nivel.html). Este teste varre TODOS os `.html` de home/templates e falha
listando `arquivo:linha` de cada `{#` sem `#}` na mesma linha. Para comentário de várias linhas
use `{% comment %}...{% endcomment %}`."""
import os

from django.test import SimpleTestCase

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


def _comentarios_multilinha(path):
    """Devolve [(linha_1based, trecho)] de cada `{#` cujo fechamento `#}` NÃO está na mesma
    linha. Trata múltiplos comentários por linha (`{# a #} {# b #}`) e ignora `#}` órfão (a
    linha de FECHAMENTO de um comentário quebrado não gera achado novo — o achado é o `{#`
    de abertura)."""
    achados = []
    with open(path, encoding='utf-8') as fh:
        for n, linha in enumerate(fh, start=1):
            idx = 0
            while True:
                abre = linha.find('{#', idx)
                if abre == -1:
                    break
                fecha = linha.find('#}', abre + 2)
                if fecha == -1:
                    achados.append((n, linha.rstrip()[:80]))
                    break
                idx = fecha + 2
    return achados


class TemplateCommentLintTests(SimpleTestCase):
    def test_sem_comentario_django_multilinha(self):
        violacoes = []
        for raiz, _dirs, arquivos in os.walk(_TEMPLATES_DIR):
            for nome in arquivos:
                if not nome.endswith('.html'):
                    continue
                caminho = os.path.join(raiz, nome)
                for linha, trecho in _comentarios_multilinha(caminho):
                    rel = os.path.relpath(caminho, os.path.dirname(_TEMPLATES_DIR))
                    violacoes.append('%s:%d  %s' % (rel.replace('\\', '/'), linha, trecho))
        self.assertEqual(
            violacoes, [],
            'Comentário Django `{# #}` multilinha (não suportado — vaza cru). '
            'Use uma única linha ou `{%% comment %%}`:\n' + '\n'.join(violacoes))
