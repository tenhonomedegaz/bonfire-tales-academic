# -*- coding: utf-8 -*-
"""Reseta todas as sequências auto-incrementais do PostgreSQL para a app 'home'.

Isso evita erros de integridade (duplicate key value violates unique constraint)
após inserções de fixtures de dados explícitos.
"""
from django.db import migrations


def reset_postgresql_sequences(apps, schema_editor):
    from django.db import transaction
    connection = schema_editor.connection
    if connection.vendor == 'postgresql':
        from io import StringIO
        from django.core.management import call_command
        buf = StringIO()
        try:
            # A migration externa já é atômica. O savepoint interno garante
            # rollback do SQL opcional antes de ignorar uma incompatibilidade;
            # sem ele, capturar a exceção deixa toda a transação PostgreSQL
            # abortada e impede o Django de registrar esta migration.
            with transaction.atomic(using=connection.alias):
                call_command("sqlsequencereset", "home", stdout=buf)
                sql = buf.getvalue().strip()
                if sql:
                    with connection.cursor() as cur:
                        cur.execute(sql)
        except Exception:
            pass


def _backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0053_fix_badge_emoji_icons'),
    ]

    operations = [
        migrations.RunPython(reset_postgresql_sequences, _backward),
    ]
