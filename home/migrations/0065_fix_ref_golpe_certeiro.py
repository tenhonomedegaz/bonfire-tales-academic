# -*- coding: utf-8 -*-
"""Bug B (colisão de nome): remove o card de MAGIA espúrio de 'Golpe Certeiro'.

Duas descrições de conteúdo trazem uma sub-habilidade chamada 'Golpe Certeiro'
(uma rerrolagem de dano do Brigão de Taverna; um ataque extra do capstone do
Caçador) que foi ERRONEAMENTE linkada à magia homônima `[...](tbMagia, golpe-certeiro)`
— um truque de ATAQUE que essas features NÃO concedem. No render, o markdown do site
(`normalizeMarkdown` em markdown.js) transforma a referência num card `data-table=tbMagia`
e o hover/clique puxa a descrição da MAGIA (bug do print).

A referência é EXPLÍCITA e sintaticamente igual às legítimas (talentos de Marca/Iniciado
que de fato concedem magias), então não há sinal automático que a distinga — a correção é
no DADO: desembrulha `[<rótulo>](tbMagia, golpe-certeiro)` de volta para o texto puro
`<rótulo>` (vira negrito comum, igual às sub-habilidades irmãs). Cirúrgico ao slug
`golpe-certeiro` (as duas ocorrências são espúrias; nenhuma feature concede o truque),
então NENHUM card legítimo de magia é afetado.

Idempotente: uma vez desembrulhada, o regex não casa mais. reverse = no-op (a referência
era um erro de conteúdo, não há estado a restaurar).
"""
import re

from django.db import migrations

# `[<qualquer rótulo>](tbMagia, golpe-certeiro)`  ->  `<rótulo>` (tolerante a espaços).
_REF_RX = re.compile(r'\[([^\]]+)\]\(\s*tbMagia\s*,\s*golpe-certeiro\s*\)', re.IGNORECASE)


def _unwrap(texto):
    return _REF_RX.sub(r'\1', texto) if texto else texto


def _fix_refs(apps, schema_editor):
    for modelo in ('TbTalento', 'TbClassehabilidade'):
        M = apps.get_model('home', modelo)
        for obj in M.objects.filter(descricao__contains='golpe-certeiro'):
            novo = _unwrap(obj.descricao or '')
            if novo != obj.descricao:
                obj.descricao = novo
                obj.save(update_fields=['descricao'])


def _reverse(apps, schema_editor):
    # sem reverso: a referência espúria era erro de conteúdo, não há estado a recuperar.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0064_personagem_item_concessao'),
    ]

    operations = [
        migrations.RunPython(_fix_refs, _reverse),
    ]
