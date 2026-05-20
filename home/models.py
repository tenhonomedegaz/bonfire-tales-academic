





















import json

from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver





class TbAcessoopcao(models.Model):

    id_acessoopcao = models.AutoField(db_column='Id_AcessoOpcao', primary_key=True)  

    id_opcao = models.ForeignKey('TbOpcaojogo', models.DO_NOTHING, db_column='Id_Opcao')  

    id_classe = models.ForeignKey('TbClasse', models.DO_NOTHING, db_column='Id_Classe', blank=True, null=True)  

    id_subclasse = models.ForeignKey('TbSubclasse', models.DO_NOTHING, db_column='Id_Subclasse', blank=True, null=True)  

    nivel_recebimento = models.IntegerField(db_column='NivelRecebimento', default=1)  


    class Meta:

        managed = True

        db_table = 'TB_AcessoOpcao'
        verbose_name = 'Acesso de Opção'
        verbose_name_plural = 'Acessos de Opções'

    def __str__(self):
        return f"{self.id_opcao} / {self.id_classe or '-'} / {self.id_subclasse or '-'}"





class TbClasse(models.Model):

    id_classe = models.AutoField(db_column='Id_Classe', primary_key=True)  

    nome = models.CharField(db_column='Nome')  

    slug = models.CharField(db_column='Slug', unique=True)  

    tagline = models.CharField(db_column='Tagline', blank=True, null=True)  

    atributo_principal = models.TextField(db_column='AtributoPrincipal', blank=True, null=True)
    dado_vida = models.TextField(db_column='DadoVida', blank=True, null=True)
    pv_nivel_1 = models.TextField(db_column='PVNivel1', blank=True, null=True)
    pv_por_nivel = models.TextField(db_column='PVPORNivel', blank=True, null=True)
    resistencias = models.TextField(db_column='Resistencias', blank=True, null=True)
    pericias = models.TextField(db_column='Pericias', blank=True, null=True)
    armas = models.TextField(db_column='Armas', blank=True, null=True)
    ferramentas = models.TextField(db_column='Ferramentas', blank=True, null=True)
    armaduras = models.TextField(db_column='Armaduras', blank=True, null=True)
    equipamento = models.TextField(db_column='Equipamento', blank=True, null=True)
    multiclass_requisitos = models.TextField(db_column='MulticlassRequisitos', blank=True, null=True)
    multiclass_pericias = models.TextField(db_column='MulticlassPericias', blank=True, null=True)
    multiclass_ferramentas = models.TextField(db_column='MulticlassFerramentas', blank=True, null=True)
    multiclass_armaduras = models.TextField(db_column='MulticlassArmaduras', blank=True, null=True)



    class Meta:

        managed = True

        db_table = 'TB_Classe'
        verbose_name = 'Classe'
        verbose_name_plural = 'Classes'

    def __str__(self):
        return self.nome





class TbClassehabilidade(models.Model):

    id_habilidade = models.AutoField(db_column='Id_Habilidade', primary_key=True)  

    id_classe = models.ForeignKey(TbClasse, models.DO_NOTHING, db_column='Id_Classe')  

    id_subclasse = models.ForeignKey('TbSubclasse', models.DO_NOTHING, db_column='Id_Subclasse', blank=True, null=True)  

    nome = models.CharField(db_column='Nome')  

    descricao = models.TextField(db_column='Descricao')  

    niveladquirido = models.IntegerField(db_column='NivelAdquirido')  

    table_only = models.BooleanField(db_column='TableOnly', default=False, help_text='Mostra esta habilidade apenas na tabela de progressao.')



    class Meta:

        managed = True

        db_table = 'TB_ClasseHabilidade'
        verbose_name = 'Habilidade de Classe'
        verbose_name_plural = 'Habilidades de Classe'

    def __str__(self):
        return f"{self.nome} (Nivel {self.niveladquirido})"





class TbOpcaojogo(models.Model):

    id_opcao = models.AutoField(db_column='Id_Opcao', primary_key=True)  

    nome = models.CharField(db_column='Nome')  

    slug = models.CharField(db_column='Slug', unique=True)  

    tipo = models.CharField(db_column='Tipo')  

    descricao = models.TextField(db_column='Descricao', blank=True, null=True)  

    pre_requisito = models.TextField(db_column='PreRequisito', blank=True, null=True)
    etiquetas_adicionais = models.CharField(db_column='EtiquetasAdicionais', max_length=255, blank=True, null=True)


    class Meta:

        managed = True

        db_table = 'TB_OpcaoJogo'
        verbose_name = 'Opção de Jogo'
        verbose_name_plural = 'Opções de Jogo'

    def __str__(self):
        return self.nome





