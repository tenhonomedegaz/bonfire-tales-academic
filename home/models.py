





















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

    id_recurso = models.AutoField(db_column='Id_Recurso', primary_key=True)  

    id_classe = models.ForeignKey(TbClasse, models.DO_NOTHING, db_column='Id_Classe')  

    id_subclasse = models.ForeignKey('TbSubclasse', models.DO_NOTHING, db_column='Id_Subclasse', blank=True, null=True)  

    nome = models.CharField(db_column='Nome')  

    slug = models.CharField(db_column='Slug')  

    nivel = models.IntegerField(db_column='Nivel', blank=True, null=True)

    valor = models.CharField(db_column='Valor', blank=True, null=True)

    valores_json = models.JSONField(db_column='ValoresJSON', blank=True, default=dict, help_text='Mapa nivel->valor, so os niveis onde o valor muda. Ex.: {"1":"2","5":"3"}.')
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
    tags_json = models.JSONField(db_column='TagsJSON', blank=True, default=list, help_text='Tags estruturadas usadas pelo criador de personagem.')

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
            'camada': instance.camada,
        }
    )
    
    if not created:
        marker.territorio = instance.territorio
        marker.categoria = instance.categoria
        marker.camada = instance.camada
        marker.save()

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
    fonte = models.CharField(db_column='Fonte', max_length=20, blank=True, null=True, help_text="Livro/edição de origem (ex.: PHB'24, PHB'14, DMG'24).")
    peso = models.FloatField(db_column='Peso', blank=True, null=True, help_text='Peso em kg ou lbs')
    preco = models.CharField(db_column='Preco', max_length=50, blank=True, null=True, help_text='Ex: 5 PO')
    
    
    dano = models.CharField(db_column='Dano', max_length=50, blank=True, null=True, help_text='Ex: 1d8 cortante')
    propriedades = models.CharField(db_column='Propriedades', max_length=200, blank=True, null=True, help_text='Ex: Acuidade, Leve')
    maestria = models.CharField(db_column='Maestria', max_length=100, blank=True, null=True, help_text='Opção adicional de maestria')
    
    
    ca = models.CharField(db_column='CA', max_length=50, blank=True, null=True, help_text='Ex: 14 + mod Des (max 2)')
    tipo_equip = models.CharField(db_column='TipoEquip', max_length=20, blank=True, null=True,
                                  help_text='armadura-leve / armadura-media / armadura-pesada / escudo (deriva CA).')
    ca_base = models.IntegerField(db_column='CABase', blank=True, null=True,
                                  help_text='CA base da armadura (couro=11, escamas=14, placas=18, escudo=+2).')
    ca_limite_des = models.IntegerField(db_column='CALimiteDes', blank=True, null=True,
                                        help_text='Teto do mod DES: leve=vazio (ilimitado), média=2, pesada=0.')
    forca_minima = models.IntegerField(db_column='ForcaMinima', blank=True, null=True, help_text='Força mínima para usar')
    furtividade_desvantagem = models.BooleanField(db_column='FurtividadeDesvantagem', default=False)
    
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
        ('bracos', 'Bracos'),
        ('maos', 'Mãos'),
        ('dedos', 'Dedos'),
        ('aneis', 'Aneis'),
        ('cintura', 'Cintura'),
        ('pes', 'Pés'),
        ('pele', 'Pele'),
        ('arma', 'Arma'),
        ('armadura', 'Armadura'),
        ('escudo', 'Escudo'),
        ('municao', 'Municao'),
        ('pocao', 'Pocao'),
        ('pergaminho', 'Pergaminho'),
        ('varinha', 'Varinha'),
        ('cajado_bastao', 'Cajado/Bastao'),
        ('veiculo', 'Veiculo'),
        ('flutuando', 'Flutuando'),
        ('acessorio', 'Acessorio'),
        ('edificacao', 'Edificacao'),
        ('empunhado', 'Empunhado'),
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
    subclasses = models.TextField(db_column='Subclasses', blank=True, null=True)
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
    vlibras_enabled = models.BooleanField(db_column='VlibrasEnabled', default=False, help_text='Habilita o plugin VLibras no site.')
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
    foto_url = models.CharField(db_column='FotoUrl', max_length=500, blank=True, null=True, help_text='Link da imagem do retrato do personagem.')
    token_url = models.CharField(db_column='TokenUrl', max_length=500, blank=True, null=True, help_text='Link da imagem do token do personagem.')

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
    nivel = models.IntegerField(db_column='Nivel', default=1)
    principal = models.BooleanField(db_column='Principal', default=False, help_text='Classe inicial (define dado de vida base, etc.).')

    class Meta:
        db_table = 'TB_PersonagemClasse'
        verbose_name = 'Classe do Personagem'
        verbose_name_plural = 'Classes do Personagem'

    def __str__(self):
        return f'{self.id_personagem_id} - {self.id_classe_id} Nv{self.nivel}'


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


