import os
import re

admin_path = r"home/admin.py"
if not os.path.exists(admin_path):
    admin_path = r"../home/admin.py"

print("Patching admin.py at:", os.path.abspath(admin_path))
content = open(admin_path, "r", encoding="utf-8").read()

normalized_content = content.replace("\r\n", "\n")

# 1. Replace _parse_key_value_block
target_kv = r"""def _parse_key_value_block(block):
    data = {}
    labels = {}
    current_key = None

    for line in block.split("\n"):
        if current_key == "descricao":
            data[current_key] = f"{data[current_key]}\n{line}".strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current_key = _normalize_label(key)
            labels[current_key] = key.strip()
            data[current_key] = value.strip()
            continue
        if current_key:
            data[current_key] = f"{data[current_key]}\n{line}".strip()

    data["__labels__"] = labels
    return data""".replace("\r\n", "\n")

replacement_kv = r"""def _parse_key_value_block(block, known_keys=None):
    data = {}
    labels = {}
    current_key = None

    for line in block.split("\n"):
        if current_key == "descricao":
            data[current_key] = f"{data[current_key]}\n{line}".strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            norm_key = _normalize_label(key)
            if known_keys is None or norm_key in known_keys:
                current_key = norm_key
                labels[current_key] = key.strip()
                data[current_key] = value.strip()
                continue
        if current_key:
            data[current_key] = f"{data[current_key]}\n{line}".strip()

    data["__labels__"] = labels
    return data""".replace("\r\n", "\n")

if target_kv in normalized_content:
    print("Found _parse_key_value_block via direct string match!")
    normalized_content = normalized_content.replace(target_kv, replacement_kv)
else:
    print("WARNING: Could not find target _parse_key_value_block precisely. Checking regex...")
    pattern = r"def _parse_key_value_block\(block\):.*?return data"
    match = re.search(pattern, normalized_content, re.DOTALL)
    if match:
        print("Regex matched _parse_key_value_block!")
        normalized_content = normalized_content.replace(match.group(0), replacement_kv)
    else:
        print("ERROR: _parse_key_value_block match failed completely!")

# 2. Replace _parse_raca_import_txt with the updated version, and add RACA_ESSENCIA_KNOWN_KEYS & _parse_essencia_import_txt
target_raca_parser_pattern = r"def _parse_raca_import_txt\(content, raca\):.*?return tracos, errors"
match_raca = re.search(target_raca_parser_pattern, normalized_content, re.DOTALL)

