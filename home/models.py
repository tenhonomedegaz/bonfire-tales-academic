





















import json
import uuid

from django.db import models
from django.utils import timezone
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError


# Personalização de perfil (F2). Limite de badges que o usuário fixa na vitrine.
BADGES_DESTAQUE_LIMITE = 6



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
    multiclass_armas = models.TextField(db_column='MulticlassArmas', blank=True, null=True)
    multiclass_ferramentas = models.TextField(db_column='MulticlassFerramentas', blank=True, null=True)
    multiclass_armaduras = models.TextField(db_column='MulticlassArmaduras', blank=True, null=True)
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tag da classe (hit-dice, saves-prof, skills-lvl1, subclass-choices, asi-choices, multiclass...).')



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
    nome_ingles = models.CharField(db_column='NomeIngles', max_length=200, blank=True, null=True)

    descricao = models.TextField(db_column='Descricao')  

    niveladquirido = models.IntegerField(db_column='NivelAdquirido')  

    table_only = models.BooleanField(db_column='TableOnly', default=False, help_text='Mostra esta habilidade apenas na tabela de progressao.')
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')



    class Meta:

        managed = True

        db_table = 'TB_ClasseHabilidade'
        verbose_name = 'Habilidade de Classe'
        verbose_name_plural = 'Habilidades de Classe'
        unique_together = (('id_classe', 'id_subclasse', 'nome', 'niveladquirido'),)

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
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')


    class Meta:

        managed = True

        db_table = 'TB_OpcaoJogo'
        verbose_name = 'Opção de Jogo'
        verbose_name_plural = 'Opções de Jogo'

    def __str__(self):
        return self.nome


class TbAntecedente(models.Model):
    id_antecedente = models.AutoField(db_column='Id_Antecedente', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    slug = models.CharField(db_column='Slug', max_length=150, unique=True)
    tipo = models.CharField(db_column='Tipo', max_length=100, default='Antecedente')
    pre_requisito = models.TextField(db_column='PreRequisito', blank=True, null=True)
    proficiencias = models.TextField(db_column='Proficiencias', blank=True, null=True)
    idiomas = models.TextField(db_column='Idiomas', blank=True, null=True)
    equipamento = models.TextField(db_column='Equipamento', blank=True, null=True)
    descricao = models.TextField(db_column='Descricao')
    resumo = models.TextField(db_column='Resumo', blank=True, null=True)
    etiquetas_adicionais = models.TextField(db_column='EtiquetasAdicionais', blank=True, null=True)
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')

    class Meta:
        db_table = 'backgrounds'
        verbose_name = 'Antecedente'
        verbose_name_plural = 'Antecedentes'

    def __str__(self):
        return self.nome


class TbRecursoclasse(models.Model):

    RESOURCE_TIPO_TABLE_ONLY = 'table-only'
    RESOURCE_TIPO_CONSUMABLE = 'consumable'
    RESOURCE_TIPO_CHOICE = 'choice'
    RESOURCE_TIPO_CHOICES = (
        (RESOURCE_TIPO_TABLE_ONLY, 'Apenas tabela'),
        (RESOURCE_TIPO_CONSUMABLE, 'Consumível'),
        (RESOURCE_TIPO_CHOICE, 'Escolha'),
    )

    id_recurso = models.AutoField(db_column='Id_Recurso', primary_key=True)  

    id_classe = models.ForeignKey(TbClasse, models.DO_NOTHING, db_column='Id_Classe')  

    id_subclasse = models.ForeignKey('TbSubclasse', models.DO_NOTHING, db_column='Id_Subclasse', blank=True, null=True)  

    nome = models.CharField(db_column='Nome')  

    slug = models.CharField(db_column='Slug')  

    nivel = models.IntegerField(db_column='Nivel', blank=True, null=True)

    valor = models.CharField(db_column='Valor', blank=True, null=True)

    valores_json = models.JSONField(db_column='ValoresJSON', blank=True, default=dict, help_text='Mapa nivel->valor, so os niveis onde o valor muda. Ex.: {"1":"2","5":"3"}.')
    tipo = models.CharField(db_column='Tipo', max_length=20, choices=RESOURCE_TIPO_CHOICES,
                            blank=True, default=RESOURCE_TIPO_TABLE_ONLY,
                            help_text="Papel do recurso no builder: 'table-only', 'consumable' ou 'choice'.")
    reset = models.CharField(db_column='Reset', max_length=20, blank=True, null=True,
                             help_text="Tipo de recuperação do recurso CONSUMÍVEL: 'long-rest', 'short-rest' ou 'short-or-long'. Vazio = stat derivado (não rastreável na ficha).")



    class Meta:

        managed = True

        db_table = 'TB_RecursoClasse'
        verbose_name = 'Recurso de Classe'
        verbose_name_plural = 'Recursos de Classe'
        unique_together = (('id_classe', 'id_subclasse', 'nome', 'nivel'),)

    def __str__(self):
        return f"{self.nome} - Nivel {self.nivel}"

    @property
    def tipo_efetivo(self):
        validos = {
            self.RESOURCE_TIPO_TABLE_ONLY,
            self.RESOURCE_TIPO_CONSUMABLE,
            self.RESOURCE_TIPO_CHOICE,
        }
        if self.tipo in validos:
            return self.tipo
        if self.reset:
            return self.RESOURCE_TIPO_CONSUMABLE
        return self.RESOURCE_TIPO_TABLE_ONLY

    @property
    def consumivel(self):
        return self.tipo_efetivo == self.RESOURCE_TIPO_CONSUMABLE

    @property
    def escolha(self):
        return self.tipo_efetivo == self.RESOURCE_TIPO_CHOICE

    @property
    def apenas_tabela(self):
        return self.tipo_efetivo == self.RESOURCE_TIPO_TABLE_ONLY





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

class TbContentRevision(models.Model):
    """Append-only mechanical content, independent from mutable catalog rows."""
    identity = models.CharField(max_length=200)
    checksum = models.CharField(max_length=64)
    payload = models.JSONField()
    dependencies = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['identity', 'checksum'],
                                               name='content_revision_identity_hash')]


class TbRuleset(models.Model):
    """Sealed manifest. Creation does not activate it for characters."""
    checksum = models.CharField(max_length=64, unique=True)
    manifest = models.JSONField()
    evaluator_version = models.CharField(max_length=80)
    vocabulary_version = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True)


class TbClassPublication(models.Model):
    """Current reviewed ruleset for new uses of one class."""
    id_classe = models.OneToOneField(TbClasse, on_delete=models.PROTECT,
                                     primary_key=True, related_name='publication')
    ruleset = models.ForeignKey(TbRuleset, on_delete=models.PROTECT)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'home_class_publication'


class TbClassPublicationLog(models.Model):
    id_classe = models.ForeignKey(TbClasse, on_delete=models.PROTECT)
    previous_ruleset = models.ForeignKey(TbRuleset, on_delete=models.PROTECT,
                                         null=True, related_name='+')
    new_ruleset = models.ForeignKey(TbRuleset, on_delete=models.PROTECT,
                                    related_name='+')
    actor_key_id = models.UUIDField(null=True)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'home_class_publication_log'


class TbRulesetContent(models.Model):
    ruleset = models.ForeignKey(TbRuleset, on_delete=models.PROTECT, related_name='entries')
    revision = models.ForeignKey(TbContentRevision, on_delete=models.PROTECT)
    identity = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['ruleset', 'identity'],
                                               name='ruleset_content_identity')]


class TbRaca(models.Model):
    id_raca = models.AutoField(db_column='Id_Raca', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=100)
    slug = models.CharField(db_column='Slug', max_length=100, unique=True)
    tagline = models.CharField(db_column='Tagline', max_length=255, blank=True, null=True)
    lore_presentation = models.TextField(db_column='LorePresentation', blank=True, null=True)
    lore_roleplay = models.TextField(db_column='LoreRoleplay', blank=True, null=True)
    lore_society = models.TextField(db_column='LoreSociety', blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    imagem_foco_x = models.PositiveSmallIntegerField(db_column='ImagemFocoX', default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Posição horizontal do ponto focal (0–100%).')
    imagem_foco_y = models.PositiveSmallIntegerField(db_column='ImagemFocoY', default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Posição vertical do ponto focal (0–100%).')
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
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    imagem_foco_x = models.PositiveSmallIntegerField(db_column='ImagemFocoX', default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Posição horizontal do ponto focal (0–100%).')
    imagem_foco_y = models.PositiveSmallIntegerField(db_column='ImagemFocoY', default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Posição vertical do ponto focal (0–100%).')

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
    tags_json = models.JSONField(
        db_column='TagsJSON',
        blank=True,
        default=list,
        help_text=(
            'Politicas mecanicas da essencia. Toda maldicao deve declarar '
            'suppress:pick{talento_racial, source:raca}.'
        ),
    )
    lore_presentation = models.TextField(db_column='LorePresentation', blank=True, null=True)
    lore_roleplay = models.TextField(db_column='LoreRoleplay', blank=True, null=True)
    lore_society = models.TextField(db_column='LoreSociety', blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    imagem_foco_x = models.PositiveSmallIntegerField(db_column='ImagemFocoX', default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Posição horizontal do ponto focal (0–100%).')
    imagem_foco_y = models.PositiveSmallIntegerField(db_column='ImagemFocoY', default=50, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Posição vertical do ponto focal (0–100%).')

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
    nome_ingles = models.CharField(db_column='NomeIngles', max_length=200, blank=True, null=True)
    descricao = models.TextField(db_column='Descricao')
    nivel_requisito = models.IntegerField(db_column='NivelRequisito', default=0)
    talento_racial = models.BooleanField(db_column='TalentoRacial', default=False, help_text='Marca tracos opcionais de raca que podem ser escolhidos como talentos raciais.')
    pre_requisito = models.TextField(db_column='PreRequisito', blank=True, null=True, help_text='Pre-requisito para talentos raciais opcionais.')
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')

    class Meta:
        db_table = 'TB_TracoRacial'
        verbose_name = 'Traço Racial'
        verbose_name_plural = 'Traços Raciais'

    def __str__(self):
        return self.nome


class TbMapLayer(models.Model):
    id_layer = models.IntegerField(db_column='Id_Layer', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    ordem = models.IntegerField(db_column='Ordem', default=0)
    publica = models.BooleanField(db_column='Publica', default=False)

    class Meta:
        db_table = 'TB_MapLayer'
        verbose_name = 'Camada de Mapa'
        verbose_name_plural = 'Camadas de Mapa'
        ordering = ['ordem']

    def __str__(self):
        return f"{self.nome} (Ordem: {self.ordem})"


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
    camada = models.IntegerField(db_column='Camada', default=0, help_text="Camada do mapa (0=Superficie, 1=Subterraneo Nivel 1, etc.)")
    
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
    camada = models.IntegerField(db_column='Camada', default=0, help_text="Camada do mapa (0=Superficie, 1=Subterraneo Nivel 1, etc.)")

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
    camada = models.IntegerField(db_column='Camada', default=0, help_text="Camada do mapa (0=Superficie, 1=Subterraneo Nivel 1, etc.)")
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


class TbOrganizacao(models.Model):
    id_organizacao = models.AutoField(db_column='Id_Organizacao', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=200)
    slug = models.SlugField(db_column='Slug', max_length=220, unique=True)
    tipo = models.CharField(db_column='Tipo', max_length=120, default='Organizacao')
    sede = models.CharField(db_column='Sede', max_length=220, blank=True, null=True)
    regioes = models.JSONField(db_column='Regioes', blank=True, null=True, default=list)
    territorios = models.JSONField(db_column='Territorios', blank=True, null=True, default=list)
    lideranca = models.TextField(db_column='Lideranca', blank=True, null=True)
    aliados = models.JSONField(db_column='Aliados', blank=True, null=True, default=list)
    inimigos = models.JSONField(db_column='Inimigos', blank=True, null=True, default=list)
    tags = models.JSONField(db_column='Tags', blank=True, null=True, default=list)
    descricao = models.TextField(db_column='Descricao', blank=True, null=True)
    created_at = models.DateTimeField(db_column='CreatedAt', auto_now_add=True)
    updated_at = models.DateTimeField(db_column='UpdatedAt', auto_now=True)

    class Meta:
        db_table = 'organizations'
        verbose_name = 'Organizacao'
        verbose_name_plural = 'Organizacoes'

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
    nome_ingles = models.CharField(db_column='NomeIngles', max_length=200, blank=True, null=True)
    slug = models.SlugField(db_column='Slug', max_length=150, unique=True, help_text="Ex: guerreiro-nato (usado para links)")
    tipo = models.CharField(db_column='Tipo', max_length=50, choices=TIPO_CHOICES, default='geral')
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')
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
        ('oculta', 'Oculta pela moderação'),
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
    revisao_edicao = models.JSONField(db_column='RevisaoEdicao', default=dict, blank=True)
    data_publicacao = models.DateTimeField(db_column='DataPublicacao', blank=True, null=True)
    destaque_editorial = models.BooleanField(db_column='DestaqueEditorial', default=False)

    class Meta:
        managed = True
        db_table = 'TB_Cronica'
        verbose_name = 'Crônica'
        verbose_name_plural = 'Crônicas'
        ordering = ['-data_submissao']
        permissions = [
            ('triage_tbcronica', 'Pode triar e encaminhar crônicas para Loremaster'),
        ]

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


class TbCronicaCurtida(models.Model):
    """Uma reação por leitor e crônica, separada das curtidas de perfil."""

    cronica = models.ForeignKey(TbCronica, on_delete=models.CASCADE,
                                related_name='curtidas', db_column='CronicaId')
    leitor = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                              related_name='cronicas_curtidas', db_column='LeitorId')
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)

    class Meta:
        db_table = 'TB_CronicaCurtida'
        constraints = [models.UniqueConstraint(
            fields=['cronica', 'leitor'], name='unique_cronica_curtida_leitor',
        )]


class TbCronicaNotificacao(models.Model):
    destinatario = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                                     related_name='cronica_notificacoes', db_column='DestinatarioId')
    cronica = models.ForeignKey(TbCronica, on_delete=models.CASCADE,
                                related_name='notificacoes', db_column='CronicaId')
    chave_evento = models.CharField(max_length=100, db_column='ChaveEvento')
    tipo = models.CharField(max_length=24, db_column='Tipo')
    texto = models.CharField(max_length=240, db_column='Texto')
    comentario = models.ForeignKey('TbCronicaComentario', on_delete=models.CASCADE,
                                   null=True, blank=True, db_column='ComentarioId')
    criada_em = models.DateTimeField(auto_now_add=True, db_column='CriadaEm')
    lida_em = models.DateTimeField(null=True, blank=True, db_column='LidaEm')

    class Meta:
        db_table = 'TB_CronicaNotificacao'
        ordering = ['-criada_em', '-pk']
        constraints = [models.UniqueConstraint(
            fields=['destinatario', 'chave_evento'], name='unique_cronica_notificacao_evento',
        )]


class TbCronicaComentario(models.Model):
    cronica = models.ForeignKey(TbCronica, on_delete=models.CASCADE,
                                related_name='comentarios', db_column='CronicaId')
    autor = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                             related_name='cronica_comentarios', db_column='AutorId')
    resposta_a = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True,
                                  related_name='respostas', db_column='RespostaAId')
    texto = models.TextField(db_column='Texto')
    estado = models.CharField(db_column='Estado', max_length=12, default='publico',
                              choices=[('publico', 'Público'), ('oculto', 'Oculto')])
    revisao = models.PositiveIntegerField(db_column='Revisao', default=1)
    historico_edicoes = models.JSONField(db_column='HistoricoEdicoes', default=list, blank=True)
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)
    editado_em = models.DateTimeField(db_column='EditadoEm', null=True, blank=True)
    chave_operacao = models.UUIDField(db_column='ChaveOperacao', unique=True)

    class Meta:
        db_table = 'TB_CronicaComentario'
        ordering = ['criado_em', 'pk']


class TbCronicaDenuncia(models.Model):
    cronica = models.ForeignKey(TbCronica, on_delete=models.CASCADE,
                                related_name='denuncias', db_column='CronicaId')
    comentario = models.ForeignKey(TbCronicaComentario, on_delete=models.CASCADE,
                                   null=True, blank=True, related_name='denuncias',
                                   db_column='ComentarioId')
    denunciante = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                                    related_name='cronica_denuncias', db_column='DenuncianteId')
    motivo = models.CharField(db_column='Motivo', max_length=500)
    alvo_snapshot = models.TextField(db_column='AlvoSnapshot')
    revisao_alvo = models.PositiveIntegerField(db_column='RevisaoAlvo', null=True, blank=True)
    estado = models.CharField(db_column='Estado', max_length=12, default='pendente',
                              choices=[('pendente', 'Pendente'), ('descartada', 'Descartada'),
                                       ('ocultada', 'Ocultada'), ('restaurada', 'Restaurada')])
    historico_decisoes = models.JSONField(db_column='HistoricoDecisoes', default=list, blank=True)
    decidido_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='cronica_denuncias_decididas',
                                     db_column='DecididoPorId')
    decisao_em = models.DateTimeField(db_column='DecisaoEm', null=True, blank=True)
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)

    class Meta:
        db_table = 'TB_CronicaDenuncia'
        constraints = [models.UniqueConstraint(
            fields=['cronica', 'comentario', 'denunciante'],
            name='unique_cronica_denuncia_comentario',
            condition=models.Q(comentario__isnull=False),
        ), models.UniqueConstraint(
            fields=['cronica', 'denunciante'],
            name='unique_cronica_denuncia_historia',
            condition=models.Q(comentario__isnull=True),
        )]


