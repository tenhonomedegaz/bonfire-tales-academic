# -*- coding: utf-8 -*-
"""Conserta a velocidade INFLADA na prod (bug de realimentação não-idempotente).

Antes do fix, `_refresh_vitais_derivados` (home/views.py) gravava a velocidade
JÁ DERIVADA (base + bônus de tags) de volta em `TbPersonagem.velocidade`, que o
derive tratava como BASE — cada refresh (subir de nível, editar ficha, etc.)
re-somava os bônus e a base inflava: 30 -> 50 -> 70 ... ft (havia personagens
com 120 ft armazenados). O fix de código torna `velocidade` a BASE imutável e
para de persistir a derivada; esta migração REPARA os dados já corrompidos,
resetando a base para a MESMA SEMENTE usada na criação.

Regra de criação espelhada: `_criador_persistir` cria o TbPersonagem SEM setar
velocidade, então o valor-semente é o DEFAULT do campo (`'9 m / 30 ft'`) — não há
velocidade por raça. Lemos o default do próprio campo (estado histórico) para
manter fidelidade; fallback constante por segurança.

Idempotente: `update(...)` fixa todos para a mesma semente — rodar de novo não
muda nada. reverse = no-op (a base inflada era lixo, não há o que restaurar).
"""
from django.db import migrations

SEED_FALLBACK = '9 m / 30 ft'


def _reset_velocidade(apps, schema_editor):
    TbPersonagem = apps.get_model('home', 'TbPersonagem')
    try:
        seed = TbPersonagem._meta.get_field('velocidade').default or SEED_FALLBACK
    except Exception:
        seed = SEED_FALLBACK
    # Reseta TODOS para a semente de criação (idempotente). Qualquer valor diferente
    # da semente só existe por causa da realimentação — não há override manual (a
    # única escrita de velocidade era o _refresh_vitais_derivados, agora corrigido).
    TbPersonagem.objects.exclude(velocidade=seed).update(velocidade=seed)


def _reverse(apps, schema_editor):
    # sem reverso: a base inflada era resultado de bug, não há estado a recuperar.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0060_alter_tbmapdesenho_dados_json'),
    ]

    operations = [
        migrations.RunPython(_reset_velocidade, _reverse),
    ]