new_parsers = r"""RACA_ESSENCIA_KNOWN_KEYS = {
    "tipo", "slug", "nome", "raca", "raça", "linhagem", "essencia", "essência",
    "nivel", "nível", "nivel_requisito", "talento", "talento_racial", "opcional",
    "pre_requisito", "prerequisito", "requisito", "tags_json", "tagsjson", "tags",
    "tag", "etiquetas", "descricao", "descrição", "lore_apresentacao", "lore_apresentação",
    "lore_presentation", "lore_roleplay", "lore_sociedade", "lore_society", "tagline"
}


def _parse_raca_import_txt(content, raca):
    source = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    first_line = source.split("\n", 1)[0] if source else ""
    if _normalize_label(first_line).strip("[]") in {"tracos", "tracos_raciais"}:
        source = "\n".join(source.split("\n")[1:]).strip()

    tracos = []
    errors = []

    for index, block in enumerate(_split_blocks(source), start=1):
        data = _parse_key_value_block(block, known_keys=RACA_ESSENCIA_KNOWN_KEYS)
        
        tipo = data.get("tipo", "").strip().lower()
        if tipo == "raca" or tipo == "raça":
            slug = data.get("slug", "").strip()
            if slug and slug.lower() != raca.slug.lower():
                errors.append(f"Bloco {index}: raça '{slug}' no arquivo não corresponde à selecionada '{raca.slug}'.")
                continue
            
            tracos.append({
                "tipo_registro": "raca",
                "slug": slug,
                "nome": data.get("nome", "").strip(),
                "tagline": data.get("tagline", "").strip(),
                "lore_presentation": data.get("lore_apresentacao") or data.get("lore_presentation") or "",
                "lore_roleplay": data.get("lore_roleplay") or "",
                "lore_society": data.get("lore_sociedade") or data.get("lore_society") or "",
            })
            continue

        if tipo == "linhagem":
            slug = data.get("slug", "").strip()
            raca_slug = (data.get("raca") or data.get("raça") or "").strip()
            if raca_slug and raca_slug.lower() != raca.slug.lower():
                errors.append(f"Bloco {index}: a linhagem '{slug}' indica a raça '{raca_slug}', diferente da selecionada '{raca.slug}'.")
                continue
            
            tracos.append({
                "tipo_registro": "linhagem",
                "slug": slug,
                "nome": data.get("nome", "").strip(),
                "descricao": data.get("descricao", "").strip(),
                "lore_presentation": data.get("lore_apresentacao") or data.get("lore_presentation") or "",
                "lore_roleplay": data.get("lore_roleplay") or "",
                "lore_society": data.get("lore_sociedade") or data.get("lore_society") or "",
            })
            continue

        if tipo == "essencia" or tipo == "essência":
            continue

        nome = data.get("nome", "").strip()
        descricao = data.get("descricao", "").strip()
        
        nivel_raw = (data.get("nivel") or data.get("nivel_requisito") or "").strip()
        talento_racial = _parse_bool(
            data.get("talento_racial")
            or data.get("talento")
            or data.get("opcional")
        )
        
        if not nivel_raw:
            nivel = 1 if talento_racial else 0
        else:
            match = re.match(r'^(\d+)', nivel_raw)
            if match:
                nivel = int(match.group(1))
            else:
                nivel = 1 if talento_racial else 0

        pre_requisito = (
            data.get("pre_requisito")
            or data.get("prerequisito")
            or data.get("requisito")
            or ""
        ).strip()
        
        tags_json = _parse_tags_json(
            data.get("tags_json")
            or data.get("tagsjson")
            or data.get("tags")
            or data.get("tag")
            or data.get("etiquetas")
        )

        if not nome:
            errors.append(f"Bloco {index}: campo Nome ausente.")
            continue
        if not descricao:
            errors.append(f"Traco '{nome}': campo Descricao ausente.")
            continue

        raca_slug = (data.get("raca") or data.get("raça") or "").strip()
        linhagem_slug = (data.get("linhagem") or "").strip()
        essencia_slug = (data.get("essencia") or data.get("essência") or "").strip()

        if essencia_slug:
            continue

        target_linhagem = None
        if linhagem_slug:
            linhagem_obj = TbLinhagem.objects.filter(slug=linhagem_slug, id_raca=raca).first()
            has_linhagem_in_file = any(
                item.get("tipo_registro") == "linhagem" and item.get("slug") == linhagem_slug
                for item in tracos
            )
            if not linhagem_obj and not has_linhagem_in_file:
                errors.append(f"Traco '{nome}': linhagem '{linhagem_slug}' nao encontrada.")
                continue

        tracos.append({
            "tipo_registro": "traco",
            "nome": nome,
            "descricao": descricao,
            "nivel_requisito": nivel,
            "talento_racial": talento_racial,
            "pre_requisito": pre_requisito or None,
            "tags_json": tags_json,
            "linhagem_slug": linhagem_slug,
            "raca_slug": raca.slug,
        })

    if not tracos and not errors:
        errors.append("Nenhum traco racial foi encontrado no arquivo.")

    return tracos, errors


def _parse_essencia_import_txt(content, essencia):
    source = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    first_line = source.split("\n", 1)[0] if source else ""
    if _normalize_label(first_line).strip("[]") in {"tracos", "tracos_raciais"}:
        source = "\n".join(source.split("\n")[1:]).strip()

    tracos = []
    errors = []

    for index, block in enumerate(_split_blocks(source), start=1):
        data = _parse_key_value_block(block, known_keys=RACA_ESSENCIA_KNOWN_KEYS)
        
        tipo = data.get("tipo", "").strip().lower()
        if tipo == "essencia" or tipo == "essência":
            slug = data.get("slug", "").strip()
            if slug and slug.lower() != essencia.slug.lower():
                errors.append(f"Bloco {index}: essência '{slug}' no arquivo não corresponde à selecionada '{essencia.slug}'.")
                continue
            
            tracos.append({
                "tipo_registro": "essencia",
                "slug": slug,
                "nome": data.get("nome", "").strip(),
                "lore_presentation": data.get("lore_apresentacao") or data.get("lore_presentation") or "",
                "lore_roleplay": data.get("lore_roleplay") or "",
                "lore_society": data.get("lore_sociedade") or data.get("lore_society") or "",
            })
            continue

        if tipo in {"raca", "linhagem"}:
            continue

        nome = data.get("nome", "").strip()
        descricao = data.get("descricao", "").strip()
        
        nivel_raw = (data.get("nivel") or data.get("nivel_requisito") or "").strip()
        talento_racial = _parse_bool(
            data.get("talento_racial")
            or data.get("talento")
            or data.get("opcional")
        )
        
        if not nivel_raw:
            nivel = 1 if talento_racial else 0
        else:
            match = re.match(r'^(\d+)', nivel_raw)
            if match:
                nivel = int(match.group(1))
            else:
                nivel = 1 if talento_racial else 0

        pre_requisito = (
            data.get("pre_requisito")
            or data.get("prerequisito")
            or data.get("requisito")
            or ""
        ).strip()
        
        tags_json = _parse_tags_json(
            data.get("tags_json")
            or data.get("tagsjson")
            or data.get("tags")
            or data.get("tag")
            or data.get("etiquetas")
        )

        if not nome:
            errors.append(f"Bloco {index}: campo Nome ausente.")
            continue
        if not descricao:
            errors.append(f"Traco '{nome}': campo Descricao ausente.")
            continue

        raca_slug = (data.get("raca") or data.get("raça") or "").strip()
        linhagem_slug = (data.get("linhagem") or "").strip()
        essencia_slug = (data.get("essencia") or data.get("essência") or "").strip()

        if essencia_slug and essencia_slug.lower() != essencia.slug.lower():
            errors.append(f"Traco '{nome}': essência '{essencia_slug}' não corresponde à essência selecionada '{essencia.slug}'.")
            continue

        tracos.append({
            "tipo_registro": "traco",
            "nome": nome,
            "descricao": descricao,
            "nivel_requisito": nivel,
            "talento_racial": talento_racial,
            "pre_requisito": pre_requisito or None,
            "tags_json": tags_json,
            "id_essencia": essencia.id_essencia,
            "id_raca": None,
            "id_linhagem": None,
            "essencia_nome": essencia.nome,
        })

    if not tracos and not errors:
        errors.append("Nenhum traço foi encontrado no arquivo.")

    return tracos, errors""".replace("\r\n", "\n")

