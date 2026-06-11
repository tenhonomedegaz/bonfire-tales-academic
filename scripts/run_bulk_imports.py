import os
import sys
import json
import django

# Set up Django environment
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bonfire.settings")
django.setup()

from django.db import transaction
from home.models import TbRaca, TbLinhagem, TbEssencia, TbTracoracial
from home.admin import _parse_raca_import_txt, _parse_essencia_import_txt

def import_raca(file_name, raca_slug):
    file_path = os.path.join("ref", file_name)
    print(f"\n--- Importing Race from {file_path} ---")
    raca = TbRaca.objects.filter(slug=raca_slug).first()
    if not raca:
        print(f"Error: Race {raca_slug} not found.")
        return
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    tracos, errors = _parse_raca_import_txt(content, raca)
    if errors:
        print("Parsing errors found:")
        for err in errors:
            print(" -", err)
        # We can still proceed if there are valid items, but let's be careful
        
    tracos_criados = tracos_atualizados = linhagens_criadas = linhagens_atualizadas = 0
    raca_metadata_atualizado = False
    
    with transaction.atomic():
        for item in tracos:
            tipo_reg = item.get("tipo_registro", "traco")
            if tipo_reg == "raca":
                if item["slug"] == raca.slug:
                    raca.tagline = item.get("tagline") or raca.tagline
                    raca.lore_presentation = item.get("lore_presentation") or raca.lore_presentation
                    raca.lore_roleplay = item.get("lore_roleplay") or raca.lore_roleplay
                    raca.lore_society = item.get("lore_society") or raca.lore_society
                    raca.save()
                    raca_metadata_atualizado = True
            elif tipo_reg == "linhagem":
                linhagem, created = TbLinhagem.objects.get_or_create(
                    slug=item["slug"],
                    defaults={"id_raca": raca, "nome": item["nome"]}
                )
                linhagem.descricao = item.get("descricao") or linhagem.descricao
                linhagem.lore_presentation = item.get("lore_presentation") or linhagem.lore_presentation
                linhagem.lore_roleplay = item.get("lore_roleplay") or linhagem.lore_roleplay
                linhagem.lore_society = item.get("lore_society") or linhagem.lore_society
                linhagem.save()
                if created:
                    linhagens_criadas += 1
                else:
                    linhagens_atualizadas += 1
            else:
                linhagem_obj = None
                if item.get("linhagem_slug"):
                    linhagem_obj = TbLinhagem.objects.filter(slug=item["linhagem_slug"], id_raca=raca).first()
                
                query = TbTracoracial.objects.filter(
                    nome=item["nome"],
                    id_raca_id=raca.id_raca,
                    id_linhagem=linhagem_obj,
                    id_essencia=None,
                )
                existing = query.first()
                if existing:
                    existing.descricao = item["descricao"]
                    existing.nivel_requisito = item["nivel_requisito"]
                    existing.talento_racial = item["talento_racial"]
                    existing.pre_requisito = item["pre_requisito"]
                    existing.tags_json = item["tags_json"]
                    existing.save()
                    tracos_atualizados += 1
                    continue

                TbTracoracial.objects.create(
                    nome=item["nome"],
                    descricao=item["descricao"],
                    nivel_requisito=item["nivel_requisito"],
                    talento_racial=item["talento_racial"],
                    pre_requisito=item["pre_requisito"],
                    tags_json=item["tags_json"],
                    id_raca=raca,
                    id_linhagem=linhagem_obj,
                    id_essencia=None,
                )
                tracos_criados += 1

    print(f"Import finished for race {raca.nome}:")
    print(f" - Race metadata updated: {raca_metadata_atualizado}")
    print(f" - Lineages created: {linhagens_criadas}, updated: {linhagens_atualizadas}")
    print(f" - Traits/Talents created: {tracos_criados}, updated: {tracos_atualizados}")


def import_essencia(file_name, essencia_slug, essencia_nome):
    file_path = os.path.join("ref", file_name)
    print(f"\n--- Importing Essence from {file_path} ---")
    essencia, created_ess = TbEssencia.objects.get_or_create(
        slug=essencia_slug,
        defaults={"nome": essencia_nome}
    )
    if created_ess:
        print(f"Created new Essence: {essencia.nome}")
    else:
        print(f"Found existing Essence: {essencia.nome}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    tracos, errors = _parse_essencia_import_txt(content, essencia)
    if errors:
        print("Parsing errors found:")
        for err in errors:
            print(" -", err)
            
    tracos_criados = tracos_atualizados = 0
    essencia_metadata_atualizado = False
    
    with transaction.atomic():
        for item in tracos:
            tipo_reg = item.get("tipo_registro", "traco")
            if tipo_reg == "essencia":
                if item["slug"] == essencia.slug:
                    essencia.lore_presentation = item.get("lore_presentation") or essencia.lore_presentation
                    essencia.lore_roleplay = item.get("lore_roleplay") or essencia.lore_roleplay
                    essencia.lore_society = item.get("lore_society") or essencia.lore_society
                    essencia.save()
                    essencia_metadata_atualizado = True
            else:
                query = TbTracoracial.objects.filter(
                    nome=item["nome"],
                    id_essencia_id=essencia.id_essencia,
                    id_raca=None,
                    id_linhagem=None,
                )
                existing = query.first()
                if existing:
                    existing.descricao = item["descricao"]
                    existing.nivel_requisito = item["nivel_requisito"]
                    existing.talento_racial = item["talento_racial"]
                    existing.pre_requisito = item["pre_requisito"]
                    existing.tags_json = item["tags_json"]
                    existing.save()
                    tracos_atualizados += 1
                    continue

                TbTracoracial.objects.create(
                    nome=item["nome"],
                    descricao=item["descricao"],
                    nivel_requisito=item["nivel_requisito"],
                    talento_racial=item["talento_racial"],
                    pre_requisito=item["pre_requisito"],
                    tags_json=item["tags_json"],
                    id_essencia=essencia,
                    id_raca=None,
                    id_linhagem=None,
                )
                tracos_criados += 1

    print(f"Import finished for essence {essencia.nome}:")
    print(f" - Essence metadata updated: {essencia_metadata_atualizado}")
    print(f" - Traits/Talents created: {tracos_criados}, updated: {tracos_atualizados}")


if __name__ == "__main__":
    import_raca("Anão in Bonfire Tales RPG _ World Anvil_import.txt", "anao")
    import_essencia("Vampirismo in Bonfire Tales RPG _ World Anvil_import.txt", "vampirismo", "Vampirismo")
    import_essencia("Nephilim in Bonfire Tales RPG _ World Anvil_import.txt", "nephilim", "Nephilim")
