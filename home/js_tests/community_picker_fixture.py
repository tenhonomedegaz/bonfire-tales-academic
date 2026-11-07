"""Render the real picker against public example data; never load the project DB."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from django.conf import settings
settings.configure(SECRET_KEY='local-community-picker-preview',STATIC_URL='/static/',
  ROOT_URLCONF='home.test_cosmetic_picker',SITE_POSTGRES_TABLES={},
  INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','home'],
  DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},
  TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}])
import django
django.setup()
from django.template import Context,Template
from home.cosmetic_packages import load_package
from home.cosmetic_picker import picker_items

if '--test' in sys.argv:
  from django.test.runner import DiscoverRunner
  modules=['home.test_cosmetic_picker','home.test_cosmetic_catalog_tiles','home.test_cosmetic_packages',
           'home.test_community_cosmetics','home.test_cosmetic_retraction','home.test_rank_metal_presentation']
  sys.exit(bool(DiscoverRunner(verbosity=1).run_tests(modules)))

release=json.loads((ROOT/'docs/cosmetics/community-catalog-release.json').read_text(encoding='utf-8'))
sources=json.loads((ROOT/'docs/cosmetics/community-art-sources.json').read_text(encoding='utf-8'))
catalog={kind:[] for kind in ('tema','moldura','efeito')}
def item(key,label,kind,*,css='',definition=None,origin='livre',selected=False,hint=''):
  row={'key':key,'slug':kind+'-'+key,'label':label,'class':css,'definicao':definition or {},
       'estado':'livre' if origin=='livre' else 'bloqueado','selected':selected,
       'origem':origin,'unlock_hint':hint,'descricao':hint,'css_url':'','escopo':'ambos'}
  catalog[kind].append(row)
  return row
item('bonfire','Bonfire','tema',css='theme-bonfire',selected=True)
for key,label,css in [('ember','Brasas de Cineria','theme-ember'),('arcane','Arcano Violeta','theme-arcane'),
                       ('verdant','Bosque Esmeralda','theme-verdant'),('moonlit','Luar Prateado','theme-moonlit'),
                       ('custom','Personalizado','theme-custom')]:
  item(key,label,'tema',css=css)
item('none','Sem moldura','moldura',selected=True)
for row in sources['frames']:
  if row['key']=='guardiao-da-fogueira':continue
  description=next(r['descricao'] for r in release['updates'] if r['slug']=='moldura-'+row['key'])
  item(row['key'],row['name'],'moldura',hint=description)
item('none','Sem efeito','efeito',selected=True)
for key,label in [('soft-glow','Brilho suave'),('glass','Vidro escuro'),('embers','Brasas discretas'),
                  ('aurora','Aurora'),('starfall','Chuva de estrelas')]:
  item(key,label,'efeito',css='effect-'+key)
for row in release['create_if_missing']:
  key=row['slug'].removeprefix(row['tipo']+'-')
  i=item(key,row['nome'],row['tipo'],css=row['css_class'],definition=row.get('definicao_json'),
       origin=row['origem'],hint=row['descricao'])
  if row['origem']=='colaborador':i['unlock_hint']='Beneficio de colaborador ativo, a partir do plano Conde.'
for row in json.loads((ROOT/'docs/cosmetics/rank-metal-catalog.json').read_text(encoding='utf-8'))['cosmetics']:
  key=row['slug'].removeprefix('tema-')
  item(key,row['nome'],'tema',css=row['css_class'],definition=row['definicao_json'],origin='conquista',hint='Liberado por conquista de rank.')

previews={}
for kind,rows in catalog.items():
  for row in picker_items(rows,kind,'perfil'):
    locked=row['estado']=='bloqueado'
    acquisition={'label':'Conhecer a colaboracao','url':'/colaborador/'} if row['origem']=='colaborador' else {'label':'Ver conquistas','url':'/perfil/#conquistas'} if locked else {'label':'','url':''}
    previews[kind+':'+row['key']]={
      'key':row['key'],'tipo':kind,'label':row['label'],'description':row['descricao'],
      'locked':locked,'unlock_hint':row['unlock_hint'] if locked else 'Disponivel para usar.',
      'acquisition':acquisition,'package':load_package(kind,row['key']),
      'css_class':row['class'],'theme_definition':row['definicao'],'theme_css_url':'',
      'theme_category':row['category'],'thumbnail_url':row['thumbnail_url']}

template=Template('''{% load cosmetic_packages %}<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bonfire | Aparencia</title>
{% for css in styles %}<link rel="stylesheet" href="/static/{{ css }}">{% endfor %}
<style>body{margin:0;background:#101112;color:#ede8e2;font:14px Arial,sans-serif;--bg1:#1c1b1e;--stroke:#4b4145;--text:#ede8e2}main{max-width:1100px;margin:auto;padding:32px 24px}.brand{display:flex;align-items:center;gap:14px;border-bottom:1px solid #593a3a;padding-bottom:20px;margin-bottom:36px}.brand img{width:44px;height:44px;object-fit:contain}.brand strong{font:700 24px Georgia,serif}.preview-label{margin-left:auto;color:#bcb4b5;font-size:12px}h1{font:700 25px Georgia,serif;margin:0 0 24px}.editor-band{border-top:1px solid #493d43;padding-top:24px}.custom-colors{display:flex;gap:16px;margin-top:30px;flex-wrap:wrap}.custom-colors[hidden]{display:none}.custom-colors label{font-size:12px;display:grid;gap:8px}.custom-colors input{width:52px;height:32px;padding:0;border:1px solid #555;background:transparent}.preview-fields{display:none}@media(max-width:600px){main{padding:24px 16px}.brand strong{font-size:20px}}</style></head><body>
<main id="profile-root" class="profile-page theme-bonfire" data-theme-category="classico"><header class="brand"><img src="/static/brand/icon.png" alt=""><strong>Bonfire Tales</strong><span class="preview-label">Previa local</span></header>
<h1>Aparencia do perfil</h1><form id="perfil-form" class="editor-band"><div class="preview-fields"><input name="username" value="Aventureiro de Cineria"><input name="bio" value="Onde aventureiros descansam e historias comecam."><input name="avatar_url" value="/static/brand/human.webp"><input name="banner_url" value="/static/brand/world.webp"></div>
<div class="profile-cosmetic-launchers">{% cosmetic_catalog themes 'tema' 'id_profile_theme' 'profile_theme' 'bonfire' 'perfil' 'Tema' %}{% cosmetic_catalog frames 'moldura' 'id_avatar_frame' 'avatar_frame' 'none' 'perfil' 'Moldura' %}{% cosmetic_catalog effects 'efeito' 'id_profile_effect' 'profile_effect' 'none' 'perfil' 'Efeito' %}</div>
<div class="custom-colors" id="profile-custom-controls" hidden><label>Destaque<input type="color" name="custom_accent" value="#ef905f"></label><label>Secundaria<input type="color" name="custom_accent2" value="#b86a93"></label><label>Superficie<input type="color" name="custom_surface" value="#1b1c20"></label><label>Fundo<input type="color" name="custom_deep" value="#101112"></label></div>
</form></main><script src="/static/cosmetics/renderer.js" defer></script><script src="/static/js/tema_swatch.js" defer></script><script src="/static/js/profile-effects.js" defer></script><script src="/static/js/cosmetic-catalog.js" defer></script>
<script>document.addEventListener('DOMContentLoaded',()=>{const theme=document.getElementById('id_profile_theme');theme.addEventListener('change',()=>document.getElementById('profile-custom-controls').hidden=theme.value!=='custom');document.getElementById('perfil-form').addEventListener('submit',e=>e.preventDefault());});</script></body></html>''')
styles=['css/brand.css','css/pages/perfil.css','css/pages/perfil-fx.css',
        'css/components/cosmetic-presentation.css','css/components/illustrated-theme-skins.css',
        'css/components/rank-theme-skins.css','css/components/profile-effects.css','css/components/cosmetic-catalog.css']
html=template.render(Context({'themes':catalog['tema'],'frames':catalog['moldura'],'effects':catalog['efeito'],'styles':styles}))
print(json.dumps({'html':html,'previews':previews},ensure_ascii=False))