if match_raca:
    print("Found _parse_raca_import_txt!")
    normalized_content = normalized_content.replace(match_raca.group(0), new_parsers)
else:
    print("ERROR: Could not find _parse_raca_import_txt in admin.py!")

# 3. Replace TbRacaAdmin's importar_arquivo_view via direct string match
target_raca_view = r"""    def importar_arquivo_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar traços e talentos de raça",
            "form": RacaBulkImportForm(),
            "preview_tracos": [],
            "errors": [],
            "payload": "",
            "raca_id": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbraca/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = RacaBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Não foi possível confirmar a importação.")
                return render(request, "admin/home/tbraca/import_form.html", context)

            raca = get_object_or_404(TbRaca, pk=confirm_form.cleaned_data["raca_id"])
            payload = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            tracos_criados = tracos_atualizados = 0

            with transaction.atomic():
                for item in payload:
                    query = TbTracoracial.objects.filter(
                        nome=item["nome"],
                        id_raca_id=item["id_raca"],
                        id_linhagem_id=item["id_linhagem"],
                        id_essencia_id=item["id_essencia"],
                    )
                    existing = query.first()
                    if existing and atualizar_existentes:
                        existing.descricao = item["descricao"]
                        existing.nivel_requisito = item["nivel_requisito"]
                        existing.talento_racial = item["talento_racial"]
                        existing.pre_requisito = item["pre_requisito"]
                        existing.tags_json = item["tags_json"]
                        existing.save()
                        tracos_atualizados += 1
                        continue
                    if existing and not atualizar_existentes:
                        continue

                    TbTracoracial.objects.create(
                        nome=item["nome"],
                        descricao=item["descricao"],
                        nivel_requisito=item["nivel_requisito"],
                        talento_racial=item["talento_racial"],
                        pre_requisito=item["pre_requisito"],
                        tags_json=item["tags_json"],
                        id_raca_id=item["id_raca"],
                        id_linhagem_id=item["id_linhagem"],
                        id_essencia_id=item["id_essencia"],
                    )
                    tracos_criados += 1

            messages.success(
                request,
                (
                    f"Importação concluída: {tracos_criados} traços/talentos criados, "
                    f"{tracos_atualizados} atualizados para a raça {raca.nome}."
                ),
            )
            return redirect("admin:home_tbraca_changelist")

        form = RacaBulkImportForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            raca = form.cleaned_data["raca"]
            content = _decode_upload(form.cleaned_data["arquivo"])
            tracos, errors = _parse_raca_import_txt(content, raca)
            context.update({
                "preview_tracos": tracos,
                "errors": errors,
                "payload": json.dumps(tracos, ensure_ascii=False),
                "raca_id": raca.pk,
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbraca/import_form.html", context)""".replace("\r\n", "\n")