def _same_map_name(left, right):
    return (left or '').strip().casefold() == (right or '').strip().casefold()


def _first_marker_by_name(name):
    if not name:
        return None
    return TbMapMarker.objects.filter(nome__iexact=name).order_by('id_marker').first()


@receiver(pre_save, sender=TbRegiao)
def remember_region_map_keys(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_nome = None
        return
    old = sender.objects.filter(pk=instance.pk).only('nome').first()
    instance._old_nome = old.nome if old else None


@receiver(post_save, sender=TbRegiao)
def sync_region_to_marker(sender, instance, **kwargs):
    if kwargs.get('raw', False):
        return

    old_nome = getattr(instance, '_old_nome', None)
    marker = _first_marker_by_name(instance.nome)
    if marker is None and old_nome and not _same_map_name(old_nome, instance.nome):
        marker = _first_marker_by_name(old_nome)

    if marker is None:
        marker = TbMapMarker.objects.create(
            nome=instance.nome,
            lat=0,
            lng=0,
            categoria=instance.categoria or 'cidade',
            territorio=instance.territorio,
            camada=instance.camada,
        )
    else:
        marker.nome = instance.nome
        marker.territorio = instance.territorio
        marker.categoria = instance.categoria or 'cidade'
        marker.camada = instance.camada
        marker.save()

    if old_nome and not _same_map_name(old_nome, instance.nome):
        TbMapMarker.objects.filter(nome__iexact=old_nome).exclude(pk=marker.pk).delete()


@receiver(post_delete, sender=TbRegiao)
def delete_region_marker(sender, instance, **kwargs):
    if TbRegiao.objects.filter(nome__iexact=instance.nome).exists():
        return
    TbMapMarker.objects.filter(nome__iexact=instance.nome).delete()


@receiver(pre_save, sender=TbTerritorio)
def remember_territory_map_keys(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_nome = None
        return
    old = sender.objects.filter(pk=instance.pk).only('nome').first()
    instance._old_nome = old.nome if old else None


@receiver(post_save, sender=TbTerritorio)
def sync_territory_references(sender, instance, **kwargs):
    if kwargs.get('raw', False):
        return

    old_nome = getattr(instance, '_old_nome', None)
    if old_nome and not _same_map_name(old_nome, instance.nome):
        TbRegiao.objects.filter(territorio__iexact=old_nome).update(
            territorio=instance.nome,
            camada=instance.camada,
        )
        TbMapMarker.objects.filter(territorio__iexact=old_nome).update(
            territorio=instance.nome,
            camada=instance.camada,
        )
    else:
        TbRegiao.objects.filter(territorio__iexact=instance.nome).update(camada=instance.camada)
        TbMapMarker.objects.filter(territorio__iexact=instance.nome).update(camada=instance.camada)


@receiver(post_delete, sender=TbTerritorio)
def clear_deleted_territory_references(sender, instance, **kwargs):
    TbRegiao.objects.filter(territorio__iexact=instance.nome).update(territorio=None)
    TbMapMarker.objects.filter(territorio__iexact=instance.nome).update(territorio=None)

class TbItemMundano(models.Model):
    CATEGORIA_CHOICES = [
        ('arma', 'Arma'),
        ('armadura', 'Armadura'),
        ('ferramenta', 'Ferramenta'),
        ('municao', 'Munição'),
        ('foco', 'Foco de Conjuração'),
        ('pacote', 'Pacote'),
        ('montaria', 'Montaria'),
        ('veiculo', 'Veículo'),
        ('mercadoria', 'Mercadoria'),
        ('veneno', 'Veneno'),
        ('explosivo', 'Explosivo'),
        ('comida', 'Comida e Bebida'),
        ('equipamento_aventura', 'Equipamento de Aventura'),
    ]

    id_item = models.AutoField(db_column='Id_Item', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    slug = models.SlugField(db_column='Slug', max_length=150, unique=True)
    categoria = models.CharField(db_column='Categoria', max_length=50, choices=CATEGORIA_CHOICES, default='equipamento_aventura')
    subcategoria = models.CharField(db_column='Subcategoria', max_length=100, blank=True, null=True, help_text='Ex: arma_simples, escudo, ferramenta_artesao')
    peso = models.FloatField(db_column='Peso', blank=True, null=True, help_text='Peso em kg ou lbs')
    preco = models.CharField(db_column='Preco', max_length=50, blank=True, null=True, help_text='Ex: 5 PO')
    
    
    # Mecânica (dano, propriedades de arma, alcance, CA, força mínima, furtividade,
    # maestrias) vive em tags_json — o DSL componível. Ver home/item_mecanica.py.
    descricao_markdown = models.TextField(db_column='DescricaoMarkdown', blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')

    class Meta:
        db_table = 'TB_ItemMundano'
        verbose_name = 'Item Mundano'
        verbose_name_plural = 'Itens Mundanos'

    def __str__(self):
        return f"[{self.get_categoria_display()}] {self.nome}"


class TbItemMagico(models.Model):
    RARIDADE_CHOICES = [
        ('comum', 'Comum'),
        ('comum_menor', 'Comum Menor'),
        ('comum_maior', 'Comum Maior'),
        ('incomum', 'Incomum'),
        ('incomum_menor', 'Incomum Menor'),
        ('incomum_maior', 'Incomum Maior'),
        ('raro', 'Raro'),
        ('raro_menor', 'Raro Menor'),
        ('raro_maior', 'Raro Maior'),
        ('muito_raro', 'Muito Raro'),
        ('muito_raro_menor', 'Muito Raro Menor'),
        ('muito_raro_maior', 'Muito Raro Maior'),
        ('lendario', 'Lendário'),
        ('lendario_menor', 'Lendario Menor'),
        ('lendario_maior', 'Lendario Maior'),
        ('artefato', 'Artefato'),
    ]

    SLOT_CHOICES = [
        ('cabeca', 'Cabeça'),
        ('face_olhos', 'Face/Olhos'),
        ('rosto', 'Rosto'),
        ('pescoco', 'Pescoço'),
        ('costas', 'Costas'),
        ('torso', 'Torso'),
        ('bracos', 'Braços'),
        ('maos', 'Mãos'),
        ('dedos', 'Dedos'),
        ('aneis', 'Anéis'),
        ('cintura', 'Cintura'),
        ('pes', 'Pés'),
        ('pele', 'Pele'),
        ('arma', 'Arma'),
        ('armadura', 'Armadura'),
        ('escudo', 'Escudo'),
        ('municao', 'Munição'),
        ('pocao', 'Poção'),
        ('pergaminho', 'Pergaminho'),
        ('varinha', 'Varinha'),
        ('cajado_bastao', 'Cajado/Bastão'),
        ('veiculo', 'Veículo'),
        ('flutuando', 'Flutuando'),
        ('acessorio', 'Acessório'),
        ('edificacao', 'Edificação'),
        ('empunhado', 'Empunhado'),
        ('objeto', 'Objeto'),
        ('item_menor', 'Item Menor'),
    ]

    id_item = models.AutoField(db_column='Id_Item', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    nome_ingles = models.CharField(db_column='NomeIngles', max_length=200, blank=True, null=True)
    slug = models.SlugField(db_column='Slug', max_length=150, unique=True)
    raridade = models.CharField(db_column='Raridade', max_length=50, choices=RARIDADE_CHOICES, default='incomum')
    requer_sintonizacao = models.BooleanField(db_column='RequerSintonizacao', default=False)
    detalhes_sintonizacao = models.CharField(db_column='DetalhesSintonizacao', max_length=150, blank=True, null=True, help_text='Ex: por um mago')
    slot = models.CharField(db_column='Slot', max_length=50, choices=SLOT_CHOICES, default='objeto')
    loja = models.CharField(blank=True, db_column='Loja', help_text='Loja/caravana em que o item pode aparecer.', max_length=100, null=True)
    preco = models.DecimalField(blank=True, db_column='Preco', decimal_places=2, help_text='Preco em PO.', max_digits=12, null=True)
    tipo = models.CharField(db_column='Tipo', max_length=100, blank=True, null=True, help_text='Ex: Espada longa, Poção, Anel')
    
    descricao_markdown = models.TextField(db_column='DescricaoMarkdown', blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')

    class Meta:
        db_table = 'TB_ItemMagico'
        verbose_name = 'Item Mágico'
        verbose_name_plural = 'Itens Mágicos'

    def __str__(self):
        return f"[{self.get_raridade_display()}] {self.nome}"


class TbMagia(models.Model):
    id_magia = models.AutoField(db_column='Id_Magia', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=200)
    nome_ingles = models.CharField(db_column='NomeIngles', max_length=200, blank=True, null=True)
    slug = models.SlugField(db_column='Slug', max_length=220, unique=True)
    nivel = models.IntegerField(db_column='Nivel', default=0, help_text='Use 0 para truques.')
    casting_time = models.CharField(db_column='CastingTime', max_length=120, blank=True, null=True)
    ritual = models.BooleanField(db_column='Ritual', default=False)
    duracao = models.CharField(db_column='Duracao', max_length=200, blank=True, null=True)
    concentracao = models.BooleanField(db_column='Concentracao', default=False)
    escola = models.CharField(db_column='Escola', max_length=120, blank=True, null=True)
    alcance = models.CharField(db_column='Alcance', max_length=120, blank=True, null=True)
    componentes = models.CharField(db_column='Componentes', max_length=300, blank=True, null=True)
    classes = models.TextField(db_column='Classes', blank=True, null=True)
    classes_slugs = models.JSONField(
        db_column='ClassesSlugs', blank=True, default=list,
        help_text=(
            'Fonte mecanica do acesso base: slugs validos de TbClasse. '
            'O campo Classes permanece apenas como rotulo legivel e compatibilidade.'
        ),
    )
    descricao = models.TextField(db_column='Descricao', blank=True, null=True)
    em_niveis_superiores = models.TextField(db_column='EmNiveisSuperiores', blank=True, null=True)
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')

    class Meta:
        managed = True
        db_table = 'spells'
        verbose_name = 'Magia'
        verbose_name_plural = 'Magias'
        ordering = ['nivel', 'nome']

    def __str__(self):
        level = 'Truque' if self.nivel == 0 else f'Nivel {self.nivel}'
        return f"{self.nome} ({level})"


class UserProfile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    avatar_url = models.CharField(db_column='AvatarUrl', max_length=500, blank=True, null=True, help_text='URL da imagem de perfil.')
    banner_url = models.CharField(db_column='BannerUrl', max_length=500, blank=True, null=True, help_text='URL do banner do perfil. Aceita imagens animadas.')
    background_url = models.CharField(db_column='BackgroundUrl', max_length=500, blank=True, null=True, help_text='Imagem/GIF de fundo da pagina de perfil (cover, fixo).')
    bio = models.TextField(db_column='Bio', blank=True, null=True, help_text='Texto curto exibido no perfil publico.')
    profile_theme = models.CharField(db_column='ProfileTheme', max_length=40, default='bonfire', help_text='Tema visual do perfil.')
    theme_custom = models.JSONField(db_column='ThemeCustom', default=dict, blank=True, help_text='Cores do tema Personalizado (accent/accent2/surface/deep/gradiente).')
    avatar_frame = models.CharField(db_column='AvatarFrame', max_length=40, blank=True, null=True, help_text='Efeito de borda do avatar.')
    profile_effect = models.CharField(db_column='ProfileEffect', max_length=40, blank=True, null=True, help_text='Efeito visual do cartao de perfil.')
    vlibras_enabled = models.BooleanField(db_column='VlibrasEnabled', default=False, help_text='Habilita o plugin VLibras no site.')
    email_verified = models.BooleanField(db_column='EmailVerified', default=False,
                                         help_text='E-mail confirmado por link de verificação. Só e-mail verificado "trava" o uso por outra conta e vale para a cobrança.')
    # Vínculo com o Discord (OAuth2). discord_user_id é o vínculo FORTE com o bot
    # (BotMember), substituindo o casamento frágil por e-mail.
    discord_user_id = models.CharField(db_column='DiscordUserId', max_length=32, blank=True, null=True, unique=True)
    discord_username = models.CharField(db_column='DiscordUsername', max_length=80, blank=True, null=True)
    # Mercado de Mestre: carteira de Moedas de Mestragem (MM) + assinatura Mestre Ouro (5º slot).
    moedas_mestragem = models.IntegerField(db_column='MoedasMestragem', default=0)
    mm_ganhas_total = models.IntegerField(db_column='MmGanhasTotal', default=0,
                                          help_text='Total acumulado de MM GANHAS (p/ moedas de evento: 1 a cada 100).')
    moedas_evento = models.IntegerField(db_column='MoedasEvento', default=0,
                                        help_text='Moedas de Evento do mestre (resgatáveis em braseiros p/ um personagem).')
    mestre_ouro_ativo = models.BooleanField(db_column='MestreOuroAtivo', default=False,
                                            help_text='Assinatura Mestre Ouro ativa → +1 espaço de personagem.')
    mestre_ouro_proximo_pgto = models.DateField(db_column='MestreOuroProximoPgto', blank=True, null=True,
                                                help_text='Data da próxima mensalidade (500 MM).')
    # Personalização F2 — vitrine de badges/títulos (o que ESTÁ equipado; a posse
    # vive no inventário TbUsuarioCosmetico e nas badges derivadas computadas).
    titulo_equipado = models.CharField(db_column='TituloEquipado', max_length=60, blank=True, default='',
                                       help_text='Slug de um cosmético tipo=titulo equipado sob o nome.')
    badges_destaque = models.JSONField(db_column='BadgesDestaque', default=list, blank=True,
                                       help_text='Slugs de badges concedidas que o usuário fixa na vitrine (até 6).')
    badges_derivadas_ocultas = models.JSONField(
        db_column='BadgesDerivadasOcultas', default=list, blank=True,
        help_text='Badges automáticas opcionais que o usuário decidiu ocultar. Equipe nunca é ocultável.')

    class Meta:
        db_table = 'TB_UserProfile'
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'

    def __str__(self):
        return f"Perfil de {self.user.username}"

    def save(self, *args, **kwargs):
        # Normaliza badges_destaque: lista de slugs (strings), sem duplicatas,
        # cortada no limite. Nunca aceita tipos estranhos (blindagem de dado).
        raw = self.badges_destaque
        if not isinstance(raw, list):
            raw = []
        seen, limpos = set(), []
        for slug in raw:
            slug = str(slug).strip()
            if slug and slug not in seen:
                seen.add(slug)
                limpos.append(slug)
        self.badges_destaque = limpos[:BADGES_DESTAQUE_LIMITE]
        raw_ocultas = self.badges_derivadas_ocultas
        if not isinstance(raw_ocultas, list):
            raw_ocultas = []
        self.badges_derivadas_ocultas = list(dict.fromkeys(
            str(slug).strip() for slug in raw_ocultas
            if str(slug).strip() and str(slug).strip() != 'staff'
        ))
        self.titulo_equipado = (self.titulo_equipado or '').strip()
        super().save(*args, **kwargs)


class AsaasCheckoutOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        PAID = 'paid', 'Pago'
        ERROR = 'error', 'Erro'
        VALUE_MISMATCH = 'value_mismatch', 'Valor divergente'

    class Mode(models.TextChoices):
        SINGLE = 'single', 'Pagamento único'
        RECURRING = 'recurring', 'Assinatura recorrente'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT, blank=True, null=True,
                             related_name='asaas_checkout_orders')
    discord_user_id = models.CharField(max_length=32, blank=True, default='')
    email = models.EmailField(max_length=254, blank=True, default='')
    product_code = models.CharField(max_length=80)
    mode = models.CharField(max_length=12, choices=Mode.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.PENDING)
    asaas_checkout_id = models.CharField(max_length=100, blank=True, default='')
    asaas_checkout_url = models.URLField(max_length=500, blank=True, default='')
    asaas_payment_id = models.CharField(max_length=100, blank=True, default='')
    error_message = models.CharField(max_length=500, blank=True, default='')
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'home_asaascheckoutorder'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['discord_user_id', 'status']),
            models.Index(fields=['email', 'status']),
            models.Index(fields=['asaas_checkout_id']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(user__isnull=False)
                           | ~models.Q(discord_user_id='')
                           | ~models.Q(email='')),
                name='asaas_order_has_identity',
            ),
        ]

    @property
    def external_reference(self):
        return 'bonfire_order:%s' % self.pk

    def __str__(self):
        identity = self.user or self.discord_user_id or self.email
        return '%s - %s' % (self.product_code, identity)


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
    subscribedPlayers = models.JSONField(db_column='subscribedPlayers', default=list, blank=True)
    questPlayers = models.JSONField(db_column='questPlayers', default=list, blank=True)
    removedPlayers = models.TextField(db_column='removedPlayers', blank=True, null=True)
    participationRequests = models.JSONField(db_column='participationRequests', default=list, blank=True)
    createdBy = models.CharField(db_column='createdBy', max_length=200)
    isPublished = models.BooleanField(db_column='isPublished', default=False)
    status = models.CharField(max_length=50, default='idle')
    timeEvents = models.JSONField(db_column='timeEvents', default=list, blank=True)
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


# =====================================================================
# FICHA DE PERSONAGEM (criador de personagem)
# Tabelas novas, gerenciadas pelo Django (managed=True). A identidade
# racial e de classe referencia o conteudo existente via FK.
# Ver docs/criador-personagem/vocabulario-tags-json.md
# =====================================================================

class TbPersonagem(models.Model):
    id_personagem = models.AutoField(db_column='Id_Personagem', primary_key=True)
    dono = models.ForeignKey('auth.User', models.CASCADE, db_column='Dono', related_name='personagens')
    nome = models.CharField(db_column='Nome', max_length=150)
    publico = models.BooleanField(db_column='Publico', default=False)
    arquivado = models.BooleanField(db_column='Arquivado', default=False, db_index=True,
                                    help_text='No cofre: guardado, não conta no limite de slots ativos.')

    # Identidade racial (conteudo existente)
    id_raca = models.ForeignKey('TbRaca', models.SET_NULL, db_column='Id_Raca', blank=True, null=True)
    id_linhagem = models.ForeignKey('TbLinhagem', models.SET_NULL, db_column='Id_Linhagem', blank=True, null=True)
    id_essencia = models.ForeignKey('TbEssencia', models.SET_NULL, db_column='Id_Essencia', blank=True, null=True)
    id_antecedente = models.ForeignKey('TbAntecedente', models.SET_NULL, db_column='Id_Antecedente', blank=True, null=True)

    # Atributos
    forca = models.IntegerField(db_column='Forca', default=10)
    destreza = models.IntegerField(db_column='Destreza', default=10)
    constituicao = models.IntegerField(db_column='Constituicao', default=10)
    inteligencia = models.IntegerField(db_column='Inteligencia', default=10)
    sabedoria = models.IntegerField(db_column='Sabedoria', default=10)
    carisma = models.IntegerField(db_column='Carisma', default=10)

    # Vitais / combate (nivel e total; PV/CA podem ser derivados, mas guardamos o estado)
    nivel = models.IntegerField(db_column='Nivel', default=1)
    pv_maximo = models.IntegerField(db_column='PVMaximo', default=0)
    pv_atual = models.IntegerField(db_column='PVAtual', default=0)
    pv_temporario = models.IntegerField(db_column='PVTemporario', default=0)
    ca = models.IntegerField(db_column='CA', default=10)
    iniciativa_bonus = models.IntegerField(db_column='IniciativaBonus', default=0)
    velocidade = models.CharField(db_column='Velocidade', max_length=50, blank=True, default='9 m / 30 ft')
    carteira_pc = models.IntegerField(db_column='CarteiraPC', default=0,
                                      help_text='Dinheiro em peças de cobre (1 PO = 100 PC, 1 PP = 10 PC, 1 PL = 1000 PC).')
    # Progressão por aventuras (Bonfire): nº de aventuras define o nível-TETO + rank;
    # cada aventura credita ouro (por rank) e braseiros (= BP). Lançado por staff.
    aventuras = models.IntegerField(db_column='Aventuras', default=0,
                                    help_text='Aventuras jogadas → define nível-teto e rank (tabela Bonfire).')
    braseiros = models.IntegerField(db_column='Braseiros', default=0,
                                    help_text='Moeda do jogador (ganha por aventura/evento, = BP por aventura).')

    # Bio / narrativa
    tagline = models.CharField(db_column='Tagline', max_length=255, blank=True, null=True)
    jogador = models.CharField(db_column='Jogador', max_length=150, blank=True, null=True)
    patente = models.CharField(db_column='Patente', max_length=100, blank=True, null=True)
    idade = models.CharField(db_column='Idade', max_length=30, blank=True, null=True)
    altura = models.CharField(db_column='Altura', max_length=30, blank=True, null=True)
    peso = models.CharField(db_column='Peso', max_length=30, blank=True, null=True)
    tamanho = models.CharField(db_column='Tamanho', max_length=30, blank=True, null=True)
    genero = models.CharField(db_column='Genero', max_length=50, blank=True, null=True)
    olhos = models.CharField(db_column='Olhos', max_length=50, blank=True, null=True)
    cabelo = models.CharField(db_column='Cabelo', max_length=50, blank=True, null=True)
    pele = models.CharField(db_column='Pele', max_length=50, blank=True, null=True)
    aparencia = models.TextField(db_column='Aparencia', blank=True, null=True)
    historia = models.TextField(db_column='Historia', blank=True, null=True)
    anotacoes = models.TextField(db_column='Anotacoes', blank=True, null=True)
    # Onda F: bloco de mesa da ABA FICHA (rascunho de sessão, salvo no blur). Não confundir
    # com `anotacoes`, que é o campo de lore da aba Informações — este fica ao lado da
    # Personalidade, na folha, e por isso nunca é nulo (string vazia = sem nota).
    notas_jogador = models.TextField(db_column='NotasJogador', blank=True, default='',
                                     help_text='Notas de mesa do jogador, exibidas na aba Ficha (a lore fica em Anotacoes).')
    foto_url = models.CharField(db_column='FotoUrl', max_length=500, blank=True, null=True, help_text='Link da imagem do retrato do personagem.')
    token_url = models.CharField(db_column='TokenUrl', max_length=500, blank=True, null=True, help_text='Link da imagem do token do personagem.')
    banner_url = models.CharField(db_column='BannerUrl', max_length=500, blank=True, null=True, help_text='Link do banner visual da ficha. Aceita imagens animadas.')
    ficha_background_url = models.CharField(db_column='FichaBackgroundUrl', max_length=500, blank=True, null=True, help_text='Imagem/GIF de fundo da pagina da ficha (cover, fixo).')
    ficha_theme = models.CharField(db_column='FichaTheme', max_length=40, default='bonfire', help_text='Tema visual da ficha.')
    ficha_theme_custom = models.JSONField(db_column='FichaThemeCustom', default=dict, blank=True, help_text='Cores do tema Personalizado da ficha (accent/accent2/surface/deep/gradiente).')
    foto_frame = models.CharField(db_column='FotoFrame', max_length=40, blank=True, null=True, help_text='Efeito de borda do retrato/token.')
    ficha_effect = models.CharField(db_column='FichaEffect', max_length=40, blank=True, null=True, help_text='Efeito visual do cabecalho da ficha.')

    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)
    atualizado_em = models.DateTimeField(db_column='AtualizadoEm', auto_now=True)

    class Meta:
        db_table = 'TB_Personagem'
        verbose_name = 'Personagem'
        verbose_name_plural = 'Personagens'

    def __str__(self):
        return self.nome


class TbPersonagemClasse(models.Model):
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='classes')
    id_classe = models.ForeignKey('TbClasse', models.PROTECT, db_column='Id_Classe')
    id_subclasse = models.ForeignKey('TbSubclasse', models.SET_NULL, db_column='Id_Subclasse', blank=True, null=True)
    ruleset = models.ForeignKey(TbRuleset, models.PROTECT, db_column='Id_Ruleset',
                                blank=True, null=True, related_name='character_classes')
    nivel = models.IntegerField(db_column='Nivel', default=1)
    principal = models.BooleanField(db_column='Principal', default=False, help_text='Classe inicial (define dado de vida base, etc.).')

    class Meta:
        db_table = 'TB_PersonagemClasse'
        verbose_name = 'Classe do Personagem'
        verbose_name_plural = 'Classes do Personagem'

    def __str__(self):
        return f'{self.id_personagem_id} - {self.id_classe_id} Nv{self.nivel}'


