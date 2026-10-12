"""Task-oriented navigation for models already visible to Django Admin."""

ADMIN_GROUPS = (
    ("Comunidade", "comunidade", {
        "TbAventuraMestre", "TbConteudoEstatico", "TbReiDaColina",
    }),
    ("Personagens", "personagens", {
        "TbPersonagem", "TbPersonagemAventura", "TbPersonagemRevisao",
        "TbSolicitacaoTranscricao",
    }),
    ("Regras e conteúdo", "regras", {
        "TbAcessoopcao", "TbAntecedente", "TbArmadilha", "TbBestiario",
        "TbClasse", "TbClassehabilidade", "TbCondicao", "TbEssencia",
        "TbItemMagico", "TbItemMundano", "TbLinhagem", "TbMagia",
        "TbOpcaojogo", "TbRaca", "TbRecursoclasse", "TbSubclasse",
        "TbTalento", "TbTracoracial",
    }),
    ("Mundo", "mundo", {
        "TbMapDesenho", "TbMapLayer", "TbMapMarker", "TbOrganizacao",
        "TbRegiao", "TbTerritorio",
    }),
    ("Economia", "economia", {
        "AsaasCheckoutOrder", "MestreOuroDireito", "MestreOuroRevisao",
        "SocialCreditEntry", "SocialCreditPolicy",
        "SocialCreditReaderRecognition", "SocialCreditRedemption",
        "SocialCreditWallet", "TbEmprestimoPersonagem",
        "TbPersonagemTreinamento", "TbRecompensaMestre", "TbTransacao",
        "TbTransacaoMestre",
    }),
    ("Cosméticos e conquistas", "cosmeticos", {
        "CosmeticCheckoutOffer", "CosmeticCheckoutPurchase",
        "EventCosmeticOffer", "EventCosmeticRedemption", "TbConquista",
        "TbCosmetico", "TbEntregaEventoConquista", "TbEventoConquista",
        "TbUsuarioConquista", "TbUsuarioCosmetico",
    }),
    ("Integrações", "integracoes", {
        "BotCharacterLog", "BotDedicatedRank", "BotKeyValueStore",
        "BotMember", "BotQuest", "BotSchedulerJob", "BotTransaction",
        "ManagedApiKey",
    }),
    ("Operação", "operacao", {"DbAccessAudit", "Group", "User"}),
)

MODEL_GROUP = {
    model_name: slug
    for _title, slug, model_names in ADMIN_GROUPS
    for model_name in model_names
}


def grouped_admin_apps(app_dict, index_url):
    """Regroup only permission-filtered model entries returned by AdminSite."""
    groups = {
        slug: {
            "name": title,
            "app_label": slug,
            "app_url": index_url,
            "has_module_perms": True,
            "models": [],
        }
        for title, slug, _model_names in ADMIN_GROUPS
    }
    for app in app_dict.values():
        for model in app["models"]:
            slug = MODEL_GROUP.get(model["object_name"], "operacao")
            groups[slug]["models"].append(model)
    for group in groups.values():
        group["models"].sort(key=lambda model: model["name"].casefold())
    return [groups[slug] for _title, slug, _model_names in ADMIN_GROUPS
            if groups[slug]["models"]]