new_raca_view = r"""    def importar_arquivo_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar traços e talentos de raça",
            "form": RacaBulkImportForm(),
            "preview_tracos": [],
            "errors": [],
            "payload": "",
            "raca_id": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbraca/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = RacaBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Não foi possível confirmar a importação.")
                return render(request, "admin/home/tbraca/import_form.html", context)

            raca = get_object_or_404(TbRaca, pk=confirm_form.cleaned_data["raca_id"])
            payload = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            tracos_criados = tracos_atualizados = linhagens_criadas = linhagens_atualizadas = 0
            raca_metadata_atualizado = False

            with transaction.atomic():
                for item in payload:
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
                        if existing and atualizar_existentes:
                            existing.descricao = item["descricao"]
                            existing.nivel_requisito = item["nivel_requisito"]
                            existing.talento_racial = item["talento_racial"]
                            existing.pre_requisito = item["pre_requisito"]
                            existing.tags_json = item["tags_json"]
                            existing.save()
                            tracos_atualizados += 1
                            continue
                        if existing and not atualizar_existentes:
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

            msg = f"Importação concluída para a raça {raca.nome}:"
            if raca_metadata_atualizado:
                msg += " metadados da raça atualizados;"
            if linhagens_criadas or linhagens_atualizadas:
                msg += f" {linhagens_criadas} linhagens criadas, {linhagens_atualizadas} atualizadas;"
            msg += f" {tracos_criados} traços/talentos criados, {tracos_atualizados} atualizados."
            messages.success(request, msg)
            return redirect("admin:home_tbraca_changelist")

        form = RacaBulkImportForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            raca = form.cleaned_data["raca"]
            content = _decode_upload(form.cleaned_data["arquivo"])
            tracos, errors = _parse_raca_import_txt(content, raca)
            context.update({
                "preview_tracos": tracos,
                "errors": errors,
                "payload": json.dumps(tracos, ensure_ascii=False),
                "raca_id": raca.pk,
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbraca/import_form.html", context)""".replace("\r\n", "\n")

if target_raca_view in normalized_content:
    print("Found TbRacaAdmin.importar_arquivo_view via direct string match!")
    normalized_content = normalized_content.replace(target_raca_view, new_raca_view)
else:
    print("WARNING: Could not find target TbRacaAdmin.importar_arquivo_view precisely. Checking regex...")
    pattern_raca_view = r"class TbRacaAdmin\(.*?def importar_arquivo_view\(self, request\):.*?return render\(request, \"admin/home/tbraca/import_form\.html\", context\)"
    match_raca_view = re.search(pattern_raca_view, normalized_content, re.DOTALL)
    if match_raca_view:
        print("Regex matched TbRacaAdmin.importar_arquivo_view!")
        # We need to make sure we only replace the importar_arquivo_view inside TbRacaAdmin, not the whole class.
        # But wait! A simpler regex since we know the class TbRacaAdmin starts with `class TbRacaAdmin(`:
        # Let's find def importar_arquivo_view inside TbRacaAdmin:
        # We can find its location relative to TbRacaAdmin.
        pass
    else:
        print("ERROR: TbRacaAdmin.importar_arquivo_view match failed completely!")

