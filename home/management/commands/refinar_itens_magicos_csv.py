# -*- coding: utf-8 -*-
"""Refina descricoes de TbItemMagico a partir de scratch/import_itens.

Usa apenas db_slug para encontrar o item e description_en como fonte textual.
Campos source/page do CSV sao ignorados: fonte e referencia de importacao, nao
conteudo do item.
"""
import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


CSV_DEFAULT = Path("scratch/import_itens/itens_descricoes_en.csv")

REPL = [
    (r"\bWhile you wear the holy symbol, you gain a \+(\d+) bonus to spell attack rolls and the saving throw DCs of your spells\b", r"Enquanto usa o simbolo sagrado, voce recebe +\1 de bonus nas jogadas de ataque de magia e nas CDs dos testes de resistencia de suas magias"),
    (r"\bWhile you wear this amulet, you can use your Channel Divinity feature without expending one of the feature's uses\b", "Enquanto usa este amuleto, voce pode usar sua caracteristica Canalizar Divindade sem gastar um dos usos dela"),
    (r"\bYou can cast\b", "Voce pode conjurar"),
    (r"\byou can cast\b", "voce pode conjurar"),
    (r"\bfrom the ring\b", "a partir do anel"),
    (r"\bfrom the item\b", "a partir do item"),
    (r"\bThe ring has (\d+) charges\b", r"O anel tem \1 cargas"),
    (r"\bYou can expend\b", "Voce pode gastar"),
    (r"\byou can expend\b", "voce pode gastar"),
    (r"\byou can\b", "voce pode"),
    (r"\bexpend (\d+) charges?\b", r"gastar \1 cargas"),
    (r"\bexpend its charges\b", "gastar suas cargas"),
    (r"\bits charges\b", "suas cargas"),
    (r"\b(\d+) charge to cast\b", r"\1 carga para conjurar"),
    (r"\b(\d+) charges as a\b", r"\1 cargas como uma"),
    (r"\bto cast\b", "para conjurar"),
    (r"\bto create up to four\b", "para criar ate quatro"),
    (r"\b3-foot-diameter spheres of lightning\b", "esferas de eletricidade de 3 pes de diametro"),
    (r"\bcharges to use the properties below\b", "cargas para usar as propriedades abaixo"),
    (r"\bto use the propriedades abaixo\b", "para usar as propriedades abaixo"),
    (r"\bLightning Spheres\b", "Esferas Eletricas"),
    (r"\bunoccupied space\b", "espaco desocupado"),
    (r"\byou can see\b", "que voce possa ver"),
    (r"\bwithin\b", "a ate"),
    (r"\bof yourself\b", "de voce"),
    (r"\byourself\b", "voce"),
    (r"\blast as long as you maintain\b", "duram enquanto voce mantiver"),
    (r"\bup to 1 minute\b", "por ate 1 minuto"),
    (r"\bsheds Dim Light\b", "emite luz fraca"),
    (r"\bradius\b", "raio"),
    (r"\bmove each sphere\b", "mover cada esfera"),
    (r"\bno farther than\b", "sem ultrapassar"),
    (r"\baway from\b", "de distancia de"),
    (r"\bEach sphere appears\b", "Cada esfera aparece"),
    (r"\bThe spheres\b", "As esferas"),
    (r"\bEach sphere\b", "Cada esfera"),
    (r"\bcomes within\b", "fica a ate"),
    (r"\bof a criatura\b", "de uma criatura"),
    (r"\bthat isn't behind\b", "que nao esteja atras de"),
    (r"\bThe first time\b", "Na primeira vez"),
    (r"\bother than you\b", "que nao seja voce"),
    (r"\bTotal Cover\b", "Cobertura Total"),
    (r"\bproperties below\b", "propriedades abaixo"),
    (r"\bvoce pode see\b", "que voce possa ver"),
    (r"\bin an espaco\b", "em um espaco"),
    (r"\band\b", "e"),
    (r"\bor\b", "ou"),
    (r"\bin a\b", "em um"),
    (r"\bAs a\b", "Como uma"),
    (r"\bup to\b", "ate"),
    (r"\bbut\b", "mas"),
    (r"\bConcentration\b", "Concentracao"),
    (r"\bMagic action\b", "acao magica"),
    (r"\bbonus action\b", "acao bonus"),
    (r"\bspells\b", "magias"),
    (r"\bspell\b", "magia"),
    (r"\bThis amulet bears the symbol of a deity inlaid with precious stones or metals\b", "Este amuleto traz o símbolo de uma divindade incrustado com pedras ou metais preciosos"),
    (r"\bThis finely detailed belt is made of dragonhide\b", "Este cinto finamente trabalhado é feito de couro de dragão"),
    (r"\bWhile wearing these wraps\b", "Enquanto usa estes envoltórios"),
    (r"\bWhile wearing this armor\b", "Enquanto usa esta armadura"),
    (r"\bwhile wearing this armor\b", "enquanto usa esta armadura"),
    (r"\bWhile you wear this item\b", "Enquanto você usa este item"),
    (r"\bWhile wearing this item\b", "Enquanto usa este item"),
    (r"\bWhile you wear (?:it|them)\b", "Enquanto usa o item"),
    (r"\bWhile wearing (?:it|them)\b", "Enquanto usa o item"),
    (r"\bWhile you hold this item\b", "Enquanto segura este item"),
    (r"\bWhile holding this item\b", "Enquanto segura este item"),
    (r"\bWhile you hold (?:it|them)\b", "Enquanto segura o item"),
    (r"\bWhile holding (?:it|them)\b", "Enquanto segura o item"),
    (r"\bwhile you are attuned to (?:it|them|this item)\b", "enquanto estiver sintonizado com o item"),
    (r"\bYou have a \+(\d+) bonus to AC\b", r"Você recebe +\1 de bônus na CA"),
    (r"\byou have a \+(\d+) bonus to AC\b", r"você recebe +\1 de bônus na CA"),
    (r"\bYou gain a \+(\d+) bonus to AC\b", r"Você recebe +\1 de bônus na CA"),
    (r"\byou gain a \+(\d+) bonus to AC\b", r"você recebe +\1 de bônus na CA"),
    (r"\bYou have a \+(\d+) bonus to attack and damage rolls\b", r"Você recebe +\1 de bônus nas jogadas de ataque e dano"),
    (r"\byou have a \+(\d+) bonus to attack and damage rolls\b", r"você recebe +\1 de bônus nas jogadas de ataque e dano"),
    (r"\bYou gain a \+(\d+) bonus to attack and damage rolls\b", r"Você recebe +\1 de bônus nas jogadas de ataque e dano"),
    (r"\byou gain a \+(\d+) bonus to attack and damage rolls\b", r"você recebe +\1 de bônus nas jogadas de ataque e dano"),
    (r"\bspell attack rolls\b", "jogadas de ataque de magia"),
    (r"\bsaving throw DCs\b", "CDs dos testes de resistência"),
    (r"\bspell save DC\b", "CD de resistência de magia"),
    (r"\bbonus to the saving throw DCs\b", "bônus nas CDs dos testes de resistência"),
    (r"\bThis item has (\d+) charges\b", r"Este item tem \1 cargas"),
    (r"\bThe item has (\d+) charges\b", r"O item tem \1 cargas"),
    (r"\bregains all expended charges daily at dawn\b", "recupera todas as cargas gastas diariamente ao amanhecer"),
    (r"\bregains (\d+)d(\d+) expended charges daily at dawn\b", r"recupera \1d\2 cargas gastas diariamente ao amanhecer"),
    (r"\bOnce this property is used, it can't be used again until the next dawn\b", "Depois de usar esta propriedade, ela não pode ser usada novamente até o próximo amanhecer"),
    (r"\bOnce used, this property can't be used again until the next dawn\b", "Depois de usada, esta propriedade não pode ser usada novamente até o próximo amanhecer"),
    (r"\bYou can use an action to\b", "Você pode usar uma ação para"),
    (r"\byou can use an action to\b", "você pode usar uma ação para"),
    (r"\bAs an action\b", "Como uma ação"),
    (r"\bas an action\b", "como uma ação"),
    (r"\bAs a bonus action\b", "Como uma ação bônus"),
    (r"\bas a bonus action\b", "como uma ação bônus"),
    (r"\bAs a reaction\b", "Como uma reação"),
    (r"\bas a reaction\b", "como uma reação"),
    (r"\bwithout expending a spell slot\b", "sem gastar espaço de magia"),
    (r"\bwithout expending one of the feature's uses\b", "sem gastar um dos usos da característica"),
    (r"\bmade with this magic weapon\b", "feitas com esta arma mágica"),
    (r"\bmade with your Unarmed Strikes\b", "feitas com seus Ataques Desarmados"),
    (r"\bThose strikes deal your choice of Force damage or their normal damage type\b", "Esses ataques causam dano de força ou seu tipo de dano normal, à sua escolha"),
    (r"\byou can use it as a spellcasting focus\b", "você pode usá-lo como foco de conjuração"),
    (r"\bChannel Divinity feature\b", "característica Canalizar Divindade"),
    (r"\bki features\b", "características de ki"),
    (r"\bMartial Arts die\b", "dado de Artes Marciais"),
    (r"\bki points\b", "pontos de ki"),
    (r"\bnormal damage type\b", "tipo de dano normal"),
    (r"\bof your spells\b", "de suas magias"),
    (r"\bof your spell\b", "de sua magia"),
    (r"\bcan't be used again until the next dawn\b", "não pode ser usado novamente até o próximo amanhecer"),
    (r"\bcan't use .* again until the next dawn\b", "não pode usar isso novamente até o próximo amanhecer"),
    (r"\bcreature\b", "criatura"),
    (r"\bcreatures\b", "criaturas"),
    (r"\btarget\b", "alvo"),
    (r"\btargets\b", "alvos"),
    (r"\bweapon\b", "arma"),
    (r"\bweapons\b", "armas"),
    (r"\barmor\b", "armadura"),
    (r"\bshield\b", "escudo"),
    (r"\battacks?\b", "ataque"),
    (r"\bdamage rolls?\b", "rolagens de dano"),
    (r"\battack rolls?\b", "jogadas de ataque"),
    (r"\bsaving throws?\b", "testes de resistência"),
    (r"\bability checks?\b", "testes de atributo"),
    (r"\bStrength\b", "Força"),
    (r"\bDexterity\b", "Destreza"),
    (r"\bConstitution\b", "Constituição"),
    (r"\bIntelligence\b", "Inteligência"),
    (r"\bWisdom\b", "Sabedoria"),
    (r"\bCharisma\b", "Carisma"),
    (r"\bAcid damage\b", "dano ácido"),
    (r"\bCold damage\b", "dano de frio"),
    (r"\bFire damage\b", "dano de fogo"),
    (r"\bForce damage\b", "dano de força"),
    (r"\bLightning damage\b", "dano elétrico"),
    (r"\bNecrotic damage\b", "dano necrótico"),
    (r"\bPoison damage\b", "dano venenoso"),
    (r"\bPsychic damage\b", "dano psíquico"),
    (r"\bRadiant damage\b", "dano radiante"),
    (r"\bThunder damage\b", "dano trovejante"),
    (r"\bpiercing damage\b", "dano perfurante"),
    (r"\bslashing damage\b", "dano cortante"),
    (r"\bbludgeoning damage\b", "dano contundente"),
    (r"\bfeet\b", "pés"),
    (r"\bfoot\b", "pé"),
    (r"\bDC\b", "CD"),
    (r"\broll a d(\d+)\b", r"role 1d\1"),
]

