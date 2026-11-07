"""Preview or assign the editorial permissions approved for named accounts."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


ROLE_PERMISSIONS = {
    'journalist': ('add_tbjornal', 'change_tbjornal'),
    'staff': ('triage_tbcronica',),
    'loremaster': ('change_tbcronica',),
}


class Command(BaseCommand):
    help = ('Preview editorial permission grants for existing is_staff accounts; '
            'use --apply after the PO names the accounts.')

    def add_arguments(self, parser):
        for role in ROLE_PERMISSIONS:
            parser.add_argument(f'--{role}', action='append', default=[], metavar='USERNAME',
                                help=f'Account to grant the {role} editorial permissions (repeatable).')
        parser.add_argument('--apply', action='store_true',
                            help='Persist the grants after validating all named accounts.')

    def handle(self, *args, **options):
        assignments = {
            role: sorted(set(options[role])) for role in ROLE_PERMISSIONS if options[role]
        }
        if not assignments:
            raise CommandError('Specify at least one --journalist, --staff or --loremaster account.')

        usernames = {name for names in assignments.values() for name in names}
        user_model = get_user_model()
        users = user_model.objects.in_bulk(usernames, field_name=user_model.USERNAME_FIELD)
        missing = usernames - users.keys()
        if missing:
            raise CommandError('Unknown account(s): ' + ', '.join(sorted(missing)))
        inactive = {name for name, user in users.items() if not user.is_active}
        if inactive:
            raise CommandError('Inactive account(s): ' + ', '.join(sorted(inactive)))
        nonstaff = {name for name, user in users.items() if not user.is_staff}
        if nonstaff:
            raise CommandError('Accounts without is_staff: ' + ', '.join(sorted(nonstaff)))

        codes = {code for role in assignments for code in ROLE_PERMISSIONS[role]}
        permissions = {
            permission.codename: permission for permission in Permission.objects.filter(
                content_type__app_label='home', codename__in=codes,
            )
        }
        if codes - permissions.keys():
            raise CommandError('Missing permission(s): ' + ', '.join(sorted(codes - permissions.keys())))

        grants = {}
        for role, names in assignments.items():
            for name in names:
                grants.setdefault(name, set()).update(ROLE_PERMISSIONS[role])

        for name, requested in sorted(grants.items()):
            self.stdout.write(f'{name}: {", ".join(sorted(requested))}')
        if not options['apply']:
            self.stdout.write('Preview only; no permissions changed.')
            return

        with transaction.atomic():
            for name, requested in sorted(grants.items()):
                users[name].user_permissions.add(*(permissions[code] for code in sorted(requested)))
        self.stdout.write(self.style.SUCCESS('Editorial permissions assigned.'))
