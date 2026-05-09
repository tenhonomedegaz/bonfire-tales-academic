from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('cadastro/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='home/login.html', authentication_form=views.EmailOrUsernameAuthenticationForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('wiki/talentos/<int:talent_id>/editar/', views.wiki_update_talent, name='wiki_update_talent'),
    path('wiki/habilidades-classe/<int:feature_id>/editar/', views.wiki_update_class_feature, name='wiki_update_class_feature'),
    path('wiki/tracos-raciais/<int:trait_id>/editar/', views.wiki_update_racial_trait, name='wiki_update_racial_trait'),
    path('wiki/racas/<int:race_id>/editar/', views.wiki_update_race, name='wiki_update_race'),
    path('wiki/regioes/criar/', views.wiki_create_region, name='wiki_create_region'),
    path('wiki/regioes/<int:region_id>/editar/', views.wiki_update_region, name='wiki_update_region'),
    path('wiki/opcoes/<int:id>/editar/', views.wiki_update_option, name='wiki_update_option'),
    path('wiki/territorios/<int:territory_id>/editar/', views.wiki_update_territory, name='wiki_update_territory'),
    path('wiki/marcadores/<int:marker_id>/posicao/', views.wiki_update_marker_position, name='wiki_update_marker_position'),
    path('wiki/mapa/salvar-lote/', views.wiki_batch_save_map, name='wiki_batch_save_map'),
    
    path('', views.home_view, name='home'),
    path('jogador/classes/', views.classes_view, name='classes'),
    path('jogador/classes', views.classes_view),
    path('jogador/classes/<slug:slug>/', views.classe_detail_view, name='classe_detail'),
    path('jogador/raca/', views.racas_view, name='racas'),
    path('jogador/raca', views.racas_view),
    path('jogador/raca/<slug:slug>/', views.raca_detail_view, name='raca_detail'),
    path('sistemas/regras-e-punicoes/', views.regras_punicoes_view, name='regras_punicoes'),
    path('sistemas/regras-e-punicoes', views.regras_punicoes_view),
    path('mestre/se-tornando-mestre/', views.guia_mestres_view, name='guia_mestres'),
    path('mestre/se-tornando-mestre', views.guia_mestres_view),

    
    path('atualizacoes/', views.placeholder_view, {'title': 'Notas de Atualização'}, name='atualizacoes'),
    path('sistemas/criacao-de-ficha/', views.placeholder_view, {'title': 'Criação de Ficha'}, name='criacao_ficha'),
    path('sistemas/glossario/', views.placeholder_view, {'title': 'Glossário do Sistema'}, name='sistemas_glossario'),
    path('sistemas/missoes/', views.sistemas_missoes_view, name='sistemas_missoes'),
    
    path('jogador/antecedente/', views.antecedentes_view, name='jogador_antecedente'),
    path('jogador/antecedente', views.antecedentes_view),
    path('jogador/antecedentes/', views.antecedentes_view, name='jogador_antecedentes'),
    path('jogador/talentos/', views.talentos_view, name='jogador_talentos'),
    path('jogador/talentos', views.talentos_view),
    path('jogador/idiomas/', views.placeholder_view, {'title': 'Idiomas'}, name='jogador_idiomas'),
    path('jogador/opcoes-adicionais/', views.opcoes_view, name='jogador_opcoes'),
    path('api/opcoes/', views.api_opcoes, name='api_opcoes'),

    path('mestre/bestiario/', views.bestiario_view, name='mestre_bestiario'),
    path('mestre/armadilhas-e-perigos/', views.placeholder_view, {'title': 'Armadilhas e Perigos'}, name='mestre_armadilhas'),
    path('mestre/condicoes/', views.placeholder_view, {'title': 'Condições'}, name='mestre_condicoes'),
    path('mestre/mercado-de-mestre/', views.placeholder_view, {'title': 'Mercado de Mestre'}, name='mestre_mercado'),
    path('mestre/tipos-de-missoes/', views.placeholder_view, {'title': 'Tipos de Missões'}, name='mestre_tipos_missoes'),
    path('mestre/missoes/', views.placeholder_view, {'title': 'Conduzindo Missões'}, name='mestre_missoes'),

    path('mercado/armas/', views.itens_mundanos_view, name='mercado_armas'),
    path('mercado/itens-mundanos/', views.itens_mundanos_view, name='mercado_itens_mundanos'),
    path('mercado/itens-magicos/', views.itens_magicos_view, name='mercado_itens_magicos'),
    path('mercado/negociacoes/', views.placeholder_view, {'title': 'Negociações'}, name='mercado_negociacoes'),

    path('magias/escolas/', views.placeholder_view, {'title': 'Escolas de Magia'}, name='magias_escolas'),
    path('magias/listas/', views.magias_view, name='magias_listas'),
    path('magias/congregacao/', views.placeholder_view, {'title': 'Congregação Mágica'}, name='magias_congregacao'),
    
    path('mundo/cosmo/', views.placeholder_view, {'title': 'Cosmologia'}, name='mundo_cosmo'),
    path('mundo/linha-do-tempo/', views.placeholder_view, {'title': 'Linha do Tempo'}, name='mundo_linha_tempo'),
    path('mundo/regioes/', views.mundo_regioes_view, name='mundo_regioes'),
    path('mundo/regioes/<slug:slug>/', views.regiao_detail_view, name='regiao_detail'),
    path('mundo/organizacoes/', views.organizacoes_view, name='mundo_organizacoes'),
    path('mundo/bestiario/', views.bestiario_view, name='mundo_bestiario'),
    path('mundo/faccoes/', views.placeholder_view, {'title': 'Facções'}, name='mundo_faccoes'),

    
    path('mundo/jornal/', views.jornal_list_view, name='mundo_jornal'),
    path('mundo/jornal/novo/', views.jornal_create_view, name='jornal_create'),
    path('mundo/jornal/importar-gdoc/', views.jornal_import_gdoc, name='jornal_import_gdoc'),
    path('mundo/jornal/<slug:slug>/', views.jornal_detail_view, name='jornal_detail'),
    path('mundo/jornal/<slug:slug>/editar/', views.jornal_update_view, name='jornal_update'),

    
    path('mundo/cronicas/', views.cronicas_list_view, name='mundo_cronicas'),
    path('mundo/cronicas/nova/', views.cronica_create_view, name='cronica_create'),
    path('mundo/cronicas/revisao/', views.cronicas_review_view, name='cronicas_review'),
    path('mundo/cronicas/<slug:slug>/', views.cronica_detail_view, name='cronica_detail'),
    path('mundo/cronicas/<slug:slug>/editar/', views.cronica_edit_view, name='cronica_edit'),
    path('mundo/cronicas/<int:cronica_id>/revisar/', views.cronica_review_action, name='cronica_review_action'),

    path('mapa/', views.mapa_view, name='mapa'),
    path('mapa', views.mapa_view),
    path('colaborador/', views.placeholder_view, {'title': 'Colaborador'}, name='colaborador'),
    path('catarse/', views.placeholder_view, {'title': 'Apoie no Catarse'}, name='catarse'),
    path('quem-somos/', views.placeholder_view, {'title': 'Quem Somos'}, name='quem_somos'),
]
