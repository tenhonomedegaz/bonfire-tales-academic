"""Define as taglines canônicas das raças (exibidas no topo da página de raça).

As raças importadas vêm com `tagline` vazia; o cabeçalho da página passou a
exibir apenas a tagline (o texto longo de apresentação foi movido para a aba
Lore). Este comando preenche as taglines de forma idempotente.

Uso:
    python manage.py set_race_taglines          # só preenche taglines vazias
    python manage.py set_race_taglines --force   # sobrescreve todas

Observação: a tagline do Anão é a definida pelo product owner. As demais são
rascunhos no mesmo tom, sujeitos a revisão.
"""

from django.core.management.base import BaseCommand

from home.models import TbRaca

# slug -> tagline canônica
TAGLINES = {
    'anao': (
        "Não medimos o tempo pelo sol que nem sempre vemos. "
        "Medimos pela espessura da rocha que já temos atrás de nós."
    ),
    # Rascunhos (revisar com o PO):
    'elfo': (
        "Contamos as eras pelas luas que restaram — e por aquela que se apagou. "
        "Nossa graça é a saudade de um mundo que já foi inteiro."
    ),
    'humano': (
        "Vivemos depressa porque vivemos pouco; ainda assim, não há costa, "
        "fronteira ou trono onde já não tenhamos deixado nosso nome."
    ),
    'orc': (
        "Não rezamos a deuses: caminhamos com os espíritos dos que vieram antes. "
        "Quem enfrenta um de nós, enfrenta toda a linhagem."
    ),
}


class Command(BaseCommand):
    help = "Preenche as taglines canônicas das raças (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Sobrescreve a tagline mesmo que já exista.',
        )

    def handle(self, *args, **options):
        force = options['force']
        updated = skipped = missing = 0

        for slug, tagline in TAGLINES.items():
            raca = TbRaca.objects.filter(slug=slug).first()
            if raca is None:
                self.stdout.write(self.style.WARNING(f'  raça "{slug}" não encontrada — pulando'))
                missing += 1
                continue

            if raca.tagline and not force:
                self.stdout.write(f'  {raca.nome}: já possui tagline — mantida')
                skipped += 1
                continue

            raca.tagline = tagline
            raca.save(update_fields=['tagline'])
            self.stdout.write(self.style.SUCCESS(f'  {raca.nome}: tagline definida'))
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Concluído. Atualizadas: {updated} | mantidas: {skipped} | ausentes: {missing}'
            )
        )