class TbPersonagemCacador(models.Model):
    """Rework preparation, explicitly bound; legacy characters have no row."""
    personagem_classe = models.OneToOneField(
        TbPersonagemClasse, on_delete=models.CASCADE, related_name='cacador_rework')
    ruleset = models.ForeignKey(TbRuleset, on_delete=models.PROTECT)
    ability = models.CharField(max_length=3, choices=[('int', 'Inteligência'), ('wis', 'Sabedoria')])
    selected = models.JSONField(default=list)
    mark = models.JSONField(default=dict)
    companion = models.JSONField(default=dict)
    awakening = models.JSONField(default=dict)
    exorcist = models.JSONField(default=dict)
    traveler = models.JSONField(default=dict)
    mutagens = models.JSONField(default=dict)
    regularization = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ability__in=['int', 'wis']),
                                               name='hunter_valid_ability')]


class TbPersonagemPericia(models.Model):
    id_pericia = models.AutoField(db_column='Id_Pericia', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='pericias')
    nome = models.CharField(db_column='Nome', max_length=50)
    atributo = models.CharField(db_column='Atributo', max_length=3)
    proficiente = models.BooleanField(db_column='Proficiente', default=False)
    expertise = models.BooleanField(db_column='Expertise', default=False)

    class Meta:
        db_table = 'TB_PersonagemPericia'
        unique_together = (('id_personagem', 'nome'),)