class TbRecursoclasse(models.Model):

    id_recurso = models.AutoField(db_column='Id_Recurso', primary_key=True)  

    id_classe = models.ForeignKey(TbClasse, models.DO_NOTHING, db_column='Id_Classe')  

    id_subclasse = models.ForeignKey('TbSubclasse', models.DO_NOTHING, db_column='Id_Subclasse', blank=True, null=True)  

    nome = models.CharField(db_column='Nome')  

    slug = models.CharField(db_column='Slug')  

    nivel = models.IntegerField(db_column='Nivel')  

    valor = models.CharField(db_column='Valor', blank=True, null=True)  



    class Meta:

        managed = True

        db_table = 'TB_RecursoClasse'
        verbose_name = 'Recurso de Classe'
        verbose_name_plural = 'Recursos de Classe'

    def __str__(self):
        return f"{self.nome} - Nivel {self.nivel}"





class TbSubclasse(models.Model):

    id_subclasse = models.AutoField(db_column='Id_Subclasse', primary_key=True)  

    id_classe = models.ForeignKey(TbClasse, models.DO_NOTHING, db_column='Id_Classe')  

    nome = models.CharField(db_column='Nome')  

    slug = models.CharField(db_column='Slug')  

    tagline = models.CharField(db_column='Tagline', blank=True, null=True)  



    class Meta:

        managed = True

        db_table = 'TB_Subclasse'
        verbose_name = 'Subclasse'
        verbose_name_plural = 'Subclasses'

    def __str__(self):
        return self.nome

class TbRaca(models.Model):
    id_raca = models.AutoField(db_column='Id_Raca', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=100)
    slug = models.CharField(db_column='Slug', max_length=100, unique=True)
    tagline = models.CharField(db_column='Tagline', max_length=255, blank=True, null=True)
    lore_presentation = models.TextField(db_column='LorePresentation', blank=True, null=True)
    lore_roleplay = models.TextField(db_column='LoreRoleplay', blank=True, null=True)
    lore_society = models.TextField(db_column='LoreSociety', blank=True, null=True)
    permite_essencia = models.BooleanField(db_column='PermiteEssencia', default=True)

    class Meta:
        db_table = 'TB_Raca'
        verbose_name = 'Raça'
        verbose_name_plural = 'Raças'

    def __str__(self):
        return self.nome

class TbLinhagem(models.Model):
    id_linhagem = models.AutoField(db_column='Id_Linhagem', primary_key=True)
    id_raca = models.ForeignKey(TbRaca, models.CASCADE, db_column='Id_Raca', related_name='linhagens')
    nome = models.CharField(db_column='Nome', max_length=100)
    slug = models.CharField(db_column='Slug', max_length=100, unique=True)
    lore_presentation = models.TextField(db_column='LorePresentation', blank=True, null=True)
    lore_roleplay = models.TextField(db_column='LoreRoleplay', blank=True, null=True)
    lore_society = models.TextField(db_column='LoreSociety', blank=True, null=True)
    descricao = models.TextField(db_column='Descricao', blank=True, null=True)

    class Meta:
        db_table = 'TB_Linhagem'
        verbose_name = 'Linhagem'
        verbose_name_plural = 'Linhagens'

    def __str__(self):
        return self.nome

class TbEssencia(models.Model):
    id_essencia = models.AutoField(db_column='Id_Essencia', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=100)
    slug = models.CharField(db_column='Slug', max_length=100, unique=True)
    lore_presentation = models.TextField(db_column='LorePresentation', blank=True, null=True)
    lore_roleplay = models.TextField(db_column='LoreRoleplay', blank=True, null=True)
    lore_society = models.TextField(db_column='LoreSociety', blank=True, null=True)

    class Meta:
        db_table = 'TB_Essencia'
        verbose_name = 'Essência'
        verbose_name_plural = 'Essências'

    def __str__(self):
        return self.nome

