"""Atomically reverse the approved G01-D pilot catalog changes.

This closes pilot offers and restores retired subscription rewards. It keeps
acquired themes active and does not reverse MM redemptions or alter rights.
"""

import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Close pilot offers, retain acquired themes, and restore original reward states atomically.'

    def add_arguments(self, parser):
        parser.add_argument('--snapshot', required=True)
        parser.add_argument('--sha256', required=True)
        parser.add_argument('--confirm', required=True)

    def handle(self, *args, **options):
        if options['confirm'] != 'G01-D-ROLLBACK-PILOT':
            raise CommandError('Write requires --confirm G01-D-ROLLBACK-PILOT.')
        with transaction.atomic():
            pilot = StringIO()
            rewards = StringIO()
            call_command('reconcile_redesign_d_pilot', snapshot=options['snapshot'],
                         sha256=options['sha256'], action='archive', confirm='G01-D-PILOT',
                         stdout=pilot)
            call_command('reconcile_redesign_d_rewards', snapshot=options['snapshot'],
                         sha256=options['sha256'], action='restore', confirm='G01-D-REWARDS',
                         stdout=rewards)
            pilot_result = json.loads(pilot.getvalue())
            retained = pilot_result['retained_owned_slugs']
            result = {
                'archived_slugs': [slug for slug in pilot_result['changed_slugs']
                                   if slug not in retained],
                'retained_owned_slugs': retained,
                'restored_reward_ids': json.loads(rewards.getvalue())['changed_reward_ids'],
            }
        self.stdout.write(json.dumps(result, ensure_ascii=False))