class TbPersonagemEscolha(models.Model):
    """Slots genericos de pick: (pericia, opcao:<tipo>, idioma, lista definida, etc.)."""
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='escolhas')
    origem = models.CharField(db_column='Origem', max_length=150, help_text='Habilidade/traco que concedeu o pick.')
    tipo = models.CharField(db_column='Tipo', max_length=60, help_text='Tipo do pick (pericia, opcao:metamagia, aspecto-selvagem...).')
    slot = models.IntegerField(db_column='Slot', default=0)
    id_opcao = models.ForeignKey('TbOpcaojogo', models.SET_NULL, db_column='Id_Opcao', blank=True, null=True)
    valor = models.CharField(db_column='Valor', max_length=200, blank=True, null=True, help_text='Texto livre quando nao ha catalogo.')

    class Meta:
        db_table = 'TB_PersonagemEscolha'
        unique_together = (('id_personagem', 'origem', 'tipo', 'slot'),)


class TbPersonagemMagia(models.Model):
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='magias')
    id_magia = models.ForeignKey('TbMagia', models.SET_NULL, db_column='Id_Magia', blank=True, null=True)
    nivel = models.IntegerField(db_column='Nivel', default=0)
    nome = models.CharField(db_column='Nome', max_length=200)
    preparada = models.BooleanField(db_column='Preparada', default=False)
    sempre_preparada = models.BooleanField(db_column='SemprePreparada', default=False)
    origem = models.CharField(db_column='Origem', max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'TB_PersonagemMagia'


class TbPersonagemMagiaAssinatura(models.Model):
    """Personalizacao de uma magia-base criada por uma feature ``spellcraft``."""
    id_assinatura = models.AutoField(
        db_column='Id_Assinatura', primary_key=True)
    id_personagem = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Personagem',
        related_name='magias_assinatura')
    id_magia_personagem = models.OneToOneField(
        'TbPersonagemMagia', models.CASCADE, db_column='Id_PersonagemMagia',
        related_name='assinatura')
    id_magia_base = models.ForeignKey(
        'TbMagia', models.PROTECT, db_column='Id_MagiaBase',
        related_name='assinaturas_personagem')
    id_classe = models.ForeignKey(
        'TbClasse', models.PROTECT, db_column='Id_Classe',
        related_name='magias_assinatura_personagem')
    slot = models.PositiveSmallIntegerField(db_column='Slot')
    nome = models.CharField(db_column='Nome', max_length=200)
    nivel_base = models.PositiveSmallIntegerField(db_column='NivelBase')
    nivel_final = models.PositiveSmallIntegerField(db_column='NivelFinal')
    modificacoes_json = models.JSONField(
        db_column='ModificacoesJSON', blank=True, default=dict)
    ultima_reforma_nivel = models.PositiveSmallIntegerField(
        db_column='UltimaReformaNivel', default=0)
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)
    atualizado_em = models.DateTimeField(db_column='AtualizadoEm', auto_now=True)

    class Meta:
        db_table = 'TB_PersonagemMagiaAssinatura'
        ordering = ('slot', 'id_assinatura')
        constraints = [
            models.UniqueConstraint(
                fields=('id_personagem', 'id_classe', 'slot'),
                name='uniq_magia_assinatura_personagem_classe_slot'),
        ]


class TbPersonagemTalento(models.Model):
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='talentos')
    id_talento = models.ForeignKey('TbTalento', models.SET_NULL, db_column='Id_Talento', blank=True, null=True)
    categoria = models.CharField(db_column='Categoria', max_length=20, blank=True, null=True)
    nivel = models.IntegerField(db_column='Nivel', blank=True, null=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    detalhes = models.CharField(db_column='Detalhes', max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'TB_PersonagemTalento'


class TbPersonagemProficiencia(models.Model):
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='proficiencias')
    tipo = models.CharField(db_column='Tipo', max_length=20, help_text='idioma / ferramenta / arma / armadura')
    nome = models.CharField(db_column='Nome', max_length=100)
    origem = models.CharField(db_column='Origem', max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'TB_PersonagemProficiencia'


class TbPersonagemTreinamento(models.Model):
    """Treinamento pago no Mercado; a proficiencia nasce somente no vencimento."""

    TIPO_CHOICES = [('idioma', 'Idioma'), ('ferramenta', 'Ferramenta')]
    STATUS_CHOICES = [
        ('ativo', 'Em andamento'),
        ('concluido', 'Concluido'),
        ('cancelado', 'Cancelado'),
    ]

    id_treinamento = models.AutoField(
        db_column='Id_Treinamento', primary_key=True)
    id_personagem = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Personagem',
        related_name='treinamentos_mercado')
    tipo = models.CharField(
        db_column='Tipo', max_length=20, choices=TIPO_CHOICES)
    nome = models.CharField(db_column='Nome', max_length=100)
    custo_pc = models.PositiveIntegerField(db_column='CustoPC', default=10000)
    status = models.CharField(
        db_column='Status', max_length=12, choices=STATUS_CHOICES,
        default='ativo', db_index=True)
    iniciado_em = models.DateTimeField(db_column='IniciadoEm', auto_now_add=True)
    conclui_em = models.DateTimeField(db_column='ConcluiEm', db_index=True)
    concluido_em = models.DateTimeField(
        db_column='ConcluidoEm', blank=True, null=True)

    class Meta:
        db_table = 'TB_PersonagemTreinamento'
        ordering = ('-iniciado_em', '-id_treinamento')
        constraints = [
            models.UniqueConstraint(
                fields=('id_personagem',), condition=models.Q(status='ativo'),
                name='uniq_treinamento_ativo_personagem'),
        ]

    def __str__(self):
        return '%s: %s (%s)' % (self.id_personagem, self.nome, self.status)


class TbPersonagemItem(models.Model):
    ORIGEM_CHOICES = [
        ('legado', 'Legado'),
        ('criacao', 'Criacao de ficha'),
        ('compra', 'Compra oficial'),
        ('comunidade', 'Mercado da comunidade'),
        ('oficina', 'Oficina de Magia'),
        ('concessao', 'Concessao da staff'),
        ('pathbuilder', 'Pathbuilder'),
    ]
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='inventario')
    qtd = models.IntegerField(db_column='Qtd', default=1)
    nome = models.CharField(db_column='Nome', max_length=200)
    custo = models.CharField(db_column='Custo', max_length=30, blank=True, null=True)
    peso = models.CharField(db_column='Peso', max_length=20, blank=True, null=True)
    equipado = models.BooleanField(db_column='Equipado', default=False)
    sintonizado = models.BooleanField(db_column='Sintonizado', default=False)
    # Mecânica do item equipado (CA/dano/propriedades) vive em tags_json — o snapshot
    # antigo (tipo_equip/ca_base/ca_limite_des) foi migrado pra cá. Ver item_mecanica.py.
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list,
                                 help_text='Snapshot da mecânica do item equipado (CA/dano/propriedades). Fonte única da mecânica.')
    # Vínculo ao catálogo mundano. O snapshot acima continua sendo a fonte estável da
    # posse: se o catálogo for substituído durante uma sincronização, SET_NULL preserva
    # o item que já estava no inventário do personagem.
    id_item_mundano = models.ForeignKey(
        'TbItemMundano', models.SET_NULL, db_column='IdItemMundano', blank=True,
        null=True, related_name='posses')
    # Vínculo ao catálogo de itens mágicos: traz tags_json (efeitos), raridade e
    # requer_sintonizacao. Itens mundanos ficam com este campo nulo.
    id_item_magico = models.ForeignKey('TbItemMagico', models.SET_NULL, db_column='Id_ItemMagico',
                                       blank=True, null=True, related_name='posses')
    # Trilha de CONCESSÃO pela staff (item de missão/recompensa que não tem preço e por
    # isso não pode ser comprado). Linhas COMPRADAS/normais ficam com estes campos nulos;
    # linhas CONCEDIDAS registram quem/quando/origem (ex.: nome da missão). Isso dá a
    # trilha e a reversão SEM tabela nova — a própria linha de inventário é o registro,
    # espelhando a filosofia enxuta do ledger de aventuras.
    concedido_por = models.ForeignKey('auth.User', models.SET_NULL, db_column='ConcedidoPor',
                                      blank=True, null=True, related_name='itens_concedidos')
    concedido_em = models.DateTimeField(db_column='ConcedidoEm', blank=True, null=True, db_index=True)
    origem_nota = models.CharField(db_column='OrigemNota', max_length=255, blank=True, default='',
                                   help_text='Origem da concessão (ex.: nome da missão).')

    origem_tipo = models.CharField(
        db_column='OrigemTipo', max_length=20, choices=ORIGEM_CHOICES,
        default='legado', db_index=True,
        help_text='Origem auditavel da linha para rebuild e reembolso seguro.',
    )

    class Meta:
        db_table = 'TB_PersonagemItem'


class TbAnuncioItemMagico(models.Model):
    """Mercado da Comunidade: um personagem anuncia um item mágico que não usa mais e
    vende pelo PREÇO DE VENDA do mercado. Ao anunciar, o item sai do inventário do
    vendedor (escrow via snapshot); ao comprar, é recriado no inventário do comprador."""
    STATUS_CHOICES = [('ativo', 'Ativo'), ('vendido', 'Vendido'), ('cancelado', 'Cancelado')]
    id = models.AutoField(db_column='Id', primary_key=True)
    vendedor = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Vendedor', related_name='anuncios')
    id_item_magico = models.ForeignKey('TbItemMagico', models.SET_NULL, db_column='Id_ItemMagico', blank=True, null=True)
    nome = models.CharField(db_column='Nome', max_length=200)
    custo = models.CharField(db_column='Custo', max_length=30, blank=True, null=True, help_text='Custo de compra original (snapshot).')
    preco_pc = models.IntegerField(db_column='PrecoPC', default=0, help_text='Preço de venda em peças de cobre.')
    status = models.CharField(db_column='Status', max_length=12, choices=STATUS_CHOICES, default='ativo')
    comprador = models.ForeignKey('TbPersonagem', models.SET_NULL, db_column='Id_Comprador', blank=True, null=True, related_name='compras_comunidade')
    estado_json = models.JSONField(
        db_column='EstadoJSON', blank=True, default=dict,
        help_text='Snapshot de estado persistente da instancia, como cargas restantes.')
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)
    vendido_em = models.DateTimeField(db_column='VendidoEm', blank=True, null=True)

    class Meta:
        db_table = 'TB_AnuncioItemMagico'
        verbose_name = 'Anúncio (Mercado da Comunidade)'
        verbose_name_plural = 'Anúncios (Mercado da Comunidade)'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.nome} ({self.get_status_display()})'


class TbTransacao(models.Model):
    """Histórico de movimentos da carteira (PC) de um personagem: compras, vendas e
    negociações do Mercado da Comunidade. `valor_pc` é ASSINADO (+ recebeu / − gastou);
    `saldo_pc` = carteira logo após o movimento."""
    TIPO_CHOICES = [('compra', 'Compra'), ('venda', 'Venda'),
                    ('mercado-compra', 'Compra (Comunidade)'), ('mercado-venda', 'Venda (Comunidade)'),
                    ('aventura', 'Ouro de aventura'), ('inicial', 'Saldo inicial'),
                    ('treinamento', 'Treinamento'), ('emprestimo', 'Emprestimo'),
                    ('repasse-divida', 'Repasse de divida'), ('ajuste', 'Ajuste'),
                    ('recompensa-social', 'Recompensa comunitária')]
    id_transacao = models.AutoField(db_column='Id_Transacao', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='transacoes')
    tipo = models.CharField(db_column='Tipo', max_length=20, choices=TIPO_CHOICES, default='ajuste')
    descricao = models.CharField(db_column='Descricao', max_length=255, blank=True, null=True)
    valor_pc = models.IntegerField(db_column='ValorPC', default=0, help_text='Assinado: + recebido, − gasto (em peças de cobre).')
    saldo_pc = models.IntegerField(db_column='SaldoPC', default=0, help_text='Carteira (PC) após o movimento.')
    detalhes_json = models.JSONField(
        db_column='DetalhesJSON', default=dict, blank=True,
        help_text='Vinculo auditavel com item, quantidade e contexto da operacao.',
    )
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)
    revertida = models.BooleanField(db_column='Revertida', default=False, db_index=True)
    revertida_em = models.DateTimeField(db_column='RevertidaEm', blank=True, null=True)
    revertida_por = models.ForeignKey(
        'auth.User', models.SET_NULL, db_column='RevertidaPor', blank=True, null=True,
        related_name='transacoes_personagem_revertidas',
    )

    class Meta:
        db_table = 'TB_Transacao'
        verbose_name = 'Transação'
        verbose_name_plural = 'Transações'
        ordering = ['-criado_em', '-id_transacao']

    def __str__(self):
        return f'{self.get_tipo_display()} {self.valor_pc} PC'


class TbEmprestimoPersonagem(models.Model):
    """Proposta e contrato de emprestimo entre dois personagens."""

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('ativo', 'Ativo'),
        ('quitado', 'Quitado'),
        ('recusado', 'Recusado'),
        ('cancelado', 'Cancelado'),
    ]

    id_emprestimo = models.AutoField(
        db_column='Id_Emprestimo', primary_key=True)
    credor = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Credor',
        related_name='emprestimos_concedidos')
    devedor = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Devedor',
        related_name='emprestimos_recebidos')
    proponente = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Proponente',
        related_name='propostas_emprestimo')
    valor_original_pc = models.PositiveIntegerField(db_column='ValorOriginalPC')
    valor_total_pc = models.PositiveIntegerField(db_column='ValorTotalPC')
    valor_pago_pc = models.PositiveIntegerField(db_column='ValorPagoPC', default=0)
    status = models.CharField(
        db_column='Status', max_length=12, choices=STATUS_CHOICES,
        default='pendente', db_index=True)
    multa_aplicada = models.BooleanField(db_column='MultaAplicada', default=False)
    solicitado_em = models.DateTimeField(db_column='SolicitadoEm', auto_now_add=True)
    aceito_em = models.DateTimeField(db_column='AceitoEm', blank=True, null=True)
    vence_em = models.DateTimeField(
        db_column='VenceEm', blank=True, null=True, db_index=True)
    encerrado_em = models.DateTimeField(db_column='EncerradoEm', blank=True, null=True)

    class Meta:
        db_table = 'TB_EmprestimoPersonagem'
        ordering = ('-solicitado_em', '-id_emprestimo')
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(credor=models.F('devedor')),
                name='emprestimo_credor_devedor_distintos'),
            models.CheckConstraint(
                condition=models.Q(valor_original_pc__gt=0),
                name='emprestimo_valor_original_positivo'),
        ]

    @property
    def saldo_devedor_pc(self):
        return max(0, int(self.valor_total_pc or 0) - int(self.valor_pago_pc or 0))

    @property
    def inadimplente(self):
        return bool(self.status == 'ativo' and self.multa_aplicada)

    def __str__(self):
        return '%s -> %s (%s)' % (self.credor, self.devedor, self.status)


