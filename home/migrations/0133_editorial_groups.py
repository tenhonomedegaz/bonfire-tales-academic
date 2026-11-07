"""Create assignable editorial cargos without enrolling any accounts."""

from django.db import migrations


ROLE_PERMISSIONS = {
    'Jornalista': (('tbjornal', 'add_tbjornal'), ('tbjornal', 'change_tbjornal')),
    'Staff': (('tbcronica', 'triage_tbcronica'),),
    'Loremaster': (('tbcronica', 'change_tbcronica'),),
}


def create_editorial_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    alias = schema_editor.connection.alias

    for name, permission_specs in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.using(alias).get_or_create(name=name)
        for model, codename in permission_specs:
            content_type, _ = ContentType.objects.using(alias).get_or_create(
                app_label='home', model=model,
            )
            permission, _ = Permission.objects.using(alias).get_or_create(
                content_type=content_type, codename=codename,
                defaults={'name': f'Can {codename.replace("_", " ")}'},
            )
            group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0132_social_credit_publication_policy'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(create_editorial_groups, reverse_code=migrations.RunPython.noop),
    ]
