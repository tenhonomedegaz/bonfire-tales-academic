from django.db import migrations, models


CONTEUDOS_INICIAIS = [
    {
        'chave': 'home-hero',
        'pagina': 'home',
        'titulo': 'Bonfire Tales',
        'subtitulo': (
            'RPG contínuo de fantasia sombria, jogado por voz no Discord e apoiado '
            'por ferramentas próprias para criar personagens, encontrar missões e '
            'acompanhar um mundo que muda com as mesas.'
        ),
        'cta_texto': 'Entrar no Discord',
        'cta_url': 'https://discord.gg/eyqe7rj2AX',
        'ordem': 10,
    },
    {
        'chave': 'home-jornada',
        'pagina': 'home',
        'titulo': 'Comece a jogar',
        'subtitulo': 'Da conta à primeira missão, o fluxo acontece pelo site e pelo Discord.',
        'conteudo_markdown': (
            '1. **Crie sua conta** e vincule seu Discord para o site reconhecer você nas missões.\n'
            '2. **Monte a ficha** no criador, escolhendo raça, classe, antecedente e talentos.\n'
            '3. **Procure uma missão** publicada e abra o anúncio original no Discord para participar.\n'
            '4. **Registre a aventura** com a equipe e acompanhe progressão, inventário e próximos níveis na ficha.'
        ),
        'cta_texto': 'Criar conta',
        'cta_url': '/cadastro/',
        'ordem': 20,
    },
    {
        'chave': 'home-atlas',
        'pagina': 'home',
        'titulo': 'Atlas interativo de Cinéria',
        'subtitulo': (
            'Abra o mapa, alterne entre as camadas liberadas e selecione marcadores '
            'para conhecer territórios, regiões e pontos de interesse. As páginas de '
            'lore ficam ligadas ao atlas e às crônicas da comunidade.'
        ),
        'cta_texto': 'Explorar o mapa',
        'cta_url': '/mapa/',
        'ordem': 30,
    },
    {
        'chave': 'home-apoio',
        'pagina': 'home',
        'titulo': 'Mantenha a chama acesa',
        'subtitulo': (
            'Jogar é gratuito. Quem colabora ajuda a manter o servidor, o bot e o '
            'site, e recebe os benefícios descritos na página de colaboração, como '
            'preferência em filas elegíveis, tokens e cosméticos conforme o pacote.'
        ),
        'cta_texto': 'Conhecer benefícios',
        'cta_url': '/colaborador/',
        'ordem': 40,
    },
    {
        'chave': 'sobre-projeto',
        'pagina': 'sobre',
        'titulo': 'Sobre o Bonfire Tales',
        'subtitulo': (
            'O Bonfire Tales é uma comunidade brasileira de RPG contínuo, com mesas '
            'organizadas no formato West Marches e um cenário compartilhado chamado Cinéria.'
        ),
        'conteudo_markdown': (
            'O site reúne as regras usadas pela comunidade, o criador e as fichas de '
            'personagem, os catálogos de jogo, o calendário de missões e a wiki do mundo. '
            'As decisões tomadas nas aventuras podem se tornar crônicas, alterar regiões '
            'e alimentar novas histórias.\n\n'
            'O conteúdo de cenário é produzido e revisado pela equipe do Bonfire Tales. '
            'As referências de sistema são organizadas para uso das mesas e identificadas '
            'como conteúdo de RPG, sem sugerir vínculo oficial com outras editoras.'
        ),
        'ordem': 10,
    },
    {
        'chave': 'contato-principal',
        'pagina': 'contato',
        'titulo': 'Fale com a equipe',
        'subtitulo': (
            'Suporte de conta, dúvidas sobre regras, colaboração e denúncias são atendidos '
            'pela equipe nos canais oficiais do Bonfire Tales.'
        ),
        'conteudo_markdown': (
            '- **Discord:** use os canais de suporte da comunidade para atendimento e dúvidas.\n'
            '- **E-mail:** mestresbonfiretales@gmail.com\n'
            '- **Conteúdo ou segurança:** informe a página, o usuário envolvido e uma descrição objetiva do problema.\n\n'
            'Nunca envie senha, código de acesso ou dados completos de pagamento. Pagamentos '
            'são processados pelo Asaas; a equipe não solicita esses dados por mensagem.'
        ),
        'cta_texto': 'Abrir o Discord',
        'cta_url': 'https://discord.gg/eyqe7rj2AX',
        'ordem': 10,
    },
    {
        'chave': 'privacidade-principal',
        'pagina': 'privacidade',
        'titulo': 'Política de Privacidade',
        'subtitulo': 'Última atualização: 12 de agosto de 2026.',
        'conteudo_markdown': (
            '## Dados que tratamos\n\n'
            'Ao criar uma conta, podemos tratar nome de usuário, e-mail, identificador e nome '
            'público do Discord. Também armazenamos o conteúdo necessário ao funcionamento das '
            'fichas, perfis, crônicas, missões, transações internas e preferências do usuário.\n\n'
            '## Para que usamos\n\n'
            'Usamos esses dados para autenticação, recuperação de acesso, integração com o bot, '
            'participação em missões, manutenção das fichas, moderação, prevenção de abuso, '
            'suporte e melhoria do serviço.\n\n'
            '## Cookies, métricas e publicidade\n\n'
            'O site usa cookies essenciais de sessão e segurança. Quando serviços do Google '
            'forem habilitados, Google e seus parceiros poderão usar cookies, endereços IP, '
            'beacons e outros identificadores para medir audiência e exibir publicidade. '
            'Consulte [como o Google usa informações de sites que utilizam seus serviços]'
            '(https://policies.google.com/technologies/partner-sites).\n\n'
            '## Compartilhamento e pagamentos\n\n'
            'A autenticação opcional usa o Discord. Pagamentos de colaboração são processados '
            'pelo Asaas; o Bonfire Tales recebe somente os dados necessários para reconhecer e '
            'conciliar o pagamento. Não vendemos dados pessoais.\n\n'
            '## Retenção, segurança e direitos\n\n'
            'Mantemos os dados enquanto a conta ou a obrigação correspondente existir, aplicando '
            'medidas razoáveis de segurança. Você pode solicitar acesso, correção ou exclusão '
            'pelos canais da página de contato. Alguns registros podem ser preservados quando '
            'necessários para segurança, prevenção de fraude ou obrigação legal.'
        ),
        'ordem': 10,
    },
    {
        'chave': 'termos-principal',
        'pagina': 'termos',
        'titulo': 'Termos de Uso',
        'subtitulo': 'Última atualização: 12 de agosto de 2026.',
        'conteudo_markdown': (
            '## Uso da plataforma\n\n'
            'Ao usar o Bonfire Tales, você concorda em respeitar as regras da comunidade, a '
            'legislação aplicável e os direitos de outras pessoas. A conta é pessoal; você é '
            'responsável por manter suas credenciais seguras e pelas ações realizadas nela.\n\n'
            '## Conteúdo da comunidade\n\n'
            'Você mantém a autoria do conteúdo que publicar e concede ao Bonfire Tales permissão '
            'para exibi-lo e organizá-lo dentro do serviço. Não publique material ilegal, '
            'ofensivo, enganoso ou que viole direitos de terceiros. A equipe pode moderar ou '
            'remover conteúdo e restringir contas para proteger a comunidade.\n\n'
            '## Serviço e conteúdo de RPG\n\n'
            'O site pode mudar durante o beta, inclusive regras, ferramentas e disponibilidade. '
            'Buscamos manter as informações corretas, mas decisões finais de mesa e de moderação '
            'seguem os documentos e canais oficiais da comunidade. Marcas e materiais de '
            'terceiros pertencem aos respectivos titulares.\n\n'
            '## Colaboração e pagamentos\n\n'
            'A colaboração é opcional e não é necessária para jogar. Os benefícios, preços e '
            'períodos válidos são os exibidos na página de colaboração no momento da compra. '
            'O processamento financeiro é realizado pelo Asaas.\n\n'
            '## Contato\n\n'
            'Dúvidas, solicitações de privacidade e avisos sobre conteúdo podem ser enviados '
            'pelos canais informados na página de contato.'
        ),
        'ordem': 10,
    },
]