class TbSolicitacaoTranscricao(models.Model):
    """Pedido auditavel para copiar uma magia do grimorio de outro jogador."""

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('aceita', 'Aceita'),
        ('recusada', 'Recusada'),
        ('cancelada', 'Cancelada'),
        ('invalida', 'Invalidada'),
    ]

    id_solicitacao = models.AutoField(db_column='Id_Solicitacao', primary_key=True)
    solicitante = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Solicitante',
        related_name='solicitacoes_transcricao_enviadas')
    fonte = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Fonte',
        related_name='solicitacoes_transcricao_recebidas')
    magia = models.ForeignKey(
        'TbMagia', models.PROTECT, db_column='Id_Magia',
        related_name='solicitacoes_transcricao')
    classe_solicitante = models.ForeignKey(
        'TbClasse', models.PROTECT, db_column='Id_ClasseSolicitante',
        related_name='solicitacoes_transcricao')
    status = models.CharField(
        db_column='Status', max_length=12, choices=STATUS_CHOICES,
        default='pendente', db_index=True)
    custo_po = models.DecimalField(
        db_column='CustoPO', max_digits=10, decimal_places=2, default=0)
    tempo_horas = models.DecimalField(
        db_column='TempoHoras', max_digits=8, decimal_places=2, default=0)
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)
    respondido_em = models.DateTimeField(db_column='RespondidoEm', blank=True, null=True)
    respondido_por = models.ForeignKey(
        'auth.User', models.SET_NULL, db_column='RespondidoPor', blank=True, null=True,
        related_name='solicitacoes_transcricao_respondidas')
    detalhes_json = models.JSONField(db_column='DetalhesJSON', default=dict, blank=True)

    class Meta:
        db_table = 'TB_SolicitacaoTranscricao'
        verbose_name = 'Solicitacao de transcricao'
        verbose_name_plural = 'Solicitacoes de transcricao'
        ordering = ['-criado_em', '-id_solicitacao']
        constraints = [
            models.UniqueConstraint(
                fields=['solicitante', 'fonte', 'magia', 'classe_solicitante'],
                condition=models.Q(status='pendente'),
                name='uniq_transcricao_pendente',
            ),
        ]

    def __str__(self):
        return f'{self.solicitante} <- {self.fonte}: {self.magia} ({self.status})'


class TbPersonagemRevisao(models.Model):
    """Snapshot mecanico anterior a uma mudanca reversivel da build.

    Dinheiro, aventuras, narrativa e cosmeticos ficam fora do snapshot. Assim, restaurar
    uma build nao sobrescreve memoria de jogo pertencente a outros fluxos.
    """
    TIPO_CHOICES = [
        ('nivel_1', 'Recriacao do nivel 1'),
        ('level_up', 'Subida de nivel'),
    ]
    id_revisao = models.AutoField(db_column='Id_Revisao', primary_key=True)
    id_personagem = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='revisoes_build')
    tipo = models.CharField(db_column='Tipo', max_length=20, choices=TIPO_CHOICES)
    descricao = models.CharField(db_column='Descricao', max_length=255, blank=True, default='')
    snapshot_json = models.JSONField(db_column='SnapshotJSON', default=dict)
    nivel_antes = models.IntegerField(db_column='NivelAntes', default=1)
    nivel_depois = models.IntegerField(db_column='NivelDepois', default=1)
    aventuras_no_momento = models.IntegerField(db_column='AventurasNoMomento', default=0)
    aventura_marker_id = models.IntegerField(db_column='AventuraMarkerId', blank=True, null=True)
    criado_por = models.ForeignKey(
        'auth.User', models.SET_NULL, db_column='CriadoPor', blank=True, null=True,
        related_name='revisoes_personagem_criadas')
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True, db_index=True)
    revertida = models.BooleanField(db_column='Revertida', default=False, db_index=True)
    revertida_em = models.DateTimeField(db_column='RevertidaEm', blank=True, null=True)
    revertida_por = models.ForeignKey(
        'auth.User', models.SET_NULL, db_column='RevertidaPor', blank=True, null=True,
        related_name='revisoes_personagem_revertidas')

    class Meta:
        db_table = 'TB_PersonagemRevisao'
        verbose_name = 'Revisao de build'
        verbose_name_plural = 'Revisoes de build'
        ordering = ['-criado_em', '-id_revisao']

    def __str__(self):
        return '%s: %s' % (self.id_personagem, self.get_tipo_display())


class TbPersonagemAventura(models.Model):
    """Ledger de LANÇAMENTOS de aventuras que a staff registra num personagem. Cada linha
    é um `personagem_registrar_aventuras`: dá NOME ao lançamento e habilita ROLLBACK de um
    lançamento errado. Guarda o que AQUELE lançamento pagou (aventuras, ouro em PC, braseiros)
    para que o estorno devolva exatamente isso — NÃO altera a matemática de ouro/nível de
    `aplicar_aventuras`, só registra.

    Onda E (Ficha v2): a linha passa a ser o registro COMPLETO da missão — `data_missao`
    (quando a mesa aconteceu, ≠ `criado_em`, que é quando a staff lançou), `id_mestre`
    (o mestre que conduziu, do cadastro real do Mercado de Mestre = `auth.User`) e
    `detalhes_json` (consumos da missão + trilha de edição). 1 linha/missão continua sendo
    a unidade auditável; nada de JSON no personagem."""
    id_lancamento = models.AutoField(db_column='Id_Lancamento', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem',
                                      related_name='aventuras_ledger')
    nome_aventura = models.CharField(db_column='NomeAventura', max_length=200,
                                     help_text='Nome da mesa/aventura lançada (obrigatório).')
    origem = models.CharField(max_length=32, default='mesa', choices=[
        ('mesa', 'Mesa jogada'), ('recompensa_comunidade', 'Recompensa comunitária'),
    ], db_index=True)
    qtd_aventuras = models.IntegerField(db_column='QtdAventuras', default=0,
                                        help_text='Quantas aventuras ESTE lançamento adicionou.')
    ouro_pago_pc = models.IntegerField(db_column='OuroPagoPC', default=0,
                                       help_text='Ouro creditado por ESTE lançamento, em peças de cobre (o estorno remove isto).')
    braseiros_pago = models.IntegerField(db_column='BraseirosPago', default=0,
                                         help_text='Braseiros creditados por ESTE lançamento (missão de evento).')
    nivel_no_lancamento = models.IntegerField(db_column='NivelNoLancamento', default=1,
                                              help_text='Nível do personagem no momento do lançamento.')
    data_missao = models.DateField(db_column='DataMissao', blank=True, null=True, db_index=True,
                                   help_text='Data em que a MISSÃO aconteceu (≠ CriadoEm, que é a data do lançamento). '
                                             'Linhas legadas ficam nulas; lançamento novo preenche.')
    # Mestre que conduziu a missão. O "cadastro de mestres" já existe e é `auth.User` — é o
    # mesmo alvo de TbAventuraMestre.mestre / TbTransacaoMestre.mestre no Mercado de Mestre.
    # No SCHEMA é nulo (o legado não tinha esse dado) e PROTECT (mestre com lançamento não
    # é apagável); na CAMADA DE APLICAÇÃO é obrigatório para criar/editar lançamento novo.
    id_mestre = models.ForeignKey('auth.User', models.PROTECT, db_column='Id_Mestre',
                                  related_name='aventuras_mestradas_ledger', blank=True, null=True,
                                  help_text='Mestre da missão (cadastro do Mercado de Mestre). '
                                            'Nulo só em linha LEGADA, anterior à onda E.')
    detalhes_json = models.JSONField(db_column='DetalhesJSON', default=dict, blank=True,
                                     help_text='Consumos da missão (itens gastos, ouro de RP, observações) + '
                                               'trilha de edição da staff — tudo NA LINHA.')
    criado_por = models.ForeignKey('auth.User', models.SET_NULL, db_column='CriadoPor',
                                   related_name='aventuras_lancadas', blank=True, null=True)
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)
    revertido = models.BooleanField(db_column='Revertido', default=False, db_index=True,
                                    help_text='Lançamento estornado (aventuras/ouro devolvidos).')
    revertido_em = models.DateTimeField(db_column='RevertidoEm', blank=True, null=True)
    revertido_por = models.ForeignKey('auth.User', models.SET_NULL, db_column='RevertidoPor',
                                      related_name='aventuras_revertidas', blank=True, null=True)

    class Meta:
        db_table = 'TB_PersonagemAventura'
        verbose_name = 'Lançamento de Aventura'
        verbose_name_plural = 'Lançamentos de Aventura'
        ordering = ['-criado_em', '-id_lancamento']

    def __str__(self):
        marca = ' (revertido)' if self.revertido else ''
        return '%s ×%d%s' % (self.nome_aventura, self.qtd_aventuras, marca)

    @property
    def ouro_pago_po(self):
        """Ouro pago em PO inteiro (a coluna numérica do admin ordena por isto)."""
        return int(self.ouro_pago_pc or 0) // 100

    @property
    def ouro_pago_display(self):
        """Ouro pago DECOMPOSTO para a UI ('12 PO', '1 PO 5 PP') — home/moeda.py."""
        from .moeda import moeda_display
        return moeda_display(self.ouro_pago_pc)

    # ── leitura de `detalhes_json` (sempre por aqui; nada de indexar o dict no template) ──
    LEGADO_LABEL = '(legado)'

    @property
    def mestre_display(self):
        """Nome do mestre para exibição. Linha ANTERIOR à onda E não tem mestre gravado —
        aparece como `(legado)`, nunca como vazio (o dado não existe, não é "sem mestre")."""
        if self.origem == 'recompensa_comunidade':
            return 'Recompensa comunitária'
        if self.id_mestre_id:
            u = self.id_mestre
            return (u.get_full_name() or u.username) if u else self.LEGADO_LABEL
        return self.LEGADO_LABEL

    @property
    def eh_legado(self):
        """True quando a linha nasceu antes da onda E (sem mestre gravado)."""
        return self.origem == 'mesa' and not self.id_mestre_id

    def _bloco(self, chave, vazio):
        val = (self.detalhes_json or {}).get(chave)
        return val if isinstance(val, type(vazio)) else vazio

    @property
    def consumos(self):
        """Consumos registrados NA LINHA: [{tipo, ...}] (item consumível gasto, ouro de RP).

        O gasto de ouro sai daqui já DECOMPOSTO em `valor_display` (PO/PP/PC), derivado do
        `valor_pc` gravado — o template não formata dinheiro, e linhas antigas (que só têm
        `valor_po`) continuam legíveis."""
        from .moeda import moeda_display
        saida = []
        for c in self._bloco('consumos', []):
            if isinstance(c, dict) and c.get('tipo') == 'ouro':
                c = dict(c, valor_display=moeda_display(
                    c.get('valor_pc') if c.get('valor_pc') is not None
                    else int(c.get('valor_po') or 0) * 100))
            saida.append(c)
        return saida

    @property
    def trilha(self):
        """Trilha de edição da staff: [{quem, quando, o_que_mudou}] — append-only."""
        return self._bloco('trilha', [])

    @property
    def observacoes(self):
        return (self.detalhes_json or {}).get('observacoes') or ''

    @property
    def ouro_rp_pc(self):
        """Total de ouro gasto em RP nesta missão (PC), somado dos consumos."""
        return sum(int(c.get('valor_pc') or 0) for c in self.consumos if c.get('tipo') == 'ouro')

    @property
    def ouro_rp_po(self):
        return int(self.ouro_rp_pc) // 100


# ───────────────────── Mercado de Mestre (Moedas de Mestragem) ─────────────────────
class TbRecompensaMestre(models.Model):
    """Catálogo de recompensas trocáveis por Moedas de Mestragem (MM). `tipo` define a
    mecânica: normal (resgate simples, staff cumpre), leilao (Rei da Colina), assinatura
    (Mestre Ouro, 5º slot mensal)."""
    TIPO_CHOICES = [('normal', 'Resgate'), ('leilao', 'Leilão (Rei da Colina)'),
                    ('assinatura', 'Assinatura (Mestre Ouro)')]
    id_recompensa = models.AutoField(db_column='Id_Recompensa', primary_key=True)
    slug = models.SlugField(db_column='Slug', max_length=80, unique=True)
    nome = models.CharField(db_column='Nome', max_length=120)
    descricao = models.TextField(db_column='Descricao', blank=True, null=True)
    preco_mm = models.IntegerField(db_column='PrecoMM', default=0, help_text='Preço em Moedas de Mestragem.')
    mensalidade_mm = models.IntegerField(db_column='MensalidadeMM', default=0, help_text='Custo mensal (assinatura).')
    preco_vitalicio_aprovado_mm = models.PositiveIntegerField(null=True, blank=True,
        help_text='Preço único aprovado pelo PO em MM; deve coincidir com PrecoMM.')
    tipo = models.CharField(db_column='Tipo', max_length=12, choices=TIPO_CHOICES, default='normal')
    ativo = models.BooleanField(db_column='Ativo', default=True)
    ordem = models.IntegerField(db_column='Ordem', default=0)

    class Meta:
        db_table = 'TB_RecompensaMestre'
        verbose_name = 'Recompensa de Mestre'
        verbose_name_plural = 'Recompensas de Mestre'
        ordering = ['ordem', 'preco_mm']

    def __str__(self):
        return f'{self.nome} ({self.preco_mm} MM)'


class TbAventuraMestre(models.Model):
    """Mesa/aventura CONDUZIDA por um mestre. Ao registrar, credita `recompensa_mm` MM
    na carteira do mestre (ganho automático ao registrar a mesa)."""
    id_aventura = models.AutoField(db_column='Id_Aventura', primary_key=True)
    mestre = models.ForeignKey('auth.User', models.CASCADE, db_column='Id_Mestre', related_name='aventuras_mestradas')
    nome = models.CharField(db_column='Nome', max_length=200)
    data = models.DateField(db_column='Data', blank=True, null=True)
    jogadores = models.IntegerField(db_column='Jogadores', default=0)
    recompensa_mm = models.IntegerField(db_column='RecompensaMM', default=0)
    observacao = models.CharField(db_column='Observacao', max_length=255, blank=True, null=True)
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)

    class Meta:
        db_table = 'TB_AventuraMestre'
        verbose_name = 'Aventura Mestrada'
        verbose_name_plural = 'Aventuras Mestradas'
        ordering = ['-data', '-id_aventura']

    def __str__(self):
        return f'{self.nome} — {self.mestre_id}'