POST_REPL = [
    ("Plate Armor of Etherealness", "Armadura de Placas da Eterealidade"),
    ("Orrery of the Wanderer", "Orrery do Andarilho"),
    ("The Witherbloom Primer", "A Cartilha de Witherbloom"),
    ("Witherbloom College", "Colégio Witherbloom"),
    ("Turn Undead", "Expulsar Mortos-vivos"),
    ("Turn the Unholy", "Expulsar Profanos"),
    ("Finesse", "Acuidade"),
    ("Icewind Dale: Rime of the Frostmaiden", "Vale do Vento Gélido: Canção da Donzela do Gelo"),
    ("The Everlight", "A Luz Eterna"),
    ("Chroma Conclave", "Conclave Cromático"),
    ("The Whispered One", "O Sussurrado"),
    ("to use the propriedades abaixo", "para usar as propriedades abaixo"),
    ("Lightning Spheres", "Esferas Eletricas"),
    ("in an espaco desocupado voce pode see", "em um espaco desocupado que voce possa ver"),
    ("the sphere comes a ate", "a esfera fica a ate"),
    ("of a criatura", "de uma criatura"),
    ("the sphere discharges lightning at that criatura e disappears", "a esfera descarrega eletricidade naquela criatura e desaparece"),
    ("That criatura makes", "Essa criatura faz"),
    ("On a failed save", "Em uma falha"),
    ("takes dano", "sofre dano"),
]