class TbPersonagemItem(models.Model):
    id = models.AutoField(db_column='Id', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='inventario')
    qtd = models.IntegerField(db_column='Qtd', default=1)
    nome = models.CharField(db_column='Nome', max_length=200)
    custo = models.CharField(db_column='Custo', max_length=30, blank=True, null=True)
    peso = models.CharField(db_column='Peso', max_length=20, blank=True, null=True)
    equipado = models.BooleanField(db_column='Equipado', default=False)
    sintonizado = models.BooleanField(db_column='Sintonizado', default=False)
    # armadura-base equipável (para derivar CA): tipo + base + teto de mod DES
    tipo_equip = models.CharField(db_column='TipoEquip', max_length=20, blank=True, null=True,
                                  help_text='armadura-leve / armadura-media / armadura-pesada / escudo (deriva CA).')
    ca_base = models.IntegerField(db_column='CABase', blank=True, null=True,
                                  help_text='CA base da armadura (couro=11, cota-de-escamas=14, placas=18, escudo=+2).')
    ca_limite_des = models.IntegerField(db_column='CALimiteDes', blank=True, null=True,
                                        help_text='Teto do mod DES: leve=vazio (ilimitado), média=2, pesada=0.')
    # Vínculo ao catálogo de itens mágicos: traz tags_json (efeitos), raridade e
    # requer_sintonizacao. Itens mundanos ficam com este campo nulo.
    id_item_magico = models.ForeignKey('TbItemMagico', models.SET_NULL, db_column='Id_ItemMagico',
                                       blank=True, null=True, related_name='posses')

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
                    ('aventura', 'Ouro de aventura'), ('inicial', 'Saldo inicial'), ('ajuste', 'Ajuste')]
    id_transacao = models.AutoField(db_column='Id_Transacao', primary_key=True)
    id_personagem = models.ForeignKey('TbPersonagem', models.CASCADE, db_column='Id_Personagem', related_name='transacoes')
    tipo = models.CharField(db_column='Tipo', max_length=20, choices=TIPO_CHOICES, default='ajuste')
    descricao = models.CharField(db_column='Descricao', max_length=255, blank=True, null=True)
    valor_pc = models.IntegerField(db_column='ValorPC', default=0, help_text='Assinado: + recebido, − gasto (em peças de cobre).')
    saldo_pc = models.IntegerField(db_column='SaldoPC', default=0, help_text='Carteira (PC) após o movimento.')
    criado_em = models.DateTimeField(db_column='CriadoEm', auto_now_add=True)

    class Meta:
        db_table = 'TB_Transacao'
        verbose_name = 'Transação'
        verbose_name_plural = 'Transações'
        ordering = ['-criado_em', '-id_transacao']

    def __str__(self):
        return f'{self.get_tipo_display()} {self.valor_pc} PC'


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

    class Meta:
        db_table = 'TB_PersonagemRecurso'


class TbBestiario(models.Model):
    """ESBOÇO v0 — Bestiário do site. Toda criatura invocável/companheiro (summon:bestiary{<slug>})
    vive aqui; o statblock NÃO fica solto na tag (mesmo princípio do recurso/pool).
    Ataques e tracos reusam o MESMO vocabulario de tags_json das habilidades.
    Ver docs/criador-personagem/bestiario-e-summon.md."""
    id_criatura = models.AutoField(db_column='Id_Criatura', primary_key=True)
    nome = models.CharField(db_column='Nome', max_length=150)
    slug = models.SlugField(db_column='Slug', max_length=150, unique=True, help_text='Chave do summon:bestiary{<slug>}.')
    tipo = models.CharField(db_column='Tipo', max_length=60, blank=True, null=True, help_text='Tipo (5etools type.type): undead, beast, fiend, construct…')
    tamanho = models.CharField(db_column='Tamanho', max_length=30, blank=True, null=True, help_text='T/S/M/L/H/G (5etools).')
    nd = models.CharField(db_column='ND', max_length=20, blank=True, null=True, help_text='Nível de Desafio / cr (ex.: 1/4, 1/2, 5). Forma Selvagem filtra por isto.')
    alinhamento = models.CharField(db_column='Alinhamento', max_length=40, blank=True, null=True)
    source = models.CharField(db_column='Source', max_length=60, blank=True, null=True, default='BonfireTales', help_text='Fonte (BonfireTales, XMM…).')
    ca = models.CharField(db_column='CA', max_length=40, blank=True, null=True, help_text='Número ou fórmula (atalho de display).')
    pv = models.CharField(db_column='PV', max_length=60, blank=True, null=True, help_text='Número ou fórmula (ex.: 5+5*classlvl) p/ companheiros que escalam.')
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
    source = models.CharField(db_column='Source', max_length=60, blank=True, null=True, default='BonfireTales')
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
