"""Reconstrói fatos de publicações antigas com aprovação comprovada."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from home.conquistas import registrar_publicacao_cronica
from home.models import TbCronica, TbEventoConquista, TbUsuarioConquista


class Command(BaseCommand):
    help = ('Prévia por padrão; --apply registra fatos de Crônicas aprovadas com '
            'publicação e revisão identificadas, e reavalia a primeira publicação.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user-id', type=int)

    def handle(self, *args, **options):
        users = get_user_model().objects.filter(
            pk__in=TbCronica.objects.filter(status='aprovada').values('autor_id')
        ).order_by('pk')
        if options['user_id'] is not None:
            users = users.filter(pk=options['user_id'])
        counts = {'contas': 0, 'fatos_novos': 0, 'concessoes_novas': 0,
                  'sem_prova': 0, 'inconsistentes': 0}
        for user in users.iterator():
            with transaction.atomic():
                get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
                counts['contas'] += 1
                stories = TbCronica.objects.filter(
                    autor=user, status='aprovada', data_publicacao__isnull=False
                ).order_by('data_publicacao', 'pk')
                for story in stories.iterator():
                    key = f'cronica:{story.pk}:publicada'
                    existing = TbEventoConquista.objects.filter(
                        origem='site', chave_origem=key).first()
                    if (existing is None and
                            (story.revisado_por_id is None or story.data_revisao is None or
                             story.data_revisao > story.data_publicacao)):
                        counts['sem_prova'] += 1
                        continue
                    before = TbUsuarioConquista.objects.filter(
                        user=user, conquista__criterio_json__metric='stories_published',
                        revogada_em__isnull=True).count()
                    try:
                        with transaction.atomic():
                            registrar_publicacao_cronica(story)
                    except ValueError:
                        counts['inconsistentes'] += 1
                        continue
                    counts['fatos_novos'] += int(existing is None)
                    after = TbUsuarioConquista.objects.filter(
                        user=user, conquista__criterio_json__metric='stories_published',
                        revogada_em__isnull=True).count()
                    counts['concessoes_novas'] += after - before
                if not options['apply']:
                    transaction.set_rollback(True)
        self.stdout.write('%s: %s' % (
            'aplicado' if options['apply'] else 'prévia',
            ' '.join(f'{key}={value}' for key, value in counts.items())))