class TbTransacaoMestre(models.Model):
    """Histórico de Moedas de Mestragem (MM) de um mestre: ganho de aventura, resgate,
    leilão, assinatura, ajuste. `valor_mm` ASSINADO (+ recebeu / − gastou)."""
    TIPO_CHOICES = [('aventura', 'Ganho de aventura'), ('resgate', 'Resgate'),
                    ('leilao', 'Rei da Colina'), ('assinatura', 'Mestre Ouro'),
                    ('mensalidade', 'Mensalidade'), ('ajuste', 'Ajuste')]
    id_transacao = models.AutoField(db_column='Id_Transacao', primary_key=True)
    mestre = models.ForeignKey('auth.User', models.CASCADE, db_column='Id_Mestre', related_name='transacoes_mm')
    tipo = models.CharField(db_column='Tipo', max_length=14, choices=TIPO_CHOICES, default='ajuste')
    descricao = models.CharField(db_column='Descricao', max_length=255, blank=True, null=True)
    valor_mm = models.IntegerField(db_column='ValorMM', default=0)
    saldo_mm = models.IntegerField(db_column='SaldoMM', default=0)
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)

    class Meta:
        db_table = 'TB_TransacaoMestre'
        verbose_name = 'Transação de Mestre (MM)'
        verbose_name_plural = 'Transações de Mestre (MM)'
        ordering = ['-criado_em', '-id_transacao']

    def __str__(self):
        return f'{self.get_tipo_display()} {self.valor_mm} MM'


class MestreOuroDireito(models.Model):
    """Lifetime entitlement from one proven first purchase in the MM ledger."""

    user = models.OneToOneField('auth.User', on_delete=models.PROTECT,
                                related_name='mestre_ouro_direito')
    primeira_compra = models.OneToOneField(TbTransacaoMestre, on_delete=models.PROTECT)
    adquirido_em = models.DateTimeField()
    concedido_em = models.DateTimeField(auto_now_add=True)


class MestreOuroRevisao(models.Model):
    """Ambiguous legacy status retained for an explicit PO/staff decision."""

    user = models.OneToOneField('auth.User', on_delete=models.PROTECT)
    motivo = models.CharField(max_length=120)
    registrada_em = models.DateTimeField(auto_now_add=True)


class TbReiDaColina(models.Model):
    """Cargo único 'Rei da Colina' (leilão): quem paga o preço atual assume o cargo e o
    preço sobe 100 MM; o mestre anterior perde o cargo. Linha única (singleton)."""
    id = models.AutoField(db_column='Id', primary_key=True)
    holder = models.ForeignKey('auth.User', models.SET_NULL, db_column='Id_Holder', blank=True, null=True, related_name='rei_da_colina')
    preco_atual = models.IntegerField(db_column='PrecoAtual', default=500)
    desde = models.DateTimeField(db_column='Desde', blank=True, null=True)

    class Meta:
        db_table = 'TB_ReiDaColina'
        verbose_name = 'Rei da Colina'
        verbose_name_plural = 'Rei da Colina'

    def __str__(self):
        return f'Rei da Colina: {self.holder_id or "vago"} ({self.preco_atual} MM)'


class TbPersonagemAtributoBonus(models.Model):
    """Bônus de atributo por fonte (antecedente +2/+1, talento-ASI +1, ASI de classe).
    Os 6 campos de TbPersonagem guardam o SCORE BASE (point-buy); derive() soma
    base + Σ(bônus) e expõe o breakdown. ASI passivo via tag (attr:<x>-score+N) é
    fonte DISJUNTA (vai pelo pré-passe de tags), não entra aqui."""
    ATRIBUTO_CHOICES = [('FOR', 'Força'), ('DES', 'Destreza'), ('CON', 'Constituição'),
                        ('INT', 'Inteligência'), ('SAB', 'Sabedoria'), ('CAR', 'Carisma')]
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='atributo_bonus')
    atributo = models.CharField(db_column='Atributo', max_length=3, choices=ATRIBUTO_CHOICES)
    valor = models.IntegerField(db_column='Valor', default=1)
    origem = models.CharField(db_column='Origem', max_length=150,
                              help_text='Fonte legível: Antecedente Viajante, Talento Luchador (N4), ASI Bárbaro N8…')
    origem_tipo = models.CharField(db_column='OrigemTipo', max_length=20, blank=True, null=True,
                                   help_text='antecedente / talento-asi / classe-asi (agrupa o breakdown).')

    class Meta:
        db_table = 'TB_PersonagemAtributoBonus'
        verbose_name = 'Bônus de Atributo do Personagem'
        verbose_name_plural = 'Bônus de Atributo do Personagem'


class TbPersonagemPersonalidade(models.Model):
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='personalidade')
    tipo = models.CharField(db_column='Tipo', max_length=20, help_text='traco / ideal / vinculo / defeito')
    texto = models.TextField(db_column='Texto')

    class Meta:
        db_table = 'TB_PersonagemPersonalidade'


class TbPersonagemRecurso(models.Model):
    """Contadores de recurso (usos de Furia, Ki, etc.) — maximo costuma ser derivado, atual e o gasto."""
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='recursos')
    nome = models.CharField(db_column='Nome', max_length=100)
    atual = models.IntegerField(db_column='Atual', default=0)
    maximo = models.IntegerField(db_column='Maximo', default=0)
    versao = models.PositiveBigIntegerField(db_column='Versao', default=0)
    chave = models.CharField(
        db_column='Chave', max_length=180, blank=True, default='', db_index=True,
        help_text='Identidade mecanica estavel; o nome e apenas apresentacao.')
    origem = models.CharField(
        db_column='Origem', max_length=180, blank=True, default='',
        help_text='Fonte declarativa do recurso: classe, habilidade, magia ou item.')
    reset = models.CharField(
        db_column='Reset', max_length=40, blank=True, default='',
        help_text='Evento de recuperacao declarado pela tag.')
    recuperacao = models.CharField(
        db_column='Recuperacao', max_length=80, blank=True, default='',
        help_text='Formula recuperada no evento; vazio significa recuperar ate o maximo.')
    id_item = models.ForeignKey(
        'TbPersonagemItem', models.CASCADE, db_column='Id_Item', blank=True,
        null=True, related_name='recursos',
        help_text='Instancia dona do recurso quando ele representa cargas de item.')

    class Meta:
        db_table = 'TB_PersonagemRecurso'
        constraints = [
            models.UniqueConstraint(
                fields=('id_personagem', 'chave'),
                condition=~models.Q(chave=''),
                name='uniq_recurso_personagem_chave'),
        ]


class TbOperacaoRecurso(models.Model):
    """Recibo durável de um comando, preservado fora dos snapshots de build."""
    id_personagem = models.ForeignKey(
        'TbPersonagem', models.CASCADE, related_name='operacoes_recurso')
    operation_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    resposta = models.JSONField()
    status_http = models.PositiveSmallIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'TB_OperacaoRecurso'
        constraints = [models.UniqueConstraint(
            fields=('id_personagem', 'operation_id'), name='uniq_operacao_recurso_personagem')]


class TbPersonagemEstado(models.Model):
    """Estado persistente fora de combate declarado pelo DSL.

    O payload continua vocabulario-neutro. Combate nao escreve aqui: turnos, alvos,
    salvaguardas e condicoes momentaneas pertencem ao runtime do VTT.
    """
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey(
        'TbPersonagem', models.CASCADE, db_column='Id_Personagem',
        related_name='estados')
    chave = models.CharField(db_column='Chave', max_length=180)
    origem = models.CharField(db_column='Origem', max_length=180, blank=True, default='')
    payload_json = models.JSONField(db_column='PayloadJSON', blank=True, default=dict)
    ends_on_json = models.JSONField(db_column='EndsOnJSON', blank=True, default=list)
    ativo = models.BooleanField(db_column='Ativo', default=True, db_index=True)
    iniciado_em = models.DateTimeField(db_column='IniciadoEm', auto_now_add=True)
    encerrado_em = models.DateTimeField(db_column='EncerradoEm', blank=True, null=True)

    class Meta:
        db_table = 'TB_PersonagemEstado'
        constraints = [
            models.UniqueConstraint(
                fields=('id_personagem', 'chave'),
                name='uniq_estado_personagem_chave'),
        ]