class TbTracoracial(models.Model):
    id_traco = models.AutoField(db_column='Id_Traco', primary_key=True)
    id_raca = models.ForeignKey(TbRaca, models.CASCADE, db_column='Id_Raca', blank=True, null=True, related_name='tracos')
    id_linhagem = models.ForeignKey(TbLinhagem, models.CASCADE, db_column='Id_Linhagem', blank=True, null=True, related_name='tracos_linhagem')
    id_essencia = models.ForeignKey(TbEssencia, models.CASCADE, db_column='Id_Essencia', blank=True, null=True, related_name='tracos')
    nome = models.CharField(db_column='Nome', max_length=150)
    descricao = models.TextField(db_column='Descricao')
    nivel_requisito = models.IntegerField(db_column='NivelRequisito', default=0)
    talento_racial = models.BooleanField(db_column='TalentoRacial', default=False, help_text='Marca tracos opcionais de raca que podem ser escolhidos como talentos raciais.')
    pre_requisito = models.TextField(db_column='PreRequisito', blank=True, null=True, help_text='Pre-requisito para talentos raciais opcionais.')

    class Meta:
        db_table = 'TB_TracoRacial'
        verbose_name = 'Traço Racial'
        verbose_name_plural = 'Traços Raciais'

    def __str__(self):
        return self.nome

class TbMapMarker(models.Model):

    PIN_ICON_CHOICES = [
        ('capital', 'Capital'),
        ('cidade', 'Cidade'),
        ('fortaleza', 'Fortaleza'),
        ('conglomerado_vilas', 'Conglomerado de Vilas'),
        ('vila', 'Vila'),
        ('cidade_portuaria', 'Cidade Portuária'),
        ('area_selvagem', 'Área Selvagem'),
    ]

    id_marker = models.AutoField(db_column='Id_Marker', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    lat = models.FloatField(db_column='Latitude', help_text="Ponto Y / Cima pra baixo no mapa customizado.")
    lng = models.FloatField(db_column='Longitude', help_text="Ponto X / Esquerda pra direita no mapa customizado.")
    categoria = models.CharField(db_column='Categoria', max_length=50, choices=PIN_ICON_CHOICES, default='cidade')
    territorio = models.CharField(db_column='Territorio', max_length=150, blank=True, null=True)
    
    class Meta:
        db_table = 'TB_MapMarker'
        verbose_name = 'Marcador do Mapa'
        verbose_name_plural = 'Marcadores do Mapa'

    def __str__(self):
        return self.nome


class TbRegiao(models.Model):
    CATEGORIA_CHOICES = TbMapMarker.PIN_ICON_CHOICES
    id_regiao = models.AutoField(db_column='Id_Regiao', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=200)
    slug = models.SlugField(db_column='Slug', max_length=200, unique=True)
    lore_markdown = models.TextField(db_column='LoreMarkdown', blank=True, null=True, help_text='Conteudo completo de lore da regiao em Markdown.')
    territorio = models.CharField(db_column='Territorio', max_length=150, blank=True, null=True)
    categoria = models.CharField(db_column='Categoria', max_length=50, choices=CATEGORIA_CHOICES, default='cidade')
    brasao_url = models.CharField(db_column='BrasaoUrl', max_length=500, blank=True, null=True, help_text='URL ou caminho static da imagem do brasão.')
    mapa_url = models.CharField(db_column='MapaUrl', max_length=500, blank=True, null=True, help_text='URL ou caminho static do mapa lateral da região.')
    etiquetas_adicionais = models.TextField(db_column='EtiquetasAdicionais', blank=True, null=True, help_text='Tags adicionais separadas por vírgula.')

    movimentacoes_economicas = models.IntegerField(db_column='MovimentacoesEconomicas', default=0)
    poder_militar = models.IntegerField(db_column='PoderMilitar', default=0)
    desenvolvimento_tecnologico = models.IntegerField(db_column='DesenvolvimentoTecnologico', default=0)
    estabilidade_politica_interna = models.IntegerField(db_column='EstabilidadePoliticaInterna', default=0)
    ameacas_externas = models.IntegerField(db_column='AmeacasExternas', default=0)
    densidade_populacional = models.IntegerField(db_column='DensidadePopulacional', default=0)
    tolerancia_estrangeiros = models.IntegerField(db_column='ToleranciaEstrangeiros', default=0)
    manipulacao_trama = models.IntegerField(db_column='ManipulacaoTrama', default=0)
    
    ameacas_internas = models.IntegerField(db_column='AmeacasInternas', default=0)
    nivel_periculosidade = models.IntegerField(db_column='NivelPericulosidade', default=0)
    recursos_naturais = models.IntegerField(db_column='RecursosNaturais', default=0)
    recursos_magicos = models.IntegerField(db_column='RecursosMagicos', default=0)
    diversidade_criaturas = models.IntegerField(db_column='DiversidadeCriaturas', default=0)

    class Meta:
        db_table = 'TB_Regiao'
        verbose_name = 'Região'
        verbose_name_plural = 'Regiões'

    def __str__(self):
        return self.nome


class TbTerritorio(models.Model):
    id_territorio = models.AutoField(db_column='Id_Territorio', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150, unique=True)
    slug = models.SlugField(db_column='Slug', max_length=160, unique=True)
    descricao_breve = models.TextField(db_column='DescricaoBreve', blank=True, null=True)
    lore_markdown = models.TextField(db_column='LoreMarkdown', blank=True, null=True, help_text='Lore do território em Markdown.')
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True, help_text='URL ou caminho static da imagem de capa.')

    coordenadas_poligono = models.JSONField(db_column='CoordenadasPoligono', blank=True, null=True, help_text='Coordenadas GeoJSON para renderizar a área no mapa.')
    cor_hex = models.CharField(db_column='CorHex', max_length=7, default='#ffffff', help_text='Cor em formato Hexadecimal (ex: #FFFFFF)')
    riqueza_natural = models.IntegerField(db_column='RiquezaNatural', default=0)
    riqueza_monetaria = models.IntegerField(db_column='RiquezaMonetaria', default=0)
    poder_militar = models.IntegerField(db_column='PoderMilitar', default=0)
    desenvolvimento_tecnologico = models.IntegerField(db_column='DesenvolvimentoTecnologico', default=0)
    estabilidade_politica_interna = models.IntegerField(db_column='EstabilidadePoliticaInterna', default=0)
    ameacas_externas = models.IntegerField(db_column='AmeacasExternas', default=0)
    diplomacia = models.IntegerField(db_column='Diplomacia', default=0)
    manipulacao_trama = models.IntegerField(db_column='ManipulacaoTrama', default=0)

    class Meta:
        db_table = 'TB_Territorio'
        verbose_name = 'Território'
        verbose_name_plural = 'Territórios'

    def __str__(self):
        return self.nome