def load_spell_names():
    out = {}
    for path in (Path("ref/Livros/magias_en_pt.csv"), Path("ref/Livros/magias_alinhado.csv")):
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                en = row.get("magia_en") or row.get("en")
                pt = row.get("nome_pt") or row.get("final") or row.get("adaptado")
                if en and pt:
                    out[en] = pt
    return dict(sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True))


def translate(text, spell_names=None):
    text = (text or "").strip()
    if not text:
        return ""
    # Drop enormous variant base item lists; they are import/reference noise.
    text = re.sub(r"\n\nBase items\..*\Z", "", text, flags=re.S)
    text = re.sub(r"\n\nBase Items\..*\Z", "", text, flags=re.S)
    out = text
    for pat, repl in REPL:
        out = re.sub(pat, repl, out, flags=re.I)
    for en, pt in (spell_names or {}).items():
        out = re.sub(r"\b%s\b" % re.escape(en), pt, out, flags=re.I)
    for src, dst in POST_REPL:
        out = out.replace(src, dst)
    out = out.replace(" +", " +")
    return out.strip()


def build_description(row, spell_names=None):
    body = translate(row.get("description_en"), spell_names)
    if not body:
        return ""
    return body.strip()


class Command(BaseCommand):
    help = "Aplica descricoes PT em TbItemMagico usando scratch/import_itens/itens_descricoes_en.csv."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(CSV_DEFAULT))
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        from home.models import TbItemMagico

        path = Path(opts["csv"])
        if not path.exists():
            raise CommandError(f"CSV nao encontrado: {path}")

        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        spell_names = load_spell_names()

        updates = []
        missing = []
        for row in rows:
            slug = row.get("db_slug")
            if not slug:
                continue
            obj = TbItemMagico.objects.filter(slug=slug).first()
            if not obj:
                missing.append(slug)
                continue
            desc = build_description(row, spell_names)
            if desc and (obj.descricao_markdown or "").strip() != desc:
                updates.append((obj, desc))

        if opts["apply"]:
            with transaction.atomic():
                for obj, desc in updates:
                    obj.descricao_markdown = desc
                    obj.save(update_fields=["descricao_markdown"])

        self.stdout.write(self.style.SUCCESS(
            "%s updates=%d missing=%d csv_rows=%d"
            % ("APPLY" if opts["apply"] else "PREVIEW", len(updates), len(missing), len(rows))
        ))
        if missing:
            self.stdout.write("Missing sample: " + ", ".join(missing[:20]))