class TbBestiario(models.Model):
    """ESBOÇO v0 — Bestiário do site. Toda criatura invocável/companheiro (summon:bestiary{<slug>})
    vive aqui; o statblock NÃO fica solto na tag (mesmo princípio do recurso/pool).
    Ataques e tracos reusam o MESMO vocabulario de tags_json das habilidades.
    Ver docs/criador-personagem/bestiario-e-summon.md."""
    id_criatura = models.AutoField(db_column='Id_Criatura', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    slug = models.SlugField(db_column='Slug', max_length=150, unique=True, help_text='Chave do summon:bestiary{<slug>}.')
    tipo = models.CharField(db_column='Tipo', max_length=60, blank=True, null=True, help_text='Tipo (5etools type.type): undead, beast, fiend, construct…')
    tamanho = models.CharField(db_column='Tamanho', max_length=80, blank=True, null=True, help_text='Tamanho ou lista de tamanhos possíveis.')
    nd = models.CharField(db_column='ND', max_length=80, blank=True, null=True, help_text='Nível de Desafio / CR com XP/PB quando disponível.')
    alinhamento = models.CharField(db_column='Alinhamento', max_length=40, blank=True, null=True)
    ca = models.CharField(db_column='CA', max_length=40, blank=True, null=True, help_text='Número ou fórmula (atalho de display).')
    pv = models.CharField(db_column='PV', max_length=160, blank=True, null=True, help_text='Número ou fórmula (ex.: 5+5*classlvl) p/ companheiros que escalam.')
    statblock_json = models.JSONField(db_column='StatblockJSON', blank=True, default=dict, help_text='Statblock no schema 5etools (ac, hp, speed, str..cha, save, skill, senses, languages, resist/immune/vulnerable/conditionImmune, trait/action/bonus/reaction/legendary, passive). Importável 1:1 do criador de mobs/Roll20.')
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Mecânica no vocabulário Bonfire (para summon:bestiary{} / motor da ficha).')
    companheiro_classe = models.ForeignKey('TbClasse', db_column='Id_Classe', blank=True, null=True, on_delete=models.SET_NULL, help_text='Companheiro de classe (ex.: Defensor de Aço → Artífice).')
    companheiro_subclasse = models.ForeignKey('TbSubclasse', db_column='Id_Subclasse', blank=True, null=True, on_delete=models.SET_NULL, help_text='Companheiro de subclasse específica.')
    escala_com_dono = models.BooleanField(db_column='EscalaComDono', default=False, help_text='Stats usam fórmulas do invocador (pb, classlvl, spell-mod).')
    descricao_markdown = models.TextField(db_column='DescricaoMarkdown', blank=True, null=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True, null=True)
    # Criaturas da COMUNIDADE: criadas por mestres no site (autor != null, comunidade=True);
    # criaturas oficiais ficam com autor nulo e comunidade=False.
    comunidade = models.BooleanField(db_column='Comunidade', default=False)
    autor = models.ForeignKey('auth.User', models.SET_NULL, db_column='Id_Autor', blank=True, null=True, related_name='criaturas')

    class Meta:
        db_table = 'TB_Bestiario'
        verbose_name = 'Criatura (Bestiário)'
        verbose_name_plural = 'Bestiário'

    def __str__(self):
        return self.nome


class TbArmadilha(models.Model):
    """Armadilha / Perigo. OFICIAIS (staff: comunidade=False, autor nulo) e da
    COMUNIDADE (mestres: comunidade=True, autor!=null) — mesma lógica do Bestiário."""
    id_armadilha = models.AutoField(db_column='Id_Armadilha', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    slug = models.SlugField(db_column='Slug', max_length=160, unique=True)
    tipo = models.CharField(db_column='Tipo', max_length=40, blank=True, null=True,
                            help_text='mecanica | magica | natural | perigo')
    nd = models.CharField(db_column='ND', max_length=20, blank=True, null=True,
                          help_text='Nível de Desafio (ex.: 1/4, 5).')
    gatilho = models.CharField(db_column='Gatilho', max_length=255, blank=True, null=True,
                               help_text='O que dispara a armadilha.')
    deteccao = models.CharField(db_column='Deteccao', max_length=120, blank=True, null=True,
                                help_text='Como/CD para detectar (ex.: Percepção CD 15).')
    desarme = models.CharField(db_column='Desarme', max_length=120, blank=True, null=True,
                               help_text='Como/CD para desarmar (ex.: Ferramentas de Ladrão CD 15).')
    save_atributo = models.CharField(db_column='SaveAtributo', max_length=10, blank=True, null=True,
                                     help_text='Atributo da salvaguarda (FOR/DES/CON/INT/SAB/CAR).')
    save_cd = models.CharField(db_column='SaveCD', max_length=10, blank=True, null=True)
    dano = models.CharField(db_column='Dano', max_length=120, blank=True, null=True,
                            help_text='Ex.: 2d10 perfurante.')
    efeito = models.TextField(db_column='Efeito', blank=True, null=True,
                              help_text='Efeito completo / consequências.')
    descricao_markdown = models.TextField(db_column='DescricaoMarkdown', blank=True, null=True)
    comunidade = models.BooleanField(db_column='Comunidade', default=False)
    autor = models.ForeignKey('auth.User', models.SET_NULL, db_column='Id_Autor', blank=True, null=True, related_name='armadilhas')

    class Meta:
        db_table = 'TB_Armadilha'
        verbose_name = 'Armadilha / Perigo'
        verbose_name_plural = 'Armadilhas e Perigos'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class TbCondicao(models.Model):
    """Condição (5e + homebrew). O `slug` casa com o catálogo 'condition' do
    tag_library; as tags apply:/cond-immune:/cleanse: referenciam por slug. Aqui
    fica a DEFINIÇÃO e os sub-efeitos (o que o catálogo de nomes não tem)."""
    id_condicao = models.AutoField(db_column='Id_Condicao', primary_key=True)
    slug = models.SlugField(db_column='Slug', max_length=60, unique=True)
    nome = models.CharField(db_column='Nome', max_length=80)
    nome_en = models.CharField(db_column='NomeEn', max_length=80, blank=True, null=True)
    categoria = models.CharField(db_column='Categoria', max_length=20, default='5e',
                                 help_text='5e | homebrew')
    resumo = models.CharField(db_column='Resumo', max_length=255, blank=True, null=True)
    definicao = models.TextField(db_column='Definicao', blank=True, null=True)
    efeitos_json = models.JSONField(db_column='EfeitosJSON', blank=True, default=list,
                                    help_text='[{titulo, texto}] dos sub-efeitos da condição.')
    ordem = models.IntegerField(db_column='Ordem', default=0)

    class Meta:
        db_table = 'TB_Condicao'
        verbose_name = 'Condição'
        verbose_name_plural = 'Condições'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class TbIdioma(models.Model):
    """Idioma do mundo. Categorias: basal | derivado | exotico."""
    id_idioma = models.AutoField(db_column='Id_Idioma', primary_key=True)
    slug = models.SlugField(db_column='Slug', max_length=60, unique=True)
    nome = models.CharField(db_column='Nome', max_length=80)
    nome_mundo = models.CharField(db_column='NomeMundo', max_length=80, blank=True, null=True,
                                  help_text='Nome in-world (ex.: Dominique p/ Comum).')
    categoria = models.CharField(db_column='Categoria', max_length=20, default='basal',
                                 help_text='basal | derivado | exotico')
    idioma_caracteristico = models.CharField(db_column='IdiomaCaracteristico', max_length=60,
                                             blank=True, null=True, help_text='Idioma real análogo (sabor).')
    transcricao = models.CharField(db_column='Transcricao', max_length=60, blank=True, null=True,
                                   help_text='Sistema de escrita.')
    ordem = models.IntegerField(db_column='Ordem', default=0)

    class Meta:
        db_table = 'TB_Idioma'
        verbose_name = 'Idioma'
        verbose_name_plural = 'Idiomas'
        ordering = ['categoria', 'ordem', 'nome']

    def __str__(self):
        return self.nome


class TbRegra(models.Model):
    """Glossário de regras gerais (D&D 2024) traduzido — contexto do sistema.
    Termos de referência (Ação, Cobertura, Área de Efeito…); condições têm modelo
    próprio (TbCondicao)."""
    id_regra = models.AutoField(db_column='Id_Regra', primary_key=True)
    slug = models.SlugField(db_column='Slug', max_length=90, unique=True)
    nome = models.CharField(db_column='Nome', max_length=140)
    nome_en = models.CharField(db_column='NomeEn', max_length=140, blank=True, null=True)
    categoria = models.CharField(db_column='Categoria', max_length=60, blank=True, null=True,
                                 help_text='Marcador do termo (Action, Area of Effect, Hazard…).')
    definicao = models.TextField(db_column='Definicao', blank=True, null=True)

    class Meta:
        db_table = 'TB_Regra'
        verbose_name = 'Regra (glossário)'
        verbose_name_plural = 'Regras (glossário)'
        ordering = ['nome']

    def __str__(self):
        return self.nome


# ─────────────────────────────────────────────────────────────────────────────
# Personalização de perfil/ficha (F1) — catálogo em banco + inventário por usuário
# Ver docs/agentes/arquitetura_personalizacao_perfil.md §3.
# CATÁLOGO (TbCosmetico) é CONTEÚDO sincronizado por slug; o INVENTÁRIO
# (TbUsuarioCosmetico) é dado de USUÁRIO e NÃO é sincronizado no deploy.
# ─────────────────────────────────────────────────────────────────────────────

class TbCosmetico(models.Model):
    """Catálogo de cosméticos (temas/molduras/efeitos/etc.). Cada linha aponta pra
    uma classe CSS (e opcionalmente um asset). Adicionar cosmético = INSERT + CSS,
    sem deploy de Python. A chave natural é o `slug` (usado no sync de conteúdo)."""
    TIPO_CHOICES = [
        ('tema', 'Tema'),
        ('moldura', 'Moldura'),
        ('efeito', 'Efeito'),
        ('titulo', 'Título'),
        ('badge', 'Badge'),
        ('banner_preset', 'Banner'),
    ]
    ORIGEM_CHOICES = [
        ('livre', 'Livre (todos têm)'),
        ('conquista', 'Conquista'),
        ('loja_mm', 'Loja (Moedas de Mestragem)'),
        ('loja_evento', 'Loja (Moedas de Evento)'),
        ('loja_braseiro', 'Loja (Braseiros)'),
        ('colaborador', 'Colaborador'),
        ('staff', 'Staff'),
        ('evento_manual', 'Evento (manual)'),
        ('mestre_ouro', 'Mestre Ouro vitalício'),
    ]
    ESCOPO_CHOICES = [
        ('perfil', 'Só perfil'),
        ('ficha', 'Só ficha'),
        ('ambos', 'Perfil e ficha'),
    ]

    slug = models.SlugField(db_column='Slug', max_length=60, unique=True,
                            help_text="Identificador estável (ex.: 'ember', 'gold-trim').")
    tipo = models.CharField(db_column='Tipo', max_length=20, choices=TIPO_CHOICES)
    nome = models.CharField(db_column='Nome', max_length=100)
    descricao = models.CharField(db_column='Descricao', max_length=255, blank=True)
    raridade = models.CharField(db_column='Raridade', max_length=20, default='comum',
                                help_text='comum | raro | epico | lendario (cor do card).')
    css_class = models.CharField(db_column='CssClass', max_length=60, blank=True,
                                 help_text="Classe CSS aplicada (ex.: 'theme-ember', 'frame-gold-trim').")
    asset_url = models.CharField(db_column='AssetUrl', max_length=500, blank=True,
                                 help_text='Ícone de badge ou overlay webp/gif de moldura animada.')
    asset_file = models.FileField(db_column='AssetFile', upload_to='cosmetics/badges/',
                                  blank=True,
                                  help_text='Ícone de badge enviado (upload staff). Tem prioridade sobre asset_url.')
    # Tema como dado (só usado por tipo='tema'). Sanitizado server-side em TODA
    # renderização por sanitize_definicao_tema (hex-only, enums whitelisted).
    definicao_json = models.JSONField(db_column='DefinicaoJson', default=dict, blank=True,
                                      help_text='Tema como dado: {accent,accent2,surface,deep,gradiente,particula,vel,glow}. Só tipo=tema.')
    # Arquivo .css opcional para temas avançados (upload staff-only via admin).
    css_file = models.FileField(
        db_column='CssFile', upload_to='cosmetics/css/', blank=True,
        validators=[FileExtensionValidator(['css'])],
        help_text='CSS avançado do tema (upload staff). Incluído como <link> quando o tema é equipado.')
    animado = models.BooleanField(db_column='Animado', default=False)
    origem = models.CharField(db_column='Origem', max_length=20, default='livre',
                              choices=ORIGEM_CHOICES,
                              help_text='Como o cosmético é adquirido. livre = todos têm.')
    preco = models.IntegerField(db_column='Preco', null=True, blank=True,
                                help_text='Em MM/evento/braseiro conforme a origem.')
    requer_plano = models.CharField(db_column='RequerPlano', max_length=30, blank=True,
                                    help_text='Para origem=colaborador: tier mínimo.')
    escopo = models.CharField(db_column='Escopo', max_length=10, default='ambos',
                              choices=ESCOPO_CHOICES)
    ativo = models.BooleanField(db_column='Ativo', default=True)
    ordem = models.IntegerField(db_column='Ordem', default=0)

    class Meta:
        db_table = 'TB_Cosmetico'
        verbose_name = 'Cosmético'
        verbose_name_plural = 'Cosméticos'
        ordering = ['tipo', 'ordem', 'nome']

    def __str__(self):
        return '%s (%s)' % (self.nome, self.get_tipo_display())

    @property
    def asset_efetivo(self):
        """URL do ícone efetivo de um badge: arquivo enviado (asset_file) tem
        prioridade, senão cai no asset_url (que pode ser URL de imagem ou glyph
        emoji). Só faz sentido para tipo='badge'; para tema/css não se usa."""
        try:
            if self.asset_file:
                return self.asset_file.url
        except Exception:
            # FieldFile.url pode levantar se o storage não tiver base_url; degrada.
            pass
        return self.asset_url or ''


class TbUsuarioCosmetico(models.Model):
    """Inventário: o que cada usuário TEM desbloqueado (≠ o que está usando, que
    continua nos campos string de UserProfile/TbPersonagem). Dado de USUÁRIO —
    NÃO entra no sync de conteúdo."""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                             related_name='cosmeticos', db_column='UserId')
    cosmetico = models.ForeignKey(TbCosmetico, on_delete=models.CASCADE,
                                  related_name='desbloqueios', db_column='CosmeticoId')
    desbloqueado_em = models.DateTimeField(db_column='DesbloqueadoEm', auto_now_add=True)
    origem = models.CharField(db_column='Origem', max_length=30, blank=True,
                              help_text="Como foi obtido ('conquista:<slug>', 'compra_mm', 'staff', 'seed'…).")
    suspenso_em = models.DateTimeField(db_column='SuspensoEm', null=True, blank=True)

    class Meta:
        db_table = 'TB_UsuarioCosmetico'
        verbose_name = 'Cosmético do usuário'
        verbose_name_plural = 'Cosméticos dos usuários'
        unique_together = [('user', 'cosmetico')]
        ordering = ['-desbloqueado_em']

    def __str__(self):
        return '%s → %s' % (self.user.username, self.cosmetico.slug)


# Invalidação do cache do catálogo de cosméticos quando a staff edita no admin.
@receiver(post_save, sender=TbCosmetico)
@receiver(post_delete, sender=TbCosmetico)
def _invalidate_cosmetico_cache(sender, **kwargs):
    if kwargs.get('raw', False):
        return
    try:
        from .cosmetics import invalidate_cosmetic_cache
        invalidate_cosmetic_cache()
    except Exception:
        # Cache é best-effort; nunca deixe uma falha de cache quebrar o save.
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Conquistas (F3) — definição cadastrável pela staff + concessão (inclusive em
# massa) + recompensa que cai no inventário de cosméticos.
# Ver docs/agentes/arquitetura_personalizacao_perfil.md §3 e §7 (F3).
# CONQUISTA (TbConquista) é CONTEÚDO sincronizado por slug; a CONCESSÃO
# (TbUsuarioConquista) é dado de USUÁRIO e NÃO é sincronizada no deploy.
# ─────────────────────────────────────────────────────────────────────────────

class TbConquista(models.Model):
    """Definição de uma conquista. Concedida manualmente pela staff (F3) ou, no
    futuro, por critério automático (criterio_json em signals). Ao ser concedida,
    se tiver `recompensa`, desbloqueia o cosmético ligado no inventário do usuário.
    A chave natural é o `slug` (usado no sync de conteúdo)."""
    CRITERIO_CHOICES = [
        ('manual', 'Manual (staff concede)'),
        ('automatico', 'Automático (por critério)'),
    ]

    slug = models.SlugField(db_column='Slug', max_length=60, unique=True,
                            help_text="Identificador estável (ex.: 'sangue-de-dragao').")
    nome = models.CharField(db_column='Nome', max_length=100)
    descricao = models.CharField(db_column='Descricao', max_length=255, blank=True)
    icone_url = models.CharField(db_column='IconeUrl', max_length=500, blank=True,
                                 help_text='Ícone/medalha da conquista (URL).')
    icone_file = models.FileField(db_column='IconeFile', upload_to='cosmetics/conquistas/',
                                  blank=True,
                                  help_text='Ícone/medalha enviado (upload staff). Tem prioridade sobre icone_url.')
    secreta = models.BooleanField(db_column='Secreta', default=False,
                                  help_text='Se marcada, só aparece pra quem a tem (não vaza existência).')
    criterio = models.CharField(db_column='Criterio', max_length=20, default='manual',
                                choices=CRITERIO_CHOICES,
                                help_text='manual = staff concede; automatico = por critério (fase 2).')
    criterio_json = models.JSONField(db_column='CriterioJson', default=dict, blank=True,
                                     help_text='Métricas disponíveis: characters_created, stories_published ou items_purchased; schema_version=1, scope=account, operator=gte, target=1.')
    recompensa = models.ForeignKey(TbCosmetico, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='conquistas',
                                   db_column='RecompensaId',
                                   help_text='Cosmético desbloqueado no inventário ao conceder.')
    ordem = models.IntegerField(db_column='Ordem', default=0)
    ativo = models.BooleanField(db_column='Ativo', default=True)

    class Meta:
        db_table = 'TB_Conquista'
        verbose_name = 'Conquista'
        verbose_name_plural = 'Conquistas'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        from .conquistas import (regra_inicio_classe_valida,
                                 regra_unidades_compradas_valida)
        supported = [
            {'schema_version': 1, 'metric': metric,
             'scope': 'account', 'operator': 'gte', 'target': 1}
            for metric in ('characters_created', 'stories_published', 'items_purchased')
        ]
        if (self.criterio == 'automatico' and self.criterio_json not in supported and
                not regra_unidades_compradas_valida(self.criterio_json) and
                not regra_inicio_classe_valida(self.criterio_json)):
            if self.pk and type(self).objects.filter(
                pk=self.pk, criterio='automatico', criterio_json=self.criterio_json,
            ).exists():
                return  # Definições antigas permanecem editáveis sem mudar a regra.
            raise ValidationError({'criterio_json': 'Critério automático não suportado. Use characters_created, stories_published, items_purchased, items_purchased_units ou class_started com identidade e parâmetros válidos.'})

    @property
    def icone_efetivo(self):
        """URL do ícone efetivo da conquista: arquivo enviado (icone_file) tem
        prioridade, senão cai no icone_url. Vazio → o template usa o fallback 🏆."""
        try:
            if self.icone_file:
                return self.icone_file.url
        except Exception:
            pass
        return self.icone_url or ''


class TbUsuarioConquista(models.Model):
    """Concessão de uma conquista a um usuário (o que ele CONQUISTOU). Dado de
    USUÁRIO — NÃO entra no sync de conteúdo. `concedida_por` registra qual staff
    concedeu (auditoria)."""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                             related_name='conquistas', db_column='UserId')
    conquista = models.ForeignKey(TbConquista, on_delete=models.CASCADE,
                                  related_name='concessoes', db_column='ConquistaId')
    concedida_em = models.DateTimeField(db_column='ConcedidaEm', auto_now_add=True)
    concedida_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='conquistas_concedidas',
                                      db_column='ConcedidaPorId')
    evidencia_json = models.JSONField(db_column='EvidenciaJson', default=dict, blank=True)
    definicao_json = models.JSONField(db_column='DefinicaoJson', default=dict, blank=True)
    revogada_em = models.DateTimeField(db_column='RevogadaEm', null=True, blank=True)

    class Meta:
        db_table = 'TB_UsuarioConquista'
        verbose_name = 'Conquista do usuário'
        verbose_name_plural = 'Conquistas dos usuários'
        unique_together = [('user', 'conquista')]
        ordering = ['-concedida_em']

    def __str__(self):
        return '%s → %s' % (self.user.username, self.conquista.slug)