class TbTalento(models.Model):
    TIPO_CHOICES = [
        ('origem', 'Origem'),
        ('geral', 'Geral'),
    ]

    ETIQUETA_CHOICES = [
        ('combate', 'COMBATE'),
        ('conjuracao', 'CONJURAÇÃO'),
        ('exploracao', 'EXPLORAÇÃO'),
        ('hemomancia', 'HEMOMANCIA'),
        ('marcas', 'MARCAS'),
        ('masterizacao', 'MASTERIZAÇÃO'),
        ('sobrevivencia', 'SOBREVIVÊNCIA'),
        ('social', 'SOCIAL'),
        ('suporte', 'SUPORTE'),
        ('utilidade', 'UTILIDADE'),
    ]

    id_talento = models.AutoField(db_column='Id_Talento', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    slug = models.SlugField(db_column='Slug', max_length=150, unique=True, help_text="Ex: guerreiro-nato (usado para links)")
    tipo = models.CharField(db_column='Tipo', max_length=50, choices=TIPO_CHOICES, default='geral')
    etiqueta = models.CharField(db_column='Etiqueta', max_length=50, choices=ETIQUETA_CHOICES, default='combate', help_text="Categoria/Tag principal do talento.")
    etiquetas_adicionais = models.TextField(db_column='EtiquetasAdicionais', blank=True, null=True, help_text="Tags adicionais separadas por vírgula.")
    pre_requisito = models.TextField(db_column='PreRequisito', blank=True, null=True, help_text="Pré-requisitos do talento.")
    descricao = models.TextField(db_column='Descricao', help_text="Use Markdown para formatar os benefícios (Listas, Negrito, Títulos).")
    
    
    atrib_forca = models.BooleanField(db_column='Atrib_Forca', default=False, verbose_name="+1 Força")
    atrib_destreza = models.BooleanField(db_column='Atrib_Destreza', default=False, verbose_name="+1 Destreza")
    atrib_constituicao = models.BooleanField(db_column='Atrib_Constituicao', default=False, verbose_name="+1 Constituição")
    atrib_inteligencia = models.BooleanField(db_column='Atrib_Inteligencia', default=False, verbose_name="+1 Inteligência")
    atrib_sabedoria = models.BooleanField(db_column='Atrib_Sabedoria', default=False, verbose_name="+1 Sabedoria")
    atrib_carisma = models.BooleanField(db_column='Atrib_Carisma', default=False, verbose_name="+1 Carisma")

    class Meta:
        db_table = 'TB_Talento'
        verbose_name = 'Talento'
        verbose_name_plural = 'Talentos'

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.nome}"





