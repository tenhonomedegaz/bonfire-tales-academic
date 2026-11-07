import getpass
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cria ou atualiza um superusuario para recuperar acesso ao admin."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("BONFIRE_ADMIN_USERNAME", "admin"))
        parser.add_argument("--email", default=os.environ.get("BONFIRE_ADMIN_EMAIL", "admin@bonfire.local"))
        parser.add_argument("--password", default=os.environ.get("BONFIRE_ADMIN_PASSWORD", ""))
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Nao pergunta senha interativamente; exige --password ou BONFIRE_ADMIN_PASSWORD.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        email = options["email"].strip()
        password = options["password"]

        if not username:
            raise CommandError("Username vazio.")

        if not password and options["noinput"]:
            raise CommandError("Informe --password ou BONFIRE_ADMIN_PASSWORD.")

        if not password:
            password = getpass.getpass("Senha do admin: ")
            confirm = getpass.getpass("Confirme a senha: ")
            if password != confirm:
                raise CommandError("As senhas nao conferem.")

        if not password:
            raise CommandError("Senha vazia.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True, "is_active": True},
        )
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = "criado" if created else "atualizado"
        self.stdout.write(self.style.SUCCESS(f"Superusuario {username!r} {action}."))