class TbEventoConquista(models.Model):
    """Fato canônico de domínio; simulações do criador não produzem linhas aqui."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    origem = models.CharField(db_column='Origem', max_length=30)
    chave_origem = models.CharField(db_column='ChaveOrigem', max_length=100)
    tipo = models.CharField(db_column='Tipo', max_length=50)
    versao_payload = models.PositiveSmallIntegerField(db_column='VersaoPayload', default=1)
    payload_json = models.JSONField(db_column='PayloadJSON', default=dict, blank=True)
    conta = models.ForeignKey('auth.User', on_delete=models.CASCADE, db_column='ContaId')
    personagem = models.ForeignKey('TbPersonagem', on_delete=models.SET_NULL,
                                   null=True, blank=True, db_column='PersonagemId')
    agregado_id = models.PositiveIntegerField(db_column='AgregadoId')
    ocorrido_em = models.DateTimeField(db_column='OcorridoEm')
    ingerido_em = models.DateTimeField(db_column='IngeridoEm', auto_now_add=True)

    class Meta:
        db_table = 'TB_EventoConquista'
        constraints = [models.UniqueConstraint(
            fields=['origem', 'chave_origem'], name='unique_evento_conquista_origem',
        )]


# ─────────────────────────────────────────────────────────────────────────────
# Social do perfil — CURTIR e SEGUIR (pedido dos usuários).
# As DUAS tabelas são dado de USUÁRIO ("memória"): entram em MEMORY_MODELS no
# home/deploy_sync.py e NUNCA no sync de conteúdo. Sumiu o usuário (dos dois
# lados), some a relação → on_delete=CASCADE nas duas pontas.
# Idempotência é do banco: unique_together garante que "curtir duas vezes" não
# duplica linha mesmo com corrida entre dois cliques.
# ─────────────────────────────────────────────────────────────────────────────

class TbPerfilCurtida(models.Model):
    """Uma curtida de `quem` no perfil de `alvo` (like simples, sem peso/valor).
    Relação sem estado extra: existe = curtido; deletada = descurtido."""
    quem = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                             related_name='curtidas_dadas', db_column='QuemId')
    alvo = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                             related_name='curtidas_recebidas', db_column='AlvoId')
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)

    class Meta:
        db_table = 'TB_PerfilCurtida'
        verbose_name = 'Curtida de perfil'
        verbose_name_plural = 'Curtidas de perfil'
        unique_together = [('quem', 'alvo')]
        ordering = ['-criado_em']

    def __str__(self):
        return '%s ♥ %s' % (self.quem.username, self.alvo.username)


class TbPerfilSeguidor(models.Model):
    """`seguidor` segue o perfil de `alvo`. Direcional (seguir não é mútuo).
    related_name: user.seguindo = quem ELE segue; user.seguidores = quem o segue."""
    seguidor = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                                 related_name='seguindo', db_column='SeguidorId')
    alvo = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                             related_name='seguidores', db_column='AlvoId')
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)

    class Meta:
        db_table = 'TB_PerfilSeguidor'
        verbose_name = 'Seguidor de perfil'
        verbose_name_plural = 'Seguidores de perfil'
        unique_together = [('seguidor', 'alvo')]
        ordering = ['-criado_em']

    def __str__(self):
        return '%s → %s' % (self.seguidor.username, self.alvo.username)


class TbMapDesenho(models.Model):
    """Marcação de desenho sobre o mapa criada pela staff no editor (WP1).

    Modelo genérico único para todos os tipos de marcação livre do mapa:
    imagem posicionável (overlay) e linha (reta, tracejada ou "ligação"
    ancorada em markers). O que varia por tipo mora em `dados_json` — o
    formato é validado 100% server-side (ver home/views.py:sanitize_desenho).

    Natureza igual ao TbMapMarker: é dado de MUNDO editado pela staff direto
    em produção, então entra no sync de conteúdo como "substitui inteira"
    (ver home/deploy_sync.py). O front (mapa.html) filtra por `camada`.
    """
    TIPO_CHOICES = [
        ('imagem', 'Imagem'),
        ('linha', 'Linha'),
    ]

    id_desenho = models.AutoField(db_column='Id_Desenho', primary_key=True)
    tipo = models.CharField(db_column='Tipo', max_length=20, choices=TIPO_CHOICES)
    camada = models.IntegerField(db_column='Camada', default=0, help_text="Camada do mapa (0=Superficie, 1=Subterraneo Nivel 1, etc.)")
    nome = models.CharField(db_column='Nome', max_length=150, blank=True, help_text="Rótulo do desenho (só para a staff se orientar).")
    dados_json = models.JSONField(db_column='DadosJson', default=dict, blank=True, help_text="Payload do desenho conforme o tipo (validado no servidor).")
    ordem = models.IntegerField(db_column='Ordem', default=0)
    ativo = models.BooleanField(db_column='Ativo', default=True)
    criado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name='desenhos_mapa',
                                   db_column='CriadoPorId')
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)
    atualizado_em = models.DateTimeField(db_column='AtualizadoEm', auto_now=True)

    class Meta:
        db_table = 'TB_MapDesenho'
        verbose_name = 'Desenho do Mapa'
        verbose_name_plural = 'Desenhos do Mapa'
        ordering = ['camada', 'ordem', 'id_desenho']

    def __str__(self):
        rotulo = self.nome or '(sem rótulo)'
        return '%s [%s] camada %s' % (rotulo, self.tipo, self.camada)


class TbConteudoEstatico(models.Model):
    """Bloco editorial administrável usado por páginas institucionais e pela home.

    A estrutura visual continua no template; o texto publicado fica no banco. Isso
    permite corrigir chamadas, instruções e páginas institucionais sem novo deploy.
    """

    id_conteudo = models.AutoField(db_column='Id_Conteudo', primary_key=True)
    chave = models.SlugField(
        db_column='Chave', max_length=100, unique=True,
        help_text='Identificador estável do bloco, por exemplo home-hero.',
    )
    pagina = models.SlugField(
        db_column='Pagina', max_length=60, db_index=True,
        help_text='Página proprietária do bloco, por exemplo home ou privacidade.',
    )
    titulo = models.CharField(db_column='Titulo', max_length=220, blank=True)
    subtitulo = models.TextField(db_column='Subtitulo', blank=True)
    conteudo_markdown = models.TextField(
        db_column='ConteudoMarkdown', blank=True,
        help_text='Corpo em Markdown Bonfire. Referências em card continuam disponíveis.',
    )
    cta_texto = models.CharField(db_column='CtaTexto', max_length=100, blank=True)
    cta_url = models.CharField(db_column='CtaUrl', max_length=500, blank=True)
    imagem_url = models.CharField(db_column='ImagemUrl', max_length=500, blank=True)
    ativo = models.BooleanField(db_column='Ativo', default=True)
    ordem = models.PositiveIntegerField(db_column='Ordem', default=0)
    atualizado_em = models.DateTimeField(db_column='AtualizadoEm', auto_now=True)

    class Meta:
        db_table = 'TB_ConteudoEstatico'
        verbose_name = 'Conteúdo estático'
        verbose_name_plural = 'Conteúdos estáticos'
        ordering = ['pagina', 'ordem', 'chave']

    def __str__(self):
        return '%s · %s' % (self.pagina, self.titulo or self.chave)


class TbTagLibraryRevision(models.Model):
    """Versão auditável da especificação do DSL mecânico.

    O arquivo ``home/tag_library.json`` continua sendo o fallback distribuído
    com o código. Quando existe uma revisão ativa, o interpretador passa a ler
    ``conteudo_json`` diretamente do banco.
    """

    id_revisao = models.AutoField(db_column='Id_Revisao', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=160)
    motivo = models.TextField(db_column='Motivo', blank=True)
    conteudo_json = models.JSONField(db_column='ConteudoJson')
    checksum = models.CharField(db_column='Checksum', max_length=64, db_index=True)
    ativa = models.BooleanField(db_column='Ativa', default=False, db_index=True)
    validacao_json = models.JSONField(
        db_column='ValidacaoJson', default=dict, blank=True,
        help_text='Resumo do lint e da comparação com as tags cadastradas.',
    )
    criada_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='revisoes_biblioteca_tags_criadas',
        db_column='CriadaPorId',
    )
    criada_em = models.DateTimeField(db_column='CriadaEm', auto_now_add=True)
    ativada_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='revisoes_biblioteca_tags_ativadas',
        db_column='AtivadaPorId',
    )
    ativada_em = models.DateTimeField(db_column='AtivadaEm', null=True, blank=True)

    class Meta:
        db_table = 'TB_TagLibraryRevision'
        verbose_name = 'Revisão da biblioteca de tags'
        verbose_name_plural = 'Revisões da biblioteca de tags'
        ordering = ['-criada_em', '-id_revisao']
        constraints = [
            models.UniqueConstraint(
                fields=['ativa'], condition=models.Q(ativa=True),
                name='home_tag_library_single_active',
            ),
        ]

    def __str__(self):
        estado = 'ativa' if self.ativa else 'histórica'
        return '%s (%s)' % (self.nome, estado)


class SocialCreditWallet(models.Model):
    """Integer contribution-credit balance owned by an account, not a character."""

    user = models.OneToOneField('auth.User', on_delete=models.PROTECT, related_name='social_credit_wallet')
    balance = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(balance__gte=0), name='social_credit_balance_nonnegative'),
        ]

    def __str__(self):
        return str(self.user)


class SocialCreditPolicy(models.Model):
    """Versioned economic rule; no rule is active until the PO approves one."""

    version = models.CharField(max_length=40, unique=True)
    first_publication_amount = models.PositiveIntegerField()
    reader_recognition_enabled = models.BooleanField(default=False)
    reader_milestone_size = models.PositiveIntegerField(null=True, blank=True)
    reader_milestone_amount = models.PositiveIntegerField(null=True, blank=True)
    reader_consolidation_hours = models.PositiveIntegerField(null=True, blank=True)
    reader_story_credit_cap = models.PositiveIntegerField(null=True, blank=True)
    reader_author_period_credit_cap = models.PositiveIntegerField(null=True, blank=True)
    reader_period_days = models.PositiveIntegerField(null=True, blank=True)
    redemption_enabled = models.BooleanField(default=False)
    redemption_cost = models.PositiveIntegerField(null=True, blank=True)
    redemption_gold_pc = models.PositiveIntegerField(null=True, blank=True)
    redemption_gold_source = models.CharField(max_length=120, blank=True, default='')
    redemption_counts_for_progression = models.BooleanField(null=True, blank=True)
    redemption_period_days = models.PositiveIntegerField(null=True, blank=True)
    redemption_period_limit = models.PositiveIntegerField(null=True, blank=True)
    redemption_character_limit = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Política de créditos'
        verbose_name_plural = 'Políticas de créditos'
        constraints = [
            models.CheckConstraint(condition=models.Q(first_publication_amount__gt=0),
                                   name='social_credit_first_publication_positive'),
            models.UniqueConstraint(fields=['active'], condition=models.Q(active=True),
                                    name='social_credit_one_active_policy'),
        ]

    def __str__(self):
        return self.version


class SocialCreditEntry(models.Model):
    """Immutable credit/debit record with a globally unique operation reference."""

    wallet = models.ForeignKey(SocialCreditWallet, on_delete=models.PROTECT, related_name='entries')
    operation_ref = models.CharField(max_length=160, unique=True)
    kind = models.CharField(max_length=40)
    delta = models.BigIntegerField()
    balance_after = models.BigIntegerField()
    reversal_of = models.OneToOneField('self', on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='reversal')
    policy = models.ForeignKey(SocialCreditPolicy, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.CheckConstraint(condition=~models.Q(delta=0), name='social_credit_entry_nonzero'),
            models.CheckConstraint(condition=models.Q(balance_after__gte=0),
                                   name='social_credit_entry_balance_nonnegative'),
        ]


class SocialCreditHistoricalCampaign(models.Model):
    """Immutable approval scope and audit record for one historical credit run."""

    key = models.SlugField(max_length=40, unique=True)
    policy = models.ForeignKey(SocialCreditPolicy, on_delete=models.PROTECT)
    published_from = models.DateField()
    published_through = models.DateField()
    reactions_through = models.DateField()
    snapshot_sha256 = models.CharField(max_length=64)
    applied_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    applied_at = models.DateTimeField(auto_now_add=True)


class SocialCreditReaderRecognition(models.Model):
    """First like per reader and Chronicle, retained after an unlike."""

    cronica = models.ForeignKey(TbCronica, on_delete=models.PROTECT, related_name='reader_recognitions')
    reader = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    policy = models.ForeignKey(SocialCreditPolicy, on_delete=models.PROTECT,
                               null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['cronica', 'reader'], name='unique_social_credit_reader_recognition',
        )]


class SocialCreditRedemption(models.Model):
    """One immutable purchase tied to both ledgers and its approved policy snapshot."""

    request_id = models.UUIDField(unique=True)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='social_redemptions')
    character = models.ForeignKey(TbPersonagem, on_delete=models.PROTECT,
                                  related_name='social_redemptions')
    policy = models.ForeignKey(SocialCreditPolicy, on_delete=models.PROTECT)
    credit_entry = models.OneToOneField(SocialCreditEntry, on_delete=models.PROTECT)
    adventure_entry = models.OneToOneField(TbPersonagemAventura, on_delete=models.PROTECT)
    cost = models.PositiveIntegerField()
    gold_pc = models.PositiveIntegerField()
    gold_source = models.CharField(max_length=120)
    counts_for_progression = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    reversal_reason = models.CharField(max_length=500, blank=True, default='')
    reversal_review_reason = models.CharField(max_length=500, blank=True, default='')
    reversal_review_requested_at = models.DateTimeField(null=True, blank=True)
    reversal_review_requested_by = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT, null=True, blank=True,
        related_name='social_redemption_reviews')
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT, null=True, blank=True,
        related_name='social_redemption_reversals')
    credit_reversal_entry = models.OneToOneField(
        SocialCreditEntry, on_delete=models.PROTECT, null=True, blank=True,
        related_name='social_redemption_reversal')
    gold_reversal_entry = models.OneToOneField(
        TbTransacao, on_delete=models.PROTECT, null=True, blank=True,
        related_name='social_redemption_reversal')

    class Meta:
        ordering = ['-created_at', '-pk']