class TbJornal(models.Model):
    id_jornal = models.AutoField(db_column='Id_Jornal', primary_key=True)
    titulo = models.CharField(db_column='Titulo', max_length=200)
    slug = models.SlugField(db_column='Slug', max_length=220, unique=True)
    conteudo_markdown = models.TextField(db_column='ConteudoMarkdown', blank=True, null=True)
    resumo = models.CharField(db_column='Resumo', max_length=300, blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    autor = models.ForeignKey('auth.User', models.SET_NULL, db_column='Autor', blank=True, null=True, related_name='jornais')
    data_publicacao = models.DateTimeField(db_column='DataPublicacao', default=timezone.now)
    data_edicao = models.DateTimeField(db_column='DataEdicao', auto_now=True)
    destaque = models.BooleanField(db_column='Destaque', default=False)
    layout = models.CharField(db_column='Layout', max_length=20, choices=[('padrao', 'Padrão'), ('colunas', 'Colunas'), ('atlas', 'Atlas (Jornal)')], default='padrao')

    class Meta:
        managed = True
        db_table = 'TB_Jornal'
        verbose_name = 'Artigo de Jornal'
        verbose_name_plural = 'Artigos de Jornal'
        ordering = ['-data_publicacao']

    def __str__(self):
        return self.titulo


class TbCronica(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('aprovada', 'Aprovada'),
        ('reprovada', 'Reprovada'),
    ]

    id_cronica = models.AutoField(db_column='Id_Cronica', primary_key=True)
    titulo = models.CharField(db_column='Titulo', max_length=200)
    slug = models.SlugField(db_column='Slug', max_length=220, unique=True)
    conteudo_markdown = models.TextField(db_column='ConteudoMarkdown')
    resumo = models.CharField(db_column='Resumo', max_length=300, blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    autor = models.ForeignKey('auth.User', models.CASCADE, db_column='Autor', related_name='cronicas')
    personagem_nome = models.CharField(db_column='PersonagemNome', max_length=150, blank=True, null=True, help_text='Nome do personagem narrador.')
    territorio = models.TextField(db_column='Territorio', blank=True, null=True, help_text='Territórios onde a crônica se passa.')
    regiao = models.TextField(db_column='Regiao', blank=True, null=True, help_text='Regiões específicas onde a crônica se passa.')
    status = models.CharField(db_column='Status', max_length=20, choices=STATUS_CHOICES, default='pendente')
    feedback_staff = models.TextField(db_column='FeedbackStaff', blank=True, null=True, help_text='Feedback do staff na revisão.')
    revisado_por = models.ForeignKey('auth.User', models.SET_NULL, db_column='RevisadoPor', blank=True, null=True, related_name='cronicas_revisadas')
    data_submissao = models.DateTimeField(db_column='DataSubmissao', auto_now_add=True)
    data_revisao = models.DateTimeField(db_column='DataRevisao', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'TB_Cronica'
        verbose_name = 'Crônica'
        verbose_name_plural = 'Crônicas'
        ordering = ['-data_submissao']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.titulo}"

    @staticmethod
    def _as_list(value):
        if not value:
            return []
        try:
            decoded = json.loads(value)
            if isinstance(decoded, list):
                return [str(item) for item in decoded if str(item)]
        except (TypeError, ValueError):
            pass
        return [value]

    @property
    def territorios_lista(self):
        return self._as_list(self.territorio)

    @property
    def regioes_lista(self):
        return self._as_list(self.regiao)

    @property
    def territorio_label(self):
        return ', '.join(self.territorios_lista) or 'Cinéria'

    @property
    def regiao_label(self):
        return ', '.join(self.regioes_lista)


@receiver(post_save, sender=TbRegiao)
def sync_region_to_marker(sender, instance, **kwargs):
    if kwargs.get('raw', False):
        return
    from django.utils.text import slugify
    
    
    marker, created = TbMapMarker.objects.get_or_create(
        nome=instance.nome,
        defaults={
            'lat': 0, 
            'lng': 0,
            'categoria': instance.categoria or 'cidade',
            'territorio': instance.territorio,
        }
    )
    
    if not created:
        marker.territorio = instance.territorio
        marker.categoria = instance.categoria
        marker.save()

class TbItemMundano(models.Model):
    CATEGORIA_CHOICES = [
        ('arma', 'Arma'),
        ('armadura', 'Armadura'),
        ('ferramenta', 'Ferramenta'),
        ('pacote', 'Pacote'),
        ('equipamento_aventura', 'Equipamento de Aventura'),
    ]

    id_item = models.AutoField(db_column='Id_Item', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    slug = models.SlugField(db_column='Slug', max_length=150, unique=True)
    categoria = models.CharField(db_column='Categoria', max_length=50, choices=CATEGORIA_CHOICES, default='equipamento_aventura')
    subcategoria = models.CharField(db_column='Subcategoria', max_length=100, blank=True, null=True, help_text='Ex: arma_simples, escudo, ferramenta_artesao')
    peso = models.FloatField(db_column='Peso', blank=True, null=True, help_text='Peso em kg ou lbs')
    preco = models.CharField(db_column='Preco', max_length=50, blank=True, null=True, help_text='Ex: 5 PO')
    
    
    dano = models.CharField(db_column='Dano', max_length=50, blank=True, null=True, help_text='Ex: 1d8 cortante')
    propriedades = models.CharField(db_column='Propriedades', max_length=200, blank=True, null=True, help_text='Ex: Acuidade, Leve')
    maestria = models.CharField(db_column='Maestria', max_length=100, blank=True, null=True, help_text='Opção adicional de maestria')
    
    
    ca = models.CharField(db_column='CA', max_length=50, blank=True, null=True, help_text='Ex: 14 + mod Des (max 2)')
    forca_minima = models.IntegerField(db_column='ForcaMinima', blank=True, null=True, help_text='Força mínima para usar')
    furtividade_desvantagem = models.BooleanField(db_column='FurtividadeDesvantagem', default=False)
    
    descricao_markdown = models.TextField(db_column='DescricaoMarkdown', blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)

    class Meta:
        db_table = 'TB_ItemMundano'
        verbose_name = 'Item Mundano'
        verbose_name_plural = 'Itens Mundanos'

    def __str__(self):
        return f"[{self.get_categoria_display()}] {self.nome}"


class TbItemMagico(models.Model):
    RARIDADE_CHOICES = [
        ('comum', 'Comum'),
        ('incomum', 'Incomum'),
        ('raro', 'Raro'),
        ('muito_raro', 'Muito Raro'),
        ('lendario', 'Lendário'),
        ('artefato', 'Artefato'),
    ]

    SLOT_CHOICES = [
        ('cabeca', 'Cabeça'),
        ('face_olhos', 'Face/Olhos'),
        ('pescoco', 'Pescoço'),
        ('costas', 'Costas'),
        ('torso', 'Torso'),
        ('maos', 'Mãos'),
        ('dedos', 'Dedos'),
        ('cintura', 'Cintura'),
        ('pes', 'Pés'),
        ('objeto', 'Objeto'),
        ('item_menor', 'Item Menor'),
    ]

    id_item = models.AutoField(db_column='Id_Item', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    slug = models.SlugField(db_column='Slug', max_length=150, unique=True)
    raridade = models.CharField(db_column='Raridade', max_length=50, choices=RARIDADE_CHOICES, default='incomum')
    requer_sintonizacao = models.BooleanField(db_column='RequerSintonizacao', default=False)
    detalhes_sintonizacao = models.CharField(db_column='DetalhesSintonizacao', max_length=150, blank=True, null=True, help_text='Ex: por um mago')
    slot = models.CharField(db_column='Slot', max_length=50, choices=SLOT_CHOICES, default='objeto')
    tipo = models.CharField(db_column='Tipo', max_length=100, blank=True, null=True, help_text='Ex: Espada longa, Poção, Anel')
    
    descricao_markdown = models.TextField(db_column='DescricaoMarkdown', blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)

    class Meta:
        db_table = 'TB_ItemMagico'
        verbose_name = 'Item Mágico'
        verbose_name_plural = 'Itens Mágicos'

    def __str__(self):
        return f"[{self.get_raridade_display()}] {self.nome}"


class UserProfile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    avatar_url = models.CharField(db_column='AvatarUrl', max_length=500, blank=True, null=True, help_text='URL da imagem de perfil.')

    class Meta:
        db_table = 'TB_UserProfile'
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'

    def __str__(self):
        return f"Perfil de {self.user.username}"


@receiver(post_save, sender='auth.User')
def create_user_profile(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    if created:
        UserProfile.objects.get_or_create(user=instance)


# ─────────────────────────────────────────────────────────────────────────────
# Tabelas exclusivas do Bot (Prisma) — managed=False
# O Django NÃO cria/migra essas tabelas, apenas lê/escreve.
# ─────────────────────────────────────────────────────────────────────────────

class BotQuest(models.Model):
    id = models.CharField(primary_key=True, max_length=30)
    guildId = models.CharField(db_column='guildId', max_length=100)
    channelId = models.CharField(db_column='channelId', max_length=100, blank=True, null=True)
    name = models.CharField(max_length=500)
    description = models.TextField()
    questDate = models.DateTimeField(db_column='questDate')
    playersAmount = models.IntegerField(db_column='playersAmount')
    rules = models.TextField()
    tags = models.TextField(db_column='tags', blank=True, null=True, help_text='PostgreSQL array')
    type = models.CharField(max_length=100)
    tableUrl = models.CharField(db_column='tableUrl', max_length=500)
    questMaster = models.CharField(db_column='questMaster', max_length=200)
    allowedRanks = models.TextField(db_column='allowedRanks', blank=True, null=True)
    mandatoryPlayers = models.TextField(db_column='mandatoryPlayers', blank=True, null=True)
    highPriorityPlayers = models.TextField(db_column='highPriorityPlayers', blank=True, null=True)
    subscribedPlayers = models.JSONField(db_column='subscribedPlayers', default=list)
    questPlayers = models.JSONField(db_column='questPlayers', default=list)
    removedPlayers = models.TextField(db_column='removedPlayers', blank=True, null=True)
    participationRequests = models.JSONField(db_column='participationRequests', default=list)
    createdBy = models.CharField(db_column='createdBy', max_length=200)
    isPublished = models.BooleanField(db_column='isPublished', default=False)
    status = models.CharField(max_length=50, default='idle')
    timeEvents = models.JSONField(db_column='timeEvents', default=list)
    startDate = models.DateTimeField(db_column='startDate', blank=True, null=True)
    endDate = models.DateTimeField(db_column='endDate', blank=True, null=True)
    rewardAventurasOverride = models.IntegerField(db_column='rewardAventurasOverride', blank=True, null=True)
    dedicatedRankId = models.CharField(db_column='dedicatedRankId', max_length=30, blank=True, null=True)
    createdAt = models.DateTimeField(db_column='createdAt')
    updatedAt = models.DateTimeField(db_column='updatedAt')

    class Meta:
        managed = False
        db_table = 'rpg_quests'
        verbose_name = 'Missão (Bot)'
        verbose_name_plural = 'Missões (Bot)'

    def __str__(self):
        return self.name or self.id





class BotMember(models.Model):
    id = models.CharField(primary_key=True, max_length=30)
    discordUserId = models.CharField(db_column='discordUserId', max_length=100, unique=True)
    discordUserTag = models.CharField(db_column='discordUserTag', max_length=200)
    email = models.CharField(max_length=300, unique=True)
    tokenSuperboost = models.IntegerField(db_column='tokenSuperboost', default=0)
    tokenXpBoost = models.IntegerField(db_column='tokenXpBoost', default=0)
    tokenMission = models.IntegerField(db_column='tokenMission', default=0)
    isModerator = models.BooleanField(db_column='isModerator', default=False)
    isAdmin = models.BooleanField(db_column='isAdmin', default=False)
    skipValidation = models.BooleanField(db_column='skipValidation', default=False)
    createdAt = models.DateTimeField(db_column='createdAt')
    updatedAt = models.DateTimeField(db_column='updatedAt')

    class Meta:
        managed = False
        db_table = 'discord_subscribers'
        verbose_name = 'Membro (Bot)'
        verbose_name_plural = 'Membros (Bot)'

    def __str__(self):
        return f"{self.discordUserTag} ({self.discordUserId})"


class BotTransaction(models.Model):
    id = models.CharField(primary_key=True, max_length=30)
    transactionCode = models.CharField(db_column='transactionCode', max_length=200, unique=True)
    transactionSource = models.CharField(db_column='transactionSource', max_length=200, blank=True, null=True)
    paymentDate = models.DateTimeField(db_column='paymentDate')
    expirationDate = models.DateTimeField(db_column='expirationDate')
    subscriptionPlan = models.CharField(db_column='subscriptionPlan', max_length=200)
    subscriptionPeriod = models.CharField(db_column='subscriptionPeriod', max_length=200)
    subscriptionReference = models.CharField(db_column='subscriptionReference', max_length=200, blank=True, null=True)
    status = models.IntegerField()
    grossAmount = models.FloatField(db_column='grossAmount')
    netAmount = models.FloatField(db_column='netAmount')
    name = models.CharField(max_length=300, blank=True, null=True)
    email = models.CharField(max_length=300)
    comments = models.TextField(blank=True, null=True)
    claimed = models.BooleanField(default=False)
    claimedAt = models.DateTimeField(db_column='claimedAt', blank=True, null=True)
    createdAt = models.DateTimeField(db_column='createdAt')
    updatedAt = models.DateTimeField(db_column='updatedAt')

    class Meta:
        managed = False
        db_table = 'transactions'
        verbose_name = 'Transação (Bot)'
        verbose_name_plural = 'Transações (Bot)'

    def __str__(self):
        return f"{self.transactionCode} - {self.name or self.email}"


class BotSchedulerJob(models.Model):
    id = models.CharField(primary_key=True, max_length=30)
    name = models.CharField(max_length=300)
    data = models.JSONField()
    nextRunAt = models.DateTimeField(db_column='nextRunAt')

    class Meta:
        managed = False
        db_table = 'discord_jobs'
        verbose_name = 'Job Agendado (Bot)'
        verbose_name_plural = 'Jobs Agendados (Bot)'

    def __str__(self):
        return f"{self.name} → {self.nextRunAt}"


class BotDedicatedRank(models.Model):
    id = models.CharField(primary_key=True, max_length=30)
    guildId = models.CharField(db_column='guildId', max_length=100)
    rankings = models.JSONField()
    validFrom = models.DateTimeField(db_column='validFrom')
    validUntil = models.DateTimeField(db_column='validUntil')
    isActive = models.BooleanField(db_column='isActive', default=True)
    isPriorityLocked = models.BooleanField(db_column='isPriorityLocked', default=False)
    priorityRankName = models.CharField(db_column='priorityRankName', max_length=200, blank=True, null=True)
    createdAt = models.DateTimeField(db_column='createdAt')
    updatedAt = models.DateTimeField(db_column='updatedAt')

    class Meta:
        managed = False
        db_table = 'dedicated-ranks'
        verbose_name = 'Ranking Dedicado (Bot)'
        verbose_name_plural = 'Rankings Dedicados (Bot)'

    def __str__(self):
        return f"Rank {self.priorityRankName or self.id} ({'Ativo' if self.isActive else 'Inativo'})"


class BotCharacterLog(models.Model):
    id = models.CharField(primary_key=True, max_length=30)
    discordUserId = models.CharField(db_column='discordUserId', max_length=100)
    discordUserTag = models.CharField(db_column='discordUserTag', max_length=200)
    sheetUrl = models.CharField(db_column='sheetUrl', max_length=500)
    spreadsheetId = models.CharField(db_column='spreadsheetId', max_length=300, unique=True)
    characterName = models.CharField(db_column='characterName', max_length=300)
    rankName = models.CharField(db_column='rankName', max_length=200)
    className = models.CharField(db_column='className', max_length=200)
    level = models.IntegerField(default=0)
    adventuresPlayed = models.IntegerField(db_column='adventuresPlayed', default=0)
    validStarterAdventures = models.IntegerField(db_column='validStarterAdventures', default=0)
    isNovice = models.BooleanField(db_column='isNovice', default=False)
    registeredBy = models.CharField(db_column='registeredBy', max_length=200)
    createdAt = models.DateTimeField(db_column='createdAt')
    updatedAt = models.DateTimeField(db_column='updatedAt')

    class Meta:
        managed = False
        db_table = 'rpg_character_logs'
        verbose_name = 'Ficha de Personagem (Bot)'
        verbose_name_plural = 'Fichas de Personagens (Bot)'

    def __str__(self):
        return f"{self.characterName} ({self.discordUserTag}) - Nv.{self.level}"


class BotKeyValueStore(models.Model):
    id = models.CharField(primary_key=True, max_length=30)
    key = models.CharField(max_length=300, unique=True)
    value = models.JSONField()
    createdAt = models.DateTimeField(db_column='createdAt')
    updatedAt = models.DateTimeField(db_column='updatedAt')

    class Meta:
        managed = False
        db_table = 'store_keyvalue'
        verbose_name = 'KeyValue (Bot)'
        verbose_name_plural = 'KeyValue Store (Bot)'

    def __str__(self):
        return self.key
