import json
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from home.hunter_catalog import compose_choice_revision, compose_order_revision
from home.models import TbRuleset


class Command(BaseCommand):
    help = 'Compose mapped Hunter choices, passives, conditional features and Secrets; dry-run by default, never activates characters.'

    def add_arguments(self, parser):
        parser.add_argument('--ruleset', required=True, type=int)
        parser.add_argument('--class-id', required=True, type=int)
        parser.add_argument('--preparation-id', required=True, type=int)
        parser.add_argument('--expertise-id', required=True, type=int)
        parser.add_argument('--passive-ids', help='JSON object mapping all five passive keys to reviewed feature IDs.')
        parser.add_argument('--secrets-ids', help='JSON object with reviewed feature, points and known IDs.')
        parser.add_argument('--conditional-ids', help='JSON mapping favored, territory, predator, hide, domination and favored_resource IDs.')
        parser.add_argument('--spellcasting-ids', help='JSON with feature ID and five slot resource IDs ordered by circle.')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--mark-feature-id', type=int)
        parser.add_argument('--order-ids', help='JSON mapping the eight reference Order slugs to reviewed new subclass IDs.')

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                result = compose_choice_revision(TbRuleset.objects.get(pk=options['ruleset']),
                    class_id=options['class_id'], feature_ids={
                        'preparation': options['preparation_id'], 'expertise': options['expertise_id']},
                    passive_ids=json.loads(options['passive_ids']) if options.get('passive_ids') else None,
                    secrets_ids=json.loads(options['secrets_ids']) if options.get('secrets_ids') else None,
                    conditional_ids=json.loads(options['conditional_ids']) if options.get('conditional_ids') else None,
                    spellcasting_ids=json.loads(options['spellcasting_ids']) if options.get('spellcasting_ids') else None,
                    mark_feature_id=options.get('mark_feature_id'))
                if options.get('order_ids'):
                    result = compose_order_revision(result, class_id=options['class_id'],
                        order_ids=json.loads(options['order_ids']))
                output = {'checksum': result.checksum, 'persisted': options['apply'],
                          'ruleset': result.pk if options['apply'] else None,
                          'activated': False, 'scope': ('choices-and-base-passives' if options.get('passive_ids')
                                                       else 'preparation-and-expertise-only')}
                output['secrets_replaced'] = bool(options.get('secrets_ids'))
                output['conditionals_replaced'] = bool(options.get('conditional_ids'))
                output['spellcasting_replaced'] = bool(options.get('spellcasting_ids'))
                output['orders_composed'] = bool(options.get('order_ids'))
                if not options['apply']:
                    transaction.set_rollback(True)
        except (ObjectDoesNotExist, ValueError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(output, sort_keys=True))