def criar_conteudos(apps, schema_editor):
    Conteudo = apps.get_model('home', 'TbConteudoEstatico')
    for dados in CONTEUDOS_INICIAIS:
        Conteudo.objects.update_or_create(chave=dados['chave'], defaults=dados)


def remover_conteudos(apps, schema_editor):
    Conteudo = apps.get_model('home', 'TbConteudoEstatico')
    Conteudo.objects.filter(chave__in=[item['chave'] for item in CONTEUDOS_INICIAIS]).delete()


class Migration(migrations.Migration):
    dependencies = [('home', '0091_nomes_ingles_e_dedupe_itens')]

    operations = [
        migrations.CreateModel(
            name='TbConteudoEstatico',
            fields=[
                ('id_conteudo', models.AutoField(db_column='Id_Conteudo', primary_key=True, serialize=False)),
                ('chave', models.SlugField(db_column='Chave', help_text='Identificador estável do bloco, por exemplo home-hero.', max_length=100, unique=True)),
                ('pagina', models.SlugField(db_column='Pagina', db_index=True, help_text='Página proprietária do bloco, por exemplo home ou privacidade.', max_length=60)),
                ('titulo', models.CharField(blank=True, db_column='Titulo', max_length=220)),
                ('subtitulo', models.TextField(blank=True, db_column='Subtitulo')),
                ('conteudo_markdown', models.TextField(blank=True, db_column='ConteudoMarkdown', help_text='Corpo em Markdown Bonfire. Referências em card continuam disponíveis.')),
                ('cta_texto', models.CharField(blank=True, db_column='CtaTexto', max_length=100)),
                ('cta_url', models.CharField(blank=True, db_column='CtaUrl', max_length=500)),
                ('imagem_url', models.CharField(blank=True, db_column='ImagemUrl', max_length=500)),
                ('ativo', models.BooleanField(db_column='Ativo', default=True)),
                ('ordem', models.PositiveIntegerField(db_column='Ordem', default=0)),
                ('atualizado_em', models.DateTimeField(auto_now=True, db_column='AtualizadoEm')),
            ],
            options={
                'verbose_name': 'Conteúdo estático',
                'verbose_name_plural': 'Conteúdos estáticos',
                'db_table': 'TB_ConteudoEstatico',
                'ordering': ['pagina', 'ordem', 'chave'],
            },
        ),
        migrations.RunPython(criar_conteudos, remover_conteudos),
    ]
