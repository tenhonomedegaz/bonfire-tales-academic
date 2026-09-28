"""Provision additive identities for the eight reviewed Hunter Orders."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils.text import slugify

from home.models import TbClasse, TbSubclasse


class Command(BaseCommand):
    help = 'Inspect or add eight new Hunter Order identities; never changes legacy rows.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('PostgreSQL is required.')
        reference = json.loads((Path(__file__).resolve().parents[2] /
            'rules/hunter_content.json').read_text(encoding='utf-8'))
        names = {slugify(name): name for name in reference['orders']}
        if len(names) != 8:
            raise CommandError('The reviewed Hunter reference must contain eight distinct Orders.')
        with transaction.atomic():
            classe = TbClasse.objects.select_for_update().get(slug='cacador')
            found = {}
            created = 0
            for slug, name in names.items():
                technical_slug = slug + '-rework'
                existing = TbSubclasse.objects.filter(slug=technical_slug).first()
                if existing and (existing.id_classe_id != classe.pk or existing.nome != name):
                    raise CommandError('Conflicting Order identity: %s' % technical_slug)
                if existing is None and options['apply']:
                    existing = TbSubclasse.objects.create(id_classe=classe,
                        nome=name, slug=technical_slug, tagline=None)
                    created += 1
                found[slug] = existing.pk if existing else None
        self.stdout.write(json.dumps({'applied': options['apply'], 'class_id': classe.pk,
            'order_ids': found, 'created': created},
            ensure_ascii=False, sort_keys=True))