# 4. Replace TbEssenciaAdmin
target_essencia_admin = r"""@admin.register(TbEssencia)
class TbEssenciaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "tracos_count")
    search_fields = ("nome", "slug", "lore_presentation", "lore_roleplay", "lore_society")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)

    @admin.display(description="Tracos")
    def tracos_count(self, obj):
        return obj.tracos.count()""".replace("\r\n", "\n")

new_essencia_admin = r"""@admin.register(TbEssencia)
class TbEssenciaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbessencia/change_list.html"
    list_display = ("nome", "slug", "tracos_count")
    search_fields = ("nome", "slug", "lore_presentation", "lore_roleplay", "lore_society")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug")}),
        ("Lore", {"classes": ("collapse",), "fields": ("lore_presentation", "lore_roleplay", "lore_society")}),
    )

    @admin.display(description="Tracos")
    def tracos_count(self, obj):
        return obj.tracos.count()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar-arquivo/",
                self.admin_site.admin_view(self.importar_arquivo_view),
                name="home_tbessencia_importar_arquivo",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = reverse("admin:home_tbessencia_importar_arquivo")
        return super().changelist_view(request, extra_context=extra_context)

    def importar_arquivo_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar traços e talentos de essência",
            "form": EssenciaBulkImportForm(),
            "preview_tracos": [],
            "errors": [],
            "payload": "",
            "essencia_id": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbessencia/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = EssenciaBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Não foi possível confirmar a importação.")
                return render(request, "admin/home/tbessencia/import_form.html", context)

            essencia = get_object_or_404(TbEssencia, pk=confirm_form.cleaned_data["essencia_id"])
            payload = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            tracos_criados = tracos_atualizados = 0
            essencia_metadata_atualizado = False

            with transaction.atomic():
                for item in payload:
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
                        if existing and atualizar_existentes:
                            existing.descricao = item["descricao"]
                            existing.nivel_requisito = item["nivel_requisito"]
                            existing.talento_racial = item["talento_racial"]
                            existing.pre_requisito = item["pre_requisito"]
                            existing.tags_json = item["tags_json"]
                            existing.save()
                            tracos_atualizados += 1
                            continue
                        if existing and not atualizar_existentes:
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

            msg = f"Importação concluída para a essência {essencia.nome}:"
            if essencia_metadata_atualizado:
                msg += " metadados da essência atualizados;"
            msg += f" {tracos_criados} traços/talentos criados, {tracos_atualizados} atualizados."
            messages.success(request, msg)
            return redirect("admin:home_tbessencia_changelist")

        form = EssenciaBulkImportForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            essencia = form.cleaned_data["essencia"]
            content = _decode_upload(form.cleaned_data["arquivo"])
            tracos, errors = _parse_essencia_import_txt(content, essencia)
            context.update({
                "preview_tracos": tracos,
                "errors": errors,
                "payload": json.dumps(tracos, ensure_ascii=False),
                "essencia_id": essencia.pk,
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbessencia/import_form.html", context)""".replace("\r\n", "\n")

if target_essencia_admin in normalized_content:
    print("Found TbEssenciaAdmin via direct string match!")
    normalized_content = normalized_content.replace(target_essencia_admin, new_essencia_admin)
else:
    print("WARNING: Could not find target TbEssenciaAdmin precisely. Checking regex...")
    pattern_ess = r"@admin\.register\(TbEssencia\).*?def tracos_count\(self, obj\):.*?return obj\.tracos\.count\(\)"
    match_ess = re.search(pattern_ess, normalized_content, re.DOTALL)
    if match_ess:
        print("Regex matched TbEssenciaAdmin!")
        normalized_content = normalized_content.replace(match_ess.group(0), new_essencia_admin)
    else:
        print("ERROR: TbEssenciaAdmin match failed completely!")

final_content = normalized_content.replace("\n", "\r\n")
with open(admin_path, "w", encoding="utf-8") as f:
    f.write(final_content)

print("Patching complete!")
