# -*- coding: utf-8 -*-
"""Importa/atualiza criaturas oficiais a partir dos CSVs em ref/Livros.

O texto completo de cada traco e acao e preservado em ``entries_en`` e em
``entries``. Uma etapa editorial pode traduzir ``entries`` depois sem perder a
fonte mecanica usada para conferencias e futuras reimportacoes.
"""

import csv
import re
import unicodedata
from contextlib import nullcontext
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from home.models import TbBestiario, TbMagia


CSV_PATH = Path("ref/Livros/Bestiary_selecao.csv")
SPELL_ALIGNMENT_PATHS = (
    Path("ref/Livros/magias_alinhado.csv"),
    Path("ref/Livros/magias_en_pt.csv"),
)

MANUAL_SPELL_ALIASES = {
    "alarm": ("Alarme", "alarme"),
    "beast sense": ("Sentido Bestial", "sentido-bestial"),
    "commune with nature": ("Comunhao com a Natureza", "comunhao-com-a-natureza"),
    "comprehend languages": ("Compreender Idiomas", "compreender-idiomas"),
    "locate animals or plants": ("Localizar Animais ou Plantas", "localizar-animais-ou-plantas"),
    "rary's telepathic bond": ("Ligacao Telepatica", "ligacao-telepatica"),
    "silence": ("Silencio", "silencio"),
    "tenser's floating disk": ("Disco Flutuante", "disco-flutuante"),
    "water walk": ("Andar sobre Agua", "andar-sobre-agua"),
}

SECOES = (
    ("Traits", "traits", "Tracos"),
    ("Actions", "actions", "Acoes"),
    ("Bonus Actions", "bonus_actions", "Acoes Bonus"),
    ("Reactions", "reactions", "Reacoes"),
    ("Legendary Actions", "legendary_actions", "Acoes Lendarias"),
    ("Mythic Actions", "mythic_actions", "Acoes Miticas"),
    ("Lair Actions", "lair_actions", "Acoes de Covil"),
    ("Regional Effects", "regional_effects", "Efeitos Regionais"),
)

SIZE_PT = {
    "Tiny": "Minimo",
    "Small": "Pequeno",
    "Medium": "Medio",
    "Large": "Grande",
    "Huge": "Enorme",
    "Gargantuan": "Colossal",
    "Varies": "Variavel",
}

TYPE_PT = {
    "Aberration": "Aberracao",
    "Beast": "Besta",
    "Celestial": "Celestial",
    "Construct": "Construto",
    "Dragon": "Dragao",
    "Elemental": "Elemental",
    "Fey": "Feerico",
    "Fiend": "Corruptor",
    "Giant": "Gigante",
    "Humanoid": "Humanoide",
    "Monstrosity": "Monstruosidade",
    "Ooze": "Limo",
    "Plant": "Planta",
    "Undead": "Morto-vivo",
}

ALIGNMENT_PT = {
    "unaligned": "sem alinhamento",
    "neutral": "neutro",
    "lawful good": "leal e bom",
    "neutral good": "neutro e bom",
    "chaotic good": "caotico e bom",
    "lawful neutral": "leal e neutro",
    "chaotic neutral": "caotico e neutro",
    "lawful evil": "leal e mau",
    "neutral evil": "neutro e mau",
    "chaotic evil": "caotico e mau",
    "any alignment": "qualquer alinhamento",
}

ABILITY_PT = {
    "STR": "FOR",
    "DEX": "DES",
    "CON": "CON",
    "INT": "INT",
    "WIS": "SAB",
    "CHA": "CAR",
}

FEATURE_PT = {
    "Spellcasting": "Conjuracao",
    "Innate Spellcasting": "Conjuracao Inata",
    "Multiattack": "Ataques Multiplos",
    "Legendary Resistance": "Resistencia Lendaria",
    "Magic Resistance": "Resistencia a Magia",
    "Magic Weapons": "Armas Magicas",
    "Pack Tactics": "Taticas de Matilha",
    "Keen Hearing": "Audicao Aguçada",
    "Keen Sight": "Visao Aguçada",
    "Keen Smell": "Faro Aguçado",
    "Spider Climb": "Escalada Aracnidea",
    "Sunlight Sensitivity": "Sensibilidade a Luz Solar",
    "Regeneration": "Regeneração",
    "Whispering Aura": "Aura Sussurrante",
    "Arcane Burst": "Explosão Arcana",
    "Force Blast": "Rajada de Força",
    "Consume Memories": "Consumir Memórias",
    "Dominate Mind": "Dominar Mente",
    "Lash": "Açoite",
    "Psychic Drain": "Dreno Psíquico",
    "Foul Water": "Água Contaminada",
    "Psionic Projection": "Projeção Psiônica",
    "Change Shape": "Alterar Forma",
    "Psychic Step": "Passo Psíquico",
    "Explosive Crystal": "Cristal Explosivo",
    "Beguiling Whisper": "Sussurro Encantador",
    "Rend": "Despedaçar",
    "Acid Breath": "Sopro de Ácido",
    "Lightning Breath": "Sopro de Eletricidade",
    "Fire Breath": "Sopro de Fogo",
    "Sleep Breath": "Sopro de Sono",
    "Repulsion Breath": "Sopro de Repulsão",
    "Slowing Breath": "Sopro de Lentidão",
    "Starlight Strike": "Golpe da Luz Estelar",
    "Emerald Embers": "Brasas de Esmeralda",
    "Weakening Breath": "Sopro de Enfraquecimento",
    "Poison Breath": "Sopro de Veneno",
    "Mind Invasion": "Invasão Mental",
    "Noxious Breath": "Sopro Nocivo",
    "Commanding Presence": "Presença Imponente",
    "Telekinetic Fling": "Arremesso Telecinético",
    "Awesome Thunder": "Trovão Impressionante",
    "Essential Reduction": "Redução Essencial",
    "Paralyzing Breath": "Sopro Paralisante",
    "Freezing Burst": "Explosão Congelante",
    "Frightful Presence": "Presença Aterradora",
    "Pounce": "Bote",
    "Frigid Cold": "Frio Frígido",
    "Bite": "Mordida",
    "Claw": "Garra",
    "Tail": "Cauda",
    "Slam": "Pancada",
    "Strike": "Golpe",
    "Gaze": "Olhar",
    "Aura": "Aura",
    "Constrict": "Constrição",
    "Gore": "Chifrada",
    "Tentacle": "Tentáculo",
    "Fist": "Punho",
    "Hooves": "Cascos",
    "Tusk": "Presa",
    "Talons": "Garras",
    "Stinger": "Ferrão",
    "Club": "Clava",
    "Dagger": "Adaga",
    "Greatsword": "Espada Grande",
    "Longsword": "Espada Longa",
    "Shortsword": "Espada Curta",
    "Scimitar": "Cimitarra",
    "Spear": "Lança",
    "Javelin": "Azagaia",
    "Mace": "Maça",
    "Morningstar": "Estrela da Manhã",
    "Quarterstaff": "Bordão",
    "Light Crossbow": "Bestinha",
    "Shortbow": "Arco Curto",
    "Longbow": "Arco Longo",
    "Telekinesis": "Telecinese",
    "Stomp": "Pisoteada",
    "Web": "Teia",
    "Ram": "Carneiro",
    "Battering Ram": "Aríete",
    "Beak": "Bico",
    "Claws": "Garras",
    "Pincer": "Pinça",
    "Tentacles": "Tentáculos",
    "Longship": "Dracar",
    "Warhammer": "Martelo de Guerra",
    "Cold Breath": "Sopro de Frio",
    "Bash": "Pancada",
    "Drone": "Zumbido",
    "Glaive": "Alabarda",
    "Howdah": "Palanquim",
    "Maul": "Malho",
    "Peck": "Bicada",
    "Fire Aura": "Aura de Fogo",
    "Lightning Strike": "Golpe de Relâmpago",
    "Psychic Beam": "Feixe Psíquico",
    "Fear of Fire": "Medo de Fogo",
    "Ice Throw": "Arremesso de Gelo",
    "Chilling Gaze": "Olhar Gelado",
    "Imprisoning Force": "Força Aprisionadora",
    "Spatial Projection": "Projeção Espacial",
    "Background Check": "Verificação de Histórico",
    "Crystal Profusion": "Profusão de Cristais",
    "Flail": "Mangual",
    "Animal Spirit": "Espírito Animal",
    "Fortify": "Fortificar",
    "Marked as Prey": "Marcado como Presa",
    "Pesky Swarm": "Enxame Incômodo",
    "Tunneler": "Escavador",
    "Acid Spray": "Borrifo de Ácido",
    "Radiant Burst": "Explosão Radiante",
    "Holy Word": "Palavra Sagrada",
    "Serrated Tail": "Cauda Serrilhada",
    "Lightning Lance": "Lança de Relâmpagos",
    "Donjon Visit": "Visita ao Calabouço",
    "Flame Burst": "Explosão de Chamas",
    "Burning Hammer": "Martelo Ardente",
    "Death Throes": "Estertores da Morte",
    "Flame Whip": "Chicote de Fogo",
    "Lightning Blade": "Lâmina de Relâmpagos",
    "Eye Ray": "Raio Ocular",
    "Psychic Slam": "Pancada Psíquica",
    "Fire Ray": "Raio de Fogo",
    "Psychic Projection": "Projeção Psíquica",
    "Unusual Nature": "Natureza Incomum",
    "Piercing Claw": "Garra Perfurante",
    "Shadow Step": "Passo das Sombras",
    "Swallow": "Engolir",
    "Shadow Stealth": "Furtividade das Sombras",
    "Deadly Reach": "Alcance Mortal",
    "Fire Banishment": "Banimento pelo Fogo",
    "Soul Feeding": "Alimentar-se de Almas",
    "Read Thoughts": "Ler Pensamentos",
    "Eat Memories": "Comer Memórias",
    "Amorphous": "Amorfo",
    "Aversion to Fire": "Aversão ao Fogo",
    "Pseudopod": "Pseudópode",
    "Radiant Bow": "Arco Radiante",
    "Radiant Mace": "Maça Radiante",
    "Healing Touch": "Toque Curativo",
    "Acid Absorption": "Absorção de Ácido",
    "Berserk": "Frenesi",
    "Immutable Form": "Forma Imutável",
    "Lightning Flare": "Clarão de Relâmpago",
    "Siege Monster": "Monstro de Cerco",
    "Divine Beam": "Feixe Divino",
    "Smite": "Castigo",
    "Pact Blade": "Lâmina do Pacto",
    "Flash of Light": "Clarão de Luz",
    "Lightning Blood": "Sangue de Relâmpago",
    "Blood Drain": "Dreno de Sangue",
    "Battleaxe": "Machado de Batalha",
    "Psychic Screech": "Grito Psíquico",
    "Undead Restoration": "Restauração de Morto-Vivo",
    "Howl": "Uivo",
    "Energy Drain": "Dreno de Energia",
    "Grave-Dust Flight": "Voo de Poeira de Sepultura",
    "Necrosis": "Necrose",
    "Tongue": "Língua",
    "Radiant Ray": "Raio Radiante",
    "Radiant Bolt": "Dardo Radiante",
    "Radiant Strike": "Golpe Radiante",
    "Necrotic Breath": "Sopro Necrótico",
    "Sickening Breath": "Sopro Enjoativo",
    "Necrotic Ray": "Raio Necrótico",
    "Iron Fist": "Punho de Ferro",
    "Mind-Poison Dagger": "Adaga de Veneno Mental",
    "Invisibility": "Invisibilidade",
    "Mind Mastery": "Maestria Mental",
    "Reduce": "Reduzir",
    "Uncanny Senses": "Sentidos Incomuns",
    "Dimensional Lock": "Tranca Dimensional",
    "Shadow Jump": "Salto das Sombras",
    "Psychic Crush": "Esmagamento Psíquico",
    "Cast a Spell": "Conjurar uma Magia",
    "Commanding Thought": "Pensamento de Comando",
    "Psychic-Attuned Hammer": "Martelo Sintonizado Psiquicamente",
    "Call to Attack": "Chamado ao Ataque",
    "Enlarge": "Ampliar",
    "Scouring Instruction": "Instrução de Purificação",
    "Fire Lance": "Lança de Fogo",
    "Fire Spray": "Borrifo de Fogo",
    "Creature Sense": "Sentir Criatura",
    "Telepathic Hub": "Central Telepática",
    "Thunderous Slam": "Pancada Trovejante",
    "Lightning Storm": "Tempestade de Relâmpagos",
    "Move": "Mover",
    "Screaming Gale": "Ventania Gritante",
    "Spit Fire": "Cuspir Fogo",
    "Lightning Absorption": "Absorção de Eletricidade",
    "Advanced Telepathy": "Telepatia Avançada",
    "Prone Deficiency": "Deficiência Caída",
    "Telepathic Shroud": "Manto Telepático",
    "Stench Spray": "Borrifo de Fedor",
    "Wind Javelin": "Azagaia de Vento",
    "Tentacle Lash": "Acoite de Tentaculo",
    "Mind Rot": "Podridao Mental",
    "Counterspell": "Contramagica",
    "Amphibious": "Anfibio",
    "Eldritch Restoration": "Restauracao Eldritch",
    "Mucus Cloud": "Nuvem de Muco",
    "Probing Telepathy": "Telepatia Investigativa",
    "Singularity Breath": "Sopro de Singularidade",
    "Cloaked Flight": "Voo Encoberto",
    "Sonic Boom": "Estrondo Sonico",
    "Tail Swipe": "Golpe de Cauda",
    "Sinkholes": "Sumidouros",
    "Spiteful Storms": "Tempestades Rancorosas",
    "Disorienting Breath": "Sopro Desorientador",
    "Debilitating Breath": "Sopro Debilitante",
    "Desiccating Breath": "Sopro Dessecante",
    "Breath Weapon": "Arma de Sopro",
    "Dream Breath": "Sopro Onirico",
    "Moonlight Breath": "Sopro de Luar",
    "Banish into Dream": "Banir para o Sonho",
    "Rime Breath": "Sopro de Geada",
    "Air Form": "Forma de Ar",
    "Whirlwind": "Redemoinho",
    "Turn Resistance": "Resistencia a Expulsao",
    "Frioing Grasp": "Agarrar Gelido",
    "Arcane Bolt": "Dardo Arcano",
    "Mind Blast": "Explosao Mental",
    "False Appearance": "Aparencia Falsa",
    "Foment Confusion": "Fomentar Confusao",
    "Incorporeal Movement": "Movimento Incorporeo",
    "Maddening Touch": "Toque Enlouquecedor",
    "Howling Babble": "Balbucio Uivante",
    "Whispers of Compulsion": "Sussurros de Compulsao",
    "Gem Awakening": "Despertar Gemico",
    "Breath Weapon": "Arma de Sopro",
    "Mass Telekinesis": "Telecinese em Massa",
    "Fabricate": "Fabricar",
    "Positive Energy": "Energia Positiva",
    "Banish": "Banir",
    "Stab": "Estocada",
    "Protective Magic": "Magia Protetora",
    "Infernal Command": "Comando Infernal",
    "Corrupting Touch": "Toque Corruptor",
    "Horrify": "Horrorizar",
    "Deathly Wail": "Lamento Mortal",
    "Dread": "Pavor",
    "Hellish Morningstar": "Estrela da Manha Infernal",
    "Warp Terrain": "Distorcer Terreno",
    "Sense Desires": "Sentir Desejos",
    "Supernatural Lure": "Isca Sobrenatural",
    "Barbed Hide": "Couro Farpado",
    "Diabolical Restoration": "Restauracao Diabolica",
    "Devilish Claw": "Garra Diabolica",
    "Fiery Mace": "Maca Flamejante",
    "Hellfire Spellcasting": "Conjuracao de Fogo Infernal",
    "Detect Life": "Detectar Vida",
    "Cloud of Insects": "Nuvem de Insetos",
    "Acrid Haze": "Neblina Acrida",
    "Poisonous Skin": "Pele Venenosa",
    "Water Dependency": "Dependencia de Agua",
    "Shapechanger": "Metamorfo",
    "Thunderbolt": "Raio Trovejante",
    "Uncanny Dodge": "Esquiva Sobrenatural",
    "Poison Ray": "Raio Venenoso",
    "Sun Sickness": "Enjoo Solar",
    "Rapport Spores": "Esporos de Comunicacao",
    "Paralysis": "Paralisia",
    "Mental Fortitude": "Fortitude Mental",
    "Blood Frenzy": "Frenesi de Sangue",
    "Shark Telepathy": "Telepatia de Tubarao",
    "Sunlight Weakness": "Fraqueza a Luz Solar",
    "Inscrutable": "Inescrutavel",
    "Vampire Weakness": "Fraqueza Vampirica",
    "Running Water": "Agua Corrente",
    "Stake to the Heart": "Estaca no Coracao",
    "Sunlight": "Luz Solar",
    "Low Cunning": "Astucia Baixa",
    "Spectral Fangs": "Presas Espectrais",
    "The Heart": "O Coracao",
    "The Dead": "Os Mortos",
    "The Night": "A Noite",
    "The Sea": "O Mar",
    "The Way": "O Caminho",
    "The Land": "A Terra",
    "The Sky": "O Ceu",
    "The Spider Queen": "A Rainha Aranha",
    "The Troops": "As Tropas",
    "The Draconic Origin trait below": "o traco Origem Draconica abaixo",
    "The region around its lair": "a regiao ao redor de seu covil",
    "The Dragon": "O Dragao",
    "The Kraken": "O Kraken",
    "The poisoned creature can't regain hit points": "A criatura envenenada nao pode recuperar pontos de vida",
    "The White Hand": "A Mao Branca",
    "The Grave": "A Sepultura",
    "The Riddle": "O Enigma",
    "The Storm": "A Tempestade",
    "The Pack": "A Matilha",
    "Antimagic Cone": "Cone Antimagia",
    "Astral Entity": "Entidade Astral",
    "Demiplanar Donjon": "Calabouco Demiplanar",
    "Sever Silver Cord": "Cortar Cordao de Prata",
    "Enchanting Presence": "Presenca Encantadora",
    "Fiendish Restoration": "Restauracao Corruptora",
    "Soul Tome": "Tomo de Almas",
    "Fiendish Burst": "Explosao Corruptora",
    "Banishing Claw": "Garra Banidora",
    "Coven Magic": "Magia de Coven",
    "Coven": "Coven",
    "Weakening Gaze": "Olhar Enfraquecedor",
    "Chromatic Flames": "Chamas Cromaticas",
    "Furious Bite": "Mordida Furiosa",
    "Hurl Through Avernus": "Arremessar por Avernus",
    "Chromatic Flare": "Clarão Cromatico",
    "Flyby": "Sobrevoo",
    "Illumination": "Iluminacao",
    "Demonic Restoration": "Restauracao Demoniaca",
    "Leap": "Salto",
    "Charge": "Investida",
    "Bites": "Mordidas",
    "Rock": "Rocha",
    "Divine Aid": "Auxilio Divino",
    "Eye Rays": "Raios Oculares",
    "Standing Leap": "Salto Parado",
    "Stench": "Fedor",
    "Aggressive": "Agressivo",
    "Sting": "Ferrao",
    "Misty Step": "Passo Nebuloso",
    "Fey Step": "Passo Feerico",
    "Duergar Resilience": "Resiliencia Duergar",
    "Ice Walk": "Caminhada no Gelo",
    "Watery Sight": "Visao Aquatica",
    "Scintillating Breath": "Sopro Cintilante",
    "Guiding Light": "Luz Guia",
    "Beguiling Realm": "Reino Sedutor",
    "Hurl Flame": "Arremessar Chama",
    "Greataxe": "Machado Grande",
    "Bloodied Fury": "Furia Ensanguentada",
    "Misty Escape": "Fuga Nebulosa",
    "Scratch": "Arranhao",
    "Light Sensitivity": "Sensibilidade a Luz",
    "Earth Glide": "Deslizar pela Terra",
    "Elemental Restoration": "Restauracao Elemental",
    "Wishes": "Desejos",
    "Grave Bolt": "Dardo Sepulcral",
    "Limited Amphibiousness": "Anfibiedade Limitada",
    "Plant Camouflage": "Camuflagem Vegetal",
    "Forbiddance": "Interdicao",
    "Paralyzing Tentacles": "Tentaculos Paralisantes",
    "Stone Club": "Clava de Pedra",
    "Deathly Ray": "Raio Mortal",
    "Beast of Burden": "Animal de Carga",
    "Exalted Restoration": "Restauracao Exaltada",
    "Fear Aura": "Aura de Medo",
    "Trample": "Atropelar",
    "Shell Defense": "Defesa da Concha",
    "Ink Cloud": "Nuvem de Tinta",
    "Astral Step": "Passo Astral",
    "Raxivort's Tongue": "Lingua de Raxivort",
}

CREATURE_NAME_TRANSLATIONS = {
    "Air Elemental": "Elemental do Ar",
    "Air Elemental Myrmidon": "Mirmidão Elemental do Ar",
    "Animal Lord": "Senhor dos Animais",
    "Animated Breath": "Sopro Animado",
    "Ape": "Gorila",
    "Archer": "Arqueiro",
    "Badger": "Teixugo",
    "Fire Giant": "Gigante do Fogo",
    "Fire Giant Dreadnought": "Gigante do Fogo Dreadnought",
    "Invisible Stalker": "Espreitador Invisível",
    "Drake Companion": "Companheiro Dracônico",
    "Beast Companion": "Companheiro Besta",
    "Construct Companion": "Companheiro Construto",
    "Elemental Companion": "Companheiro Elemental",
    "Undead Companion": "Companheiro Morto-Vivo",
    "Bandido Crime Lord": "Chefe do Crime Bandido",
    "Barbed Devil": "Diabo Farpado",
    "Bearded Devil": "Diabo Barbado",
    "Beast of the Land": "Besta da Terra",
    "Beast of the Sea": "Besta do Mar",
    "Beast of the Sky": "Besta do Céu",
    "Boar": "Javali",
    "Bone Devil": "Diabo de Ossos",
    "Cat": "Gato",
    "Chain Devil": "Diabo de Correntes",
    "Construct Espirito": "Espírito de Construto",
    "Crab": "Caranguejo",
    "Crawling Claw": "Garra Rastejante",
    "Crocodile": "Crocodilo",
    "Death Knight": "Cavaleiro da Morte",
    "Deep Rothe": "Rothé das Profundezas",
    "Deer": "Cervo",
    "Demonic Spirit": "Espírito Demônio",
    "Dinosaur": "Dinossauro",
    "Draft Horse": "Cavalo de Carga",
    "Dragon Spirit": "Espírito Dragão",
    "Dread Warrior": "Guerreiro do Pavor",
    "Drow Shadowblade": "Lâmina Sombria Drow",
    "Dust Mephit": "Mefite de Poeira",
    "Eagle": "Águia",
    "Earth Elemental": "Elemental da Terra",
    "Earth Elemental Myrmidon": "Mirmidão Elemental da Terra",
    "Elk": "Alce",
    "Espirito Beast": "Espírito Besta",
    "Espirito Dragon": "Espírito Dragão",
    "Espirito Elemental": "Espírito Elemental",
    "Espirito Fey": "Espírito Feérico",
    "Espirito Fiend": "Espírito Corruptor",
    "Espirito Undead": "Espírito Morto-Vivo",
    "Fey Spirit": "Espírito Feérico",
    "Fiendish Spirit": "Espírito Corruptor",
    "Fire Elemental": "Elemental do Fogo",
    "Fire Elemental Myrmidon": "Mirmidão Elemental do Fogo",
    "Frog": "Rã",
    "Gargoyle": "Gárgula",
    "Ghost": "Fantasma",
    "Ghoul": "Carniçal",
    "Giant Ape": "Gorila Gigante",
    "Giant Badger": "Teixugo Gigante",
    "Giant Bat": "Morcego Gigante",
    "Giant Boar": "Javali Gigante",
    "Giant Centipede": "Centopéia Gigante",
    "Giant Crab": "Caranguejo Gigante",
    "Giant Crocodile": "Crocodilo Gigante",
    "Giant Eagle": "Águia Gigante",
    "Giant Elk": "Alce Gigante",
    "Giant Fire Beetle": "Besouro de Fogo Gigante",
    "Giant Frog": "Rã Gigante",
    "Giant Goat": "Bode Gigante",
    "Giant Hyena": "Hiena Gigante",
    "Giant Lizard": "Lagarto Gigante",
    "Giant Octopus": "Polvo Gigante",
    "Giant Owl": "Coruja Gigante",
    "Giant Poisonous Snake": "Serpente Venenosa Gigante",
    "Giant Rat": "Rato Gigante",
    "Giant Scorpion": "Escorpião Gigante",
    "Giant Sea Seahorse": "Cavalo-marinho Gigante",
    "Giant Shark": "Tubarão Gigante",
    "Giant Snake": "Serpente Gigante",
    "Giant Spider": "Aranha Gigante",
    "Giant Toad": "Sapo Gigante",
    "Giant Vulture": "Abutre Gigante",
    "Giant Wasp": "Vespa Gigante",
    "Giant Weasel": "Doninha Gigante",
    "Giant Wolf": "Lobo Gigante",
    "Gnoll Fang of Yeenoghu": "Gnoll Presa de Yeenoghu",
    "Goat": "Bode",
    "Goblin Boss": "Chefe Goblin",
    "Grimlock": "Grimlock",
    "Hawk": "Falcão",
    "Horned Devil": "Diabo Chifrudo",
    "Hunter Shark": "Tubarão Caçador",
    "Hyena": "Hiena",
    "Ice Devil": "Diabo do Gelo",
    "Ice Mephit": "Mefite do Gelo",
    "Imp": "Diabrete",
    "Jackal": "Chacal",
    "Kobold Scale Sorcerer": "Feiticeiro de Escamas Kobold",
    "Lizard": "Lagarto",
    "Lizardfolk Render": "Metamorfo Povo-lagarto",
    "Lizardfolk Scalesinger": "Cantor de Escamas Povo-lagarto",
    "Magma Mephit": "Mefite de Magma",
    "Mammoth": "Mamute",
    "Mastiff": "Mastim",
    "Minstrel": "Menestrel",
    "Mud Mephit": "Mefite de Lama",
    "Mummy Lord": "Senhor Múmia",
    "Nightmare": "Pesadelo",
    "Noble": "Nobre",
    "Octopus": "Polvo",
    "Orc Claw of Luthic": "Garra de Luthic Orc",
    "Orc Eye of Gruumsh": "Olho de Gruumsh Orc",
    "Orc Hand of Yurtrus": "Mão de Yurtrus Orc",
    "Orc Nurtured One of Yurtrus": "Nutrido de Yurtrus Orc",
    "Orc Red Fang of Shargaas": "Presa Vermelha de Shargaas Orc",
    "Owl": "Coruja",
    "Panther": "Pantera",
    "Pony": "Pônei",
    "Priest of Osybus": "Sacerdote de Osybus",
    "Pteranodon": "Pteranodonte",
    "Rat": "Rato",
    "Raven": "Corvo",
    "Reef Shark": "Tubarão de Recife",
    "Rhinoceros": "Rinoceronte",
    "Riding Horse": "Cavalo de Montaria",
    "Sahuagin Baron": "Barão Sahuagin",
    "Sahuagin Blademaster": "Mestre das Lâminas Sahuagin",
    "Sahuagin Priestess": "Sacerdotisa Sahuagin",
    "Sea Pony": "Pônei do Mar",
    "Shadow Spirit": "Espírito das Sombras",
    "Shadowblade": "Lâmina Sombria",
    "Skeleton": "Esqueleto",
    "Smoke Mephit": "Mefite de Fumaça",
    "Snake": "Serpente",
    "Spawn of Kyuss": "Cria de Kyuss",
    "Spider": "Aranha",
    "Steam Mephit": "Mefite de Vapor",
    "Swarm of Bats": "Enxame de Morcegos",
    "Swarm of Beetles": "Enxame de Besouros",
    "Swarm of Centipedes": "Enxame de Centopéias",
    "Swarm of Insects": "Enxame de Insetos",
    "Swarm of Poisonous Snakes": "Enxame de Serpentes Venenosas",
    "Swarm of Rats": "Enxame de Ratos",
    "Swarm of Ravens": "Enxame de Corvos",
    "Swarm of Spiders": "Enxame de Aranhas",
    "Swarm of Wasp": "Enxame de Vespas",
    "Tiger": "Tigre",
    "Undead Spirit": "Espírito Morto-Vivo",
    "Unicorn": "Unicórnio",
    "Vulture": "Abutre",
    "Warhorse": "Cavalo de Guerra",
    "Warhorse Skeleton": "Esqueleto de Cavalo de Guerra",
    "Water Elemental": "Elemental da Água",
    "Water Elemental Myrmidon": "Mirmidão Elemental da Água",
    "Weasel": "Doninha",
    "Wolf": "Lobo",
    "Zombie": "Zumbi",
    "Displacer Beast": "Besta Deslocadora",
    "Dragonblood Ooze": "Limo de Sangue de Dragão",
    "Egg Hunter Adult": "Caçador de Ovos Adulto",
    "Egg Hunter Hatchling": "Caçador de Ovos Recém-Nascido",
    "Elemental Cataclysm": "Cataclismo Elemental",
    "Elephant": "Elefante",
    "Gnoll Hunter": "Gnoll Caçador",
    "Gnoll Pack Lord": "Gnoll Senhor da Matilha",
    "Goblin Hexer": "Goblin Praga",
    "Goblin Minion": "Goblin Lacaio",
    "Gray Ooze": "Limo Cinzento",
    "Half-Dragon": "Meio-Dragão",
    "Kobold Dragonshield": "Kobold Escudo-do-Dragão",
    "Kobold Inventor": "Kobold Inventor",
    "Kruthik Hive Lord": "Senhor da Colmeia Kruthik",
    "Maw Demon": "Demônio da Boca",
    "Merfolk Wavebender": "Dormador de Ondas do Povo do Mar",
    "Orc Blade of Ilneval": "Lâmina de Ilneval Orc",
    "Psychic Gray Ooze": "Limo Cinzento Psíquico",
    "Sahuagin Priest": "Sacerdote Sahuagin",
    "Sahuagin Warrior": "Guerreiro Sahuagin",
    "Scorpion": "Escorpião",
    "Shadow Demon": "Demônio das Sombras",
    "Shadow Mastiff": "Mastim das Sombras",
    "Shadow Mastiff Alpha": "Mastim das Sombras Alfa",
    "Skull Lord": "Senhor das Caveiras",
    "Spined Devil": "Diabo Espinhoso",
    "Sword Wraith Commander": "Comandante Aparição da Espada",
    "Sword Wraith Warrior": "Aparição da Espada Guerreira",
    "Tough Boss": "Chefe Durão",
    "Tyrannosaurus Rex": "Tiranossauro Rex",
    "Vampire Umbral Lord": "Senhor Umbral Vampiro",
    "Winged Kobold": "Kobold Alado",
    "Wraith": "Aparição",
    "Labyrinth Totem of the Minotaur King": "Totem do Labirinto do Rei Minotauro",
    "Construct Spirit": "Espírito de Construto",
    "Elemental Spirit": "Espírito Elemental",
    "Bandit Crime Lord": "Senhor do Crime Bandido",
    "Azer Pyromancer": "Azer Piromante",
    "Azer Sentinel": "Azer Sentinela",
    "Drow Favored Consort": "Consorte Favorito Drow",
    "Drow Inquisitor": "Inquisidor Drow",
    "Drow Matron Mother": "Madre Matrona Drow",
    "Elder Tempest": "Tempestade Anciã",
    "Angry Sorrowsworn": "Juramentado da Tristeza Irado",
    "Archpriest": "Arquisacerdote",
    "Astral Dreadnought": "Dreadnought Astral",
    "Bugbear Stalker": "Bugbear Espreitador",
    "Dragonborn of Bahamut": "Draconato de Bahamut",
    "Dragonborn of Sardior": "Draconato de Sardior",
    "Dragonborn of Tiamat": "Draconato de Tiamat",
    "Duergar Despot": "Déspota Duergar",
    "Duergar Hammerer": "Martelador Duergar",
    "Duergar Kavalrachni": "Kavalrachni Duergar",
    "Duergar Mind Master": "Mestre Mental Duergar",
    "Duergar Screamer": "Gritador Duergar",
    "Duergar Soulblade": "Lâmina Anímica Duergar",
    "Duergar Stone Guard": "Guarda de Pedra Duergar",
    "Empyrean": "Empíreo",
    "Empyrean Iota": "Iota Empírea",
    "Firenewt Warlock of Imix": "Tritão de Fogo Bruxo de Imix",
    "Firenewt Warrior": "Tritão de Fogo Guerreiro",
    "Flail Snail": "Caracol Mangual",
    "Frost Giant": "Gigante do Gelo",
    "Frost Giant Everlasting One": "Gigante do Gelo Eterno",
    "Frost Salamander": "Salamandra do Gelo",
    "Gem Stalker": "Espreitador de Gema",
    "Githzerai Anarch": "Anarca Githzerai",
    "Githzerai Enlightened": "Iluminado Githzerai",
    "Githzerai Monk": "Monge Githzerai",
    "Githzerai Psion": "Psion Githzerai",
    "Githzerai Zerth": "Zerth Githzerai",
    "Guard Drake": "Draco de Guarda",
    "Guardian Naga": "Naga Guardiã",
    "Hungry Sorrowsworn": "Juramentado da Tristeza Faminto",
    "Lonely Sorrowsworn": "Juramentado da Tristeza Solitário",
    "Lost Sorrowsworn": "Juramentado da Tristeza Perdido",
    "Wretched Sorrowsworn": "Juramentado da Tristeza Miserável",
    "Labyrinth Totem - Lesser Baphomet": "Totem do Labirinto - Baphomet Menor",
    "Labyrinth Totem - Greater Baphomet": "Totem do Labirinto - Baphomet Maior",
    "Labyrinth Totem - Molten Baphomet": "Totem do Labirinto - Baphomet Derretido",
    "Labyrinth Totem - Bronze Baphomet": "Totem do Labirinto - Baphomet de Bronze",
    "Labyrinth Totem - Crystal Baphomet": "Totem do Labirinto - Baphomet de Cristal",
    "Leviathan": "Leviatã",
    "Lizardfolk Geomancer": "Povo-Lagarto Geomante",
    "Lizardfolk Sovereign": "Povo-Lagarto Soberano",
    "Merfolk Skirmisher": "Tritão Escaramuçador",
    "Salamander Fire Serpent": "Salamandra Serpente de Fogo",
    "Shield Guardian": "Guardião de Escudo",
    "Clockwork Bronze Scout": "Batedor Mecânico de Bronze",
    "Clockwork Iron Cobra": "Cobra Mecânica de Ferro",
    "Clockwork Oaken Bolter": "Atirador Mecânico de Carvalho",
    "Clockwork Stone Defender": "Defensor Mecânico de Pedra",
}

DAMAGE_CONDITION_PT = {
    "acid": "ácido",
    "cold": "frio",
    "fire": "fogo",
    "force": "força",
    "lightning": "elétrico",
    "necrotic": "necrótico",
    "poison": "veneno",
    "psychic": "psíquico",
    "radiant": "radiante",
    "thunder": "trovejante",
    "exhaustion": "exaustão",
    "bludgeoning": "concussão",
    "piercing": "perfurante",
    "slashing": "cortante",
    "bludgeoning, piercing, and slashing from nonmagical attacks": "concussão, perfuração e corte de ataques não mágicos",
    "bludgeoning, piercing, and slashing from nonmagical weapons": "concussão, perfuração e corte de armas não mágicas",
    "bludgeoning, piercing, and slashing from nonmagical attacks that aren't silvered": "concussão, perfuração e corte de ataques não mágicos que não sejam de prata",
    "blinded": "cego",
    "charmed": "enfeitiçado",
    "deafened": "surdo",
    "frightened": "amedrontado",
    "grappled": "agarrado",
    "incapacitated": "incapacitado",
    "invisible": "invisível",
    "paralyzed": "paralisado",
    "petrified": "petrificado",
    "poisoned": "envenenado",
    "prone": "caído",
    "restrained": "contido",
    "stunned": "atordoado",
    "unconscious": "inconsciente",
    "and": "e",
    "while in dim light or darkness": "enquanto em luz difusa ou escuridão",
    "from nonmagical attacks": "de ataques não mágicos",
    "from nonmagical weapons": "de armas não mágicas",
    "that aren't silvered": "que não sejam de prata",
    "that aren't adamantine": "que não sejam de adamantina",
    "damage of the type matching the animated form": "dano do tipo correspondente à forma animada",
}

SKILLS_PT = {
    "Acrobatics": "Acrobacia",
    "Animal Handling": "Adestrar Animais",
    "Arcana": "Arcanismo",
    "Athletics": "Atletismo",
    "Deception": "Enganação",
    "History": "História",
    "Insight": "Intuição",
    "Intimidation": "Intimidação",
    "Investigation": "Investigação",
    "Medicine": "Medicina",
    "Nature": "Natureza",
    "Perception": "Percepção",
    "Performance": "Atuação",
    "Persuasion": "Persuasão",
    "Religion": "Religião",
    "Sleight of Hand": "Prestidigitação",
    "Stealth": "Furtividade",
    "Survival": "Sobrevivência",
}

LANGUAGES_PT = {
    "common": "Comum",
    "draconic": "Dracônico",
    "elvish": "Élfico",
    "dwarvish": "Anão",
    "giant": "Gigante",
    "gnomish": "Gnômico",
    "goblin": "Goblin",
    "halfling": "Halfling",
    "orc": "Orc",
    "abyssal": "Abissal",
    "celestial": "Celestial",
    "infernal": "Infernal",
    "sylvan": "Silvestre",
    "undercommon": "Dialeto Subterrâneo",
    "deep speech": "Dialeto Subterrâneo",
    "aquan": "Aquan",
    "auran": "Auran",
    "ignan": "Ignan",
    "terran": "Terran",
    "telepathy": "telepatia",
    "any one language": "qualquer um idioma",
    "any two languages": "quaisquer dois idiomas",
    "any three languages": "quaisquer três idiomas",
    "any four languages": "quaisquer quatro idiomas",
    "all": "todos",
    "all languages": "todos os idiomas",
    "and the languages of its creator": "e os idiomas de seu criador",
    "understands the languages you know": "compreende os idiomas que você conhece",
    "understands": "compreende",
    "the languages it knew in life": "os idiomas que conhecia em vida",
    "plus one more language": "mais um outro idioma",
    "plus one other language": "mais um outro idioma",
    "plus two more languages": "mais dois outros idiomas",
    "plus two other languages": "mais dois outros idiomas",
    "plus three more languages": "mais três outros idiomas",
    "plus three other languages": "mais três outros idiomas",
    "plus four more languages": "mais quatro outros idiomas",
    "plus four other languages": "mais quatro outros idiomas",
    "plus five other languages": "mais cinco outros idiomas",
    "plus any two languages": "mais quaisquer dois idiomas",
    "plus any three languages": "mais quaisquer três idiomas",
    "plus any four languages": "mais quaisquer quatro idiomas",
    "plus any one language": "mais qualquer um idioma",
    "but can't speak": "mas não pode falar",
    "can't speak": "não pode falar",
    "can speak with spiders": "pode falar com aranhas",
    "plus six more languages": "mais seis outros idiomas",
    "plus six other languages": "mais seis outros idiomas",
}

def _traduz_tipo(tipo_en):
    tipo_en = (tipo_en or "").strip()
    if not tipo_en:
        return ""
        
    PHRASE_TYPE_PT = {
        "swarm of tiny undead": "enxame de mortos-vivos miúdos",
        "celestial, fey, or fiend": "celestial, feérico ou corruptor",
        "celestial or fiend": "celestial ou corruptor",
        "otherworldly steed": "celestial, feérico ou corruptor",
    }
    
    tipo_lower = tipo_en.lower().replace(",", "")
    if tipo_lower in PHRASE_TYPE_PT:
        return PHRASE_TYPE_PT[tipo_lower]
        
    match = re.match(r"^([^(]+)\s*\(([^)]+)\)$", tipo_en)
    if match:
        base = match.group(1).strip()
        sub = match.group(2).strip()
        base_pt = _traduz_tipo(base)
        sub_pt_map = {
            "Gem": "Gema",
            "Chromatic": "Cromático",
            "Metallic": "Metálico",
            "Demon": "Demônio",
            "Devil": "Diabo",
            "Yugoloth": "Yugoloth",
            "Dinosaur": "Dinossauro",
            "Wizard": "Mago",
            "Cleric": "Clérigo",
            "Druid": "Druida",
            "Paladin": "Paladino",
            "Sorcerer": "Feiticeiro",
            "Bard": "Bardo",
            "Monk": "Monge",
            "Ranger": "Patrulheiro",
            "Fighter": "Guerreiro",
            "Rogue": "Ladino",
            "Barbarian": "Bárbaro",
            "Warlock": "Bruxo",
            "Shapechanger": "Metamorfo",
            "Titan": "Titã",
            "Kobold": "Kobold",
            "Goblinoid": "Goblinoide",
            "Orc": "Orc",
            "Gnoll": "Gnoll",
            "Grimlock": "Grimlock",
            "Mind Flayer": "Devorador de Mentes",
            "Elf": "Elfo",
            "Human": "Humano",
            "Dwarf": "Anão",
            "Gnomish": "Gnomo",
            "Angel": "Anjo",
            "Genie": "Gênio",
            "Hill Giant": "Gigante das Colinas",
            "Frost Giant": "Gigante do Gelo",
        }
        sub_parts = [part.strip() for part in sub.split(",")]
        sub_pt_parts = [sub_pt_map.get(part, part) for part in sub_parts]
        sub_pt = ", ".join(sub_pt_parts)
        return f"{base_pt} ({sub_pt})"
        
    # Check TYPE_PT case-insensitively
    for en, pt in TYPE_PT.items():
        if en.lower() == tipo_en.lower():
            return pt
            
    return tipo_en

def _traduz_alinhamento(aln_en):
    aln_en = (aln_en or "").strip().lower()
    if not aln_en:
        return ""
    if aln_en in ALIGNMENT_PT:
        return ALIGNMENT_PT[aln_en]
    texto = aln_en
    replaces = [
        ("any alignment", "qualquer alinhamento"),
        ("any non-good alignment", "qualquer alinhamento não bom"),
        ("any non-lawful alignment", "qualquer alinhamento não leal"),
        ("any non-chaotic alignment", "qualquer alinhamento não caótico"),
        ("any evil alignment", "qualquer alinhamento mau"),
        ("any good alignment", "qualquer alinhamento bom"),
        ("any chaotic alignment", "qualquer alinhamento caótico"),
        ("any lawful alignment", "qualquer alinhamento leal"),
        ("any neutral alignment", "qualquer alinhamento neutro"),
        ("lawful good", "leal e bom"),
        ("neutral good", "neutro e bom"),
        ("chaotic good", "caótico e bom"),
        ("lawful neutral", "leal e neutro"),
        ("chaotic neutral", "caótico e neutro"),
        ("lawful evil", "leal e mau"),
        ("neutral evil", "neutro e mau"),
        ("chaotic evil", "caótico e mau"),
        ("unaligned", "sem alinhamento"),
        ("neutral", "neutro"),
    ]
    for en, pt in replaces:
        texto = texto.replace(en, pt)
    return texto

def _traduz_pericia(s):
    match = re.match(r"^([A-Za-z\s]+)([\+-]\d+)?$", s.strip())
    if match:
        name = match.group(1).strip()
        mod = match.group(2) or ""
        return f"{SKILLS_PT.get(name, name)}{mod}"
    return s

def _traduz_dano_condicao(d):
    d = d.strip()
    if d.lower() in DAMAGE_CONDITION_PT:
        return DAMAGE_CONDITION_PT[d.lower()]
    texto = d
    for en, pt in DAMAGE_CONDITION_PT.items():
        texto = re.sub(rf"\b{en}\b", pt, texto, flags=re.I)
    return texto

def _traduz_sentidos(senses_en):
    senses_en = (senses_en or "").strip().lower()
    if not senses_en:
        return ""
    
    def repl_dist(match):
        dist_ft = int(match.group(1))
        dist_m = int(round(dist_ft * 0.3))
        if dist_ft == 5:
            dist_m = 1.5
        elif dist_ft == 15:
            dist_m = 4.5
        return f"{str(dist_m).replace('.', ',')} m ({dist_ft} ft.)"
        
    texto = re.sub(r"(\d+)\s*ft\.?", repl_dist, senses_en, flags=re.I)
    
    replaces_mapped = [
        ("passive perception", "Percepção passiva"),
        ("blindsight", "percepção às cegas"),
        ("darkvision", "visão no escuro"),
        ("truesight", "visão verdadeira"),
    ]
    for en, pt in replaces_mapped:
        texto = re.sub(rf"\b{en}\b", pt, texto, flags=re.I)
    return texto

def _traduz_idiomas(lang_en):
    lang_en = (lang_en or "").strip().lower()
    if not lang_en:
        return ""
    
    def repl_dist(match):
        dist_ft = int(match.group(1))
        dist_m = int(round(dist_ft * 0.3))
        if dist_ft == 5:
            dist_m = 1.5
        elif dist_ft == 15:
            dist_m = 4.5
        return f"{str(dist_m).replace('.', ',')} m ({dist_ft} ft.)"
    texto = re.sub(r"(\d+)\s*ft\.?", repl_dist, lang_en, flags=re.I)
    
    for en, pt in sorted(LANGUAGES_PT.items(), key=lambda x: len(x[0]), reverse=True):
        texto = re.sub(rf"\b{en}\b", pt, texto, flags=re.I)
    return texto

def _traduz_deslocamento(speed_en):
    speed_en = (speed_en or "").strip().lower()
    if not speed_en:
        return ""
    
    def repl_dist(match):
        dist_ft = int(match.group(1))
        dist_m = int(round(dist_ft * 0.3))
        if dist_ft == 5:
            dist_m = 1.5
        elif dist_ft == 15:
            dist_m = 4.5
        return f"{str(dist_m).replace('.', ',')} m ({dist_ft} ft.)"
    texto = re.sub(r"(\d+)\s*ft\.?", repl_dist, speed_en, flags=re.I)
    
    replaces = [
        ("fly", "voo"),
        ("swim", "nado"),
        ("climb", "escalada"),
        ("burrow", "escavação"),
        ("hover", "pairar"),
    ]
    for en, pt in replaces:
        texto = re.sub(rf"\b{en}\b", pt, texto, flags=re.I)
    return texto


CREATURE_ALIASES = {
    "Animated Object": ("objeto-animado", "Objeto Animado"),
    "Giant Insect": ("inseto-gigante", "Inseto Gigante"),
    "Riding Horse": ("cavalo-de-montaria", "Cavalo de Montaria"),
    "Skeleton": ("esqueleto", "Esqueleto"),
    "Unicorn": ("unicornio", "Unicornio"),
    "Warhorse": ("cavalo-de-guerra", "Cavalo de Guerra"),
    "Zombie": ("zumbi", "Zumbi"),
}

TAG_CREATURE_ALIASES = {
    slugify(en): pt_slug for en, (pt_slug, _nome) in CREATURE_ALIASES.items()
}

NAME_REPLACEMENTS = (
    ("Ancient", "Anciao"),
    ("Adult", "Adulto"),
    ("Young", "Jovem"),
    ("Wyrmling", "Filhote"),
    ("Black", "Negro"),
    ("Blue", "Azul"),
    ("Brass", "Latao"),
    ("Bronze", "Bronze"),
    ("Copper", "Cobre"),
    ("Gold", "Dourado"),
    ("Green", "Verde"),
    ("Red", "Vermelho"),
    ("Silver", "Prateado"),
    ("White", "Branco"),
    ("Amethyst", "Ametista"),
    ("Crystal", "Cristal"),
    ("Emerald", "Esmeralda"),
    ("Sapphire", "Safira"),
    ("Topaz", "Topazio"),
    ("Dragon", "Dragao"),
    ("Aarakocra", "Aarakocra"),
    ("Aeromancer", "Aeromante"),
    ("Skirmisher", "Escaramucador"),
    ("Aberrant", "Aberrante"),
    ("Cultist", "Cultista"),
    ("Spirit", "Espirito"),
    ("Abjurer", "Abjurador"),
    ("Conjurer", "Conjurador"),
    ("Diviner", "Adivinho"),
    ("Enchanter", "Encantador"),
    ("Evoker", "Evocador"),
    ("Illusionist", "Ilusionista"),
    ("Necromancer", "Necromante"),
    ("Transmuter", "Transmutador"),
    ("Wizard", "Mago"),
    ("Abominable", "Abominavel"),
    ("Assassin", "Assassino"),
    ("Archmage", "Arquimago"),
    ("Berserker", "Furioso"),
    ("Veteran", "Veterano"),
    ("Noble", "Nobre"),
    ("Acolyte", "Acolito"),
    ("Apprentice", "Aprendiz"),
    ("Warlock", "Bruxo"),
    ("Druid", "Druida"),
    ("Bard", "Bardo"),
    ("Monk", "Monge"),
    ("Paladin", "Paladino"),
    ("Ranger", "Guardiao"),
    ("Rogue", "Ladino"),
    ("Pirate", "Pirata"),
    ("Thug", "Capanga"),
    ("Cult", "Culto"),
    ("Skeleton", "Esqueleto"),
    ("Zombie", "Zumbi"),
    ("Ghost", "Fantasma"),
    ("Ghoul", "Carniçal"),
    ("Giant", "Gigante"),
    ("Dire", "Atroz"),
    ("Swarm", "Enxame"),
    ("Commoner", "Plebeu"),
    ("Guard", "Guarda"),
    ("Knight", "Cavaleiro"),
    ("Mage", "Mago"),
    ("Priest", "Sacerdote"),
    ("Warrior", "Guerreiro"),
    ("Scout", "Batedor"),
    ("Spy", "Espiao"),
    ("Bandit", "Bandido"),
    ("Captain", "Capitao"),
    ("Horse", "Cavalo"),
    ("Wolf", "Lobo"),
    ("Bear", "Urso"),
    ("Lion", "Leao"),
    ("Tiger", "Tigre"),
    ("Rat", "Rato"),
    ("Bat", "Morcego"),
    ("Spider", "Aranha"),
    ("Snake", "Serpente"),
    ("Eagle", "Aguia"),
    ("Hawk", "Falcao"),
    ("Owl", "Coruja"),
    ("Raven", "Corvo"),
)

SCHOOL_WIZARD_WORDS = {
    "Abjurer",
    "Conjurer",
    "Diviner",
    "Enchanter",
    "Evoker",
    "Illusionist",
    "Necromancer",
    "Transmuter",
}

BESTIARY_REF_RE = re.compile(r"\bbestiary\s*\{\s*([a-z0-9-]+)\s*\}", re.I)


def _repo_path(path):
    return Path(path)


def _norm(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", texto.lower())


def _split_lista(valor):
    return [parte.strip() for parte in re.split(r"[;,]\s*", valor or "") if parte.strip()]


def _int_or_none(valor):
    valor = (valor or "").strip()
    if not valor:
        return None
    match = re.search(r"\d+", valor)
    return int(match.group(0)) if match else None


def _traduz_nome_criatura(nome_en):
    if nome_en in CREATURE_NAME_TRANSLATIONS:
        return CREATURE_NAME_TRANSLATIONS[nome_en]
    if nome_en in CREATURE_ALIASES:
        return CREATURE_ALIASES[nome_en][1]

    palavras = nome_en.split()
    if len(palavras) == 3 and palavras[2] == "Dragon":
        cor = dict(NAME_REPLACEMENTS).get(palavras[1], palavras[1])
        idade = dict(NAME_REPLACEMENTS).get(palavras[0], palavras[0])
        return f"Dragao {cor} {idade}".strip()

    if len(palavras) == 2 and palavras[1] == "Wizard" and palavras[0] in SCHOOL_WIZARD_WORDS:
        escola = dict(NAME_REPLACEMENTS).get(palavras[0], palavras[0])
        return f"Mago {escola}"

    partes = []
    mapa = dict(NAME_REPLACEMENTS)
    for palavra in palavras:
        limpo = palavra.strip(",")
        partes.append(mapa.get(limpo, limpo))
    return " ".join(partes)


def _slug_criatura(nome_en):
    if nome_en in CREATURE_ALIASES:
        return CREATURE_ALIASES[nome_en][0]
    return slugify(nome_en)


def _traduz_feature(nome):
    match = re.match(r"^(.*?)(\s*\([^)]*\))?$", (nome or "").strip())
    base = (match.group(1) if match else nome or "").strip()
    suffix = (match.group(2) if match else "") or ""
    suffix = re.sub(r"\bRecharge\b", "Recarga", suffix, flags=re.I)
    suffix = re.sub(
        r"\bCosts?\s+(\d+)\s+Actions?\b",
        r"Custa \1 Ações",
        suffix,
        flags=re.I,
    )
    suffix = re.sub(
        r"/(Day|Rest)\b",
        lambda m: "/Dia" if m.group(1).lower() == "day" else "/Descanso",
        suffix,
        flags=re.I,
    )
    return f"{FEATURE_PT.get(base, base)}{suffix}"


def _linha_pt(rotulo, valor):
    valor = (valor or "").strip()
    return f"- **{rotulo}:** {valor}" if valor else None


def _load_spell_alignment():
    alinhamento = {}
    for path in SPELL_ALIGNMENT_PATHS:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                en = (row.get("en") or row.get("magia_en") or "").strip()
                if not en:
                    continue
                candidatos = [
                    row.get("final"),
                    row.get("nome_pt"),
                    row.get("adaptado"),
                    row.get("traduzido"),
                    row.get("traduzido_literal"),
                ]
                pt = next((c.strip() for c in candidatos if c and c.strip()), en)
                chave = en.lower()
                alinhamento[chave] = {
                    "name_en": en,
                    "name_pt": pt,
                    "slug": slugify(pt),
                    "resolved": False,
                }
    return alinhamento


def _resolve_spell_alignment(alinhamento):
    magias = list(TbMagia.objects.only("nome", "slug"))
    por_nome = {_norm(m.nome): m.slug for m in magias}
    por_slug = {m.slug for m in magias}

    for info in alinhamento.values():
        manual = MANUAL_SPELL_ALIASES.get(info["name_en"].lower())
        if manual and manual[1] in por_slug:
            info["name_pt"] = manual[0]
            info["slug"] = manual[1]
            info["resolved"] = True
            continue

        candidatos = [info["name_pt"], info["name_en"]]
        for candidato in candidatos:
            if _norm(candidato) in por_nome:
                info["slug"] = por_nome[_norm(candidato)]
                info["resolved"] = True
                break
            candidato_slug = slugify(candidato)
            if candidato_slug in por_slug:
                info["slug"] = candidato_slug
                info["resolved"] = True
                break
    return alinhamento


def _spell_catalog(alinhamento):
    catalog = []
    for key, info in alinhamento.items():
        catalog.append(
            {
                "en_lower": key,
                "name_en": info["name_en"],
                "name_pt": info["name_pt"],
                "slug": info["slug"],
                "resolved": info["resolved"],
            }
        )
    return sorted(catalog, key=lambda item: len(item["en_lower"]), reverse=True)


def _is_boundary(texto, idx, end):
    before = texto[idx - 1] if idx > 0 else " "
    after = texto[end] if end < len(texto) else " "
    return not before.isalnum() and not after.isalnum()


def _extract_spell_refs(texto, catalog):
    texto = texto or ""
    lower = texto.lower()
    matches = []
    ocupado = [False] * len(lower)

    for info in catalog:
        needle = info["en_lower"]
        start = lower.find(needle)
        while start >= 0:
            end = start + len(needle)
            if _is_boundary(lower, start, end) and not any(ocupado[start:end]):
                for pos in range(start, end):
                    ocupado[pos] = True
                matches.append((start, info))
            start = lower.find(needle, start + 1)

    refs = []
    vistos = set()
    for _pos, info in sorted(matches, key=lambda item: item[0]):
        if info["slug"] in vistos:
            continue
        vistos.add(info["slug"])
        refs.append(
            {
                "name_en": info["name_en"],
                "name": info["name_pt"],
                "slug": info["slug"],
                "resolved": info["resolved"],
            }
        )
    return refs


def _tags_for_spell_refs(refs, uso=None):
    tags = []
    for ref in refs:
        if uso == "at-will":
            tags.append(f"cast{{spell:{ref['slug']}, at-will}}")
        elif uso:
            tags.append(f"cast{{spell:{ref['slug']}, uses{{{uso}, reset:long-rest}}}}")
        else:
            tags.append(f"cast{{spell:{ref['slug']}}}")
    return tags


def _spell_uses(texto, catalog):
    usos = []
    for linha in (texto or "").splitlines():
        match = re.match(r"\s*(At will|(\d+)/(?:day|rest)(?: each)?):\s*(.+)$", linha, re.I)
        if not match:
            continue
        label = match.group(1)
        quantidade = match.group(2)
        refs = _extract_spell_refs(match.group(3), catalog)
        if not refs:
            continue
        uso_tag = "at-will" if label.lower().startswith("at will") else quantidade
        usos.append(
            {
                "label_en": label,
                "label": "A vontade" if uso_tag == "at-will" else f"{quantidade}/dia",
                "uses": None if uso_tag == "at-will" else int(quantidade),
                "spells": refs,
                "tags": _tags_for_spell_refs(refs, uso_tag),
            }
        )
    return usos


def _split_secao(texto, catalog):
    texto = (texto or "").strip()
    if not texto:
        return []

    blocos = []
    atual = None
    # Um bloco oficial sempre começa como ``Nome. descrição`` na mesma linha.
    # Usar ``\s`` aqui fazia parágrafos como ``Claw attack.\n\nBite. ...``
    # virarem ações falsas, pois a quebra de linha era aceita como separador.
    sentence_start = r"(?:The|It|This|That|These|Those|When|While|If|On)\b"
    header = rf"(?!{sentence_start})[A-Z][A-Za-z' -]+(?:\s*\([^)]*\))?"
    partes = re.split(rf"(?m)(?=^{header}\.[ \t]+(?=\S))", texto)
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        match = re.match(rf"^({header})\.[ \t]+(.+)$", parte, re.S)
        if match:
            if atual:
                blocos.append(atual)
            nome_en = match.group(1).strip()
            corpo = match.group(2).strip()
            refs = _extract_spell_refs(corpo, catalog)
            atual = {
                "name_en": nome_en,
                "name": _traduz_feature(nome_en),
                "entries_en": [corpo],
                "entries": [corpo],
            }
            if refs:
                atual["spell_refs"] = refs
                atual["tags"] = _tags_for_spell_refs(refs)
            usos = _spell_uses(corpo, catalog)
            if usos:
                atual["spell_uses"] = usos
                tags = atual.setdefault("tags", [])
                for uso in usos:
                    tags.extend(uso["tags"])
                uso_slugs = {ref["slug"] for uso in usos for ref in uso.get("spells", [])}
                atual["tags"] = [
                    tag
                    for tag in tags
                    if tag not in {f"cast{{spell:{slug}}}" for slug in uso_slugs}
                ]
        elif atual:
            atual.setdefault("entries_en", []).append(parte)
            atual.setdefault("entries", []).append(parte)
            refs = _extract_spell_refs(parte, catalog)
            if refs:
                atual.setdefault("spell_refs", []).extend(refs)
                atual.setdefault("tags", []).extend(_tags_for_spell_refs(refs))

    if atual:
        blocos.append(atual)

    for bloco in blocos:
        if "tags" in bloco:
            bloco["tags"] = sorted(set(bloco["tags"]))
        if "spell_refs" in bloco:
            bloco["spell_refs"] = _dedupe_refs(bloco["spell_refs"])
    return blocos


def _dedupe_refs(refs):
    vistos = set()
    out = []
    for ref in refs:
        if ref["slug"] in vistos:
            continue
        vistos.add(ref["slug"])
        out.append(ref)
    return out


def _build_statblock(row, catalog):
    nome_en = row["Name"].strip()
    nome_pt = _traduz_nome_criatura(nome_en)

    statblock = {
        "name": nome_pt,
        "name_en": nome_en,
        "size": SIZE_PT.get(row.get("Size", "").strip(), row.get("Size", "").strip()),
        "size_en": row.get("Size", "").strip(),
        "type": _traduz_tipo(row.get("Type", "")),
        "type_en": row.get("Type", "").strip(),
        "alignment": _traduz_alinhamento(row.get("Alignment", "")),
        "alignment_en": row.get("Alignment", "").strip(),
        "ac": _int_or_none(row.get("AC")),
        "ac_text": row.get("AC", "").strip(),
        "hp": row.get("HP", "").strip(),
        "speed": _traduz_deslocamento(row.get("Speed", "")),
        "abilities": {
            "str": _int_or_none(row.get("Strength")),
            "dex": _int_or_none(row.get("Dexterity")),
            "con": _int_or_none(row.get("Constitution")),
            "int": _int_or_none(row.get("Intelligence")),
            "wis": _int_or_none(row.get("Wisdom")),
            "cha": _int_or_none(row.get("Charisma")),
        },
        "saving_throws": _traduz_abilities(row.get("Saving Throws", "")),
        "skills": [_traduz_pericia(s) for s in _split_lista(row.get("Skills", ""))],
        "damage_vulnerabilities": [_traduz_dano_condicao(d) for d in _split_lista(row.get("Damage Vulnerabilities", ""))],
        "damage_resistances": [_traduz_dano_condicao(d) for d in _split_lista(row.get("Damage Resistances", ""))],
        "damage_immunities": [_traduz_dano_condicao(d) for d in _split_lista(row.get("Damage Immunities", ""))],
        "condition_immunities": [_traduz_dano_condicao(c) for c in _split_lista(row.get("Condition Immunities", ""))],
        "senses": _traduz_sentidos(row.get("Senses", "")),
        "languages": _traduz_idiomas(row.get("Languages", "")),
        "cr": row.get("CR", "").strip(),
        "environment": _split_lista(row.get("Environment", "")),
        "treasure": row.get("Treasure", "").strip(),
    }

    tags = set()
    spell_refs = []
    for csv_key, json_key, _label in SECOES:
        blocos = _split_secao(row.get(csv_key, ""), catalog)
        statblock[json_key] = blocos
        for bloco in blocos:
            tags.update(bloco.get("tags", []))
            spell_refs.extend(bloco.get("spell_refs", []))
            for uso in bloco.get("spell_uses", []):
                tags.update(uso.get("tags", []))
                spell_refs.extend(uso.get("spells", []))

    statblock["spell_refs"] = _dedupe_refs(spell_refs)
    statblock["tags"] = _normaliza_tags_spell(tags)
    return statblock


def _normaliza_tags_spell(tags):
    tags = set(tags)
    especificas = set()
    for tag in tags:
        match = re.match(r"cast\{spell:([^,}]+),", tag)
        if match:
            especificas.add(match.group(1))
    for slug in especificas:
        tags.discard(f"cast{{spell:{slug}}}")
    return sorted(tags)


def _traduz_abilities(valor):
    texto = valor or ""
    for en, pt in ABILITY_PT.items():
        texto = re.sub(rf"\b{en}\b", pt, texto)
    return texto.strip()


def _descricao_markdown(row, statblock):
    nome = statblock["name"]
    linhas = [
        f"### {nome}",
        "",
        "",
        _linha_pt("Tipo", f"{statblock.get('size')} {statblock.get('type')}, {statblock.get('alignment')}".strip(", ")),
        _linha_pt("ND", statblock.get("cr")),
        _linha_pt("CA", statblock.get("ac_text")),
        _linha_pt("PV", statblock.get("hp")),
        _linha_pt("Deslocamento", statblock.get("speed")),
        _linha_pt("Salvaguardas", statblock.get("saving_throws")),
        _linha_pt("Pericias", ", ".join(statblock.get("skills") or [])),
        _linha_pt("Resistencias", ", ".join(statblock.get("damage_resistances") or [])),
        _linha_pt("Imunidades a dano", ", ".join(statblock.get("damage_immunities") or [])),
        _linha_pt("Imunidades a condicao", ", ".join(statblock.get("condition_immunities") or [])),
        _linha_pt("Sentidos", statblock.get("senses")),
        _linha_pt("Idiomas", statblock.get("languages")),
    ]

    spell_lines = []
    for ref in statblock.get("spell_refs", []):
        spell_lines.append(f"- `spell:{ref['slug']}` - {ref['name']}")
    if spell_lines:
        linhas.extend(["", "#### Magias referenciadas", *spell_lines])

    for _csv_key, json_key, label in SECOES:
        blocos = statblock.get(json_key) or []
        if not blocos:
            continue
        linhas.extend(["", f"#### {label}"])
        for bloco in blocos:
            detalhe = ""
            if bloco.get("spell_refs"):
                detalhe = " (" + ", ".join(ref["name"] for ref in bloco["spell_refs"]) + ")"
            linhas.append(f"- **{bloco['name']}**{detalhe}")

    texto = "\n".join(linha for linha in linhas if linha is not None)
    replaces = [
        ("plus five times your Ranger level", "mais cinco vezes o seu nível de Patrulheiro"),
        ("plus four times your Ranger level", "mais quatro vezes o seu nível de Patrulheiro"),
        ("the beast has a number of Hit Dice", "a besta possui um número de Dados de Vida"),
        ("equal to your Ranger level", "igual ao seu nível de Patrulheiro"),
        ("the drake has a number of Hit Dice", "o draco possui um número de Dados de Vida"),
        ("equal to your ranger level", "igual ao seu nível de Patrulheiro"),
        ("plus five times your ranger level", "mais cinco vezes o seu nível de Patrulheiro"),
        ("5 + five times your ranger level", "5 + cinco vezes o seu nível de Patrulheiro"),
        ("The banderhobb can have only one creature swallowed at a time", "O banderhobb pode ter apenas uma criatura engolida por vez"),
        ("The creature gains resistance to psychic damage", "A criatura ganha resistência a dano psíquico"),
        ("your Wisdom modifier", "seu modificador de Sabedoria"),
        ("The oblex learns all the languages a memory-drained target knows and gains all its skill proficiencies", "O oblex aprende todos os idiomas que um alvo com a memória drenada conhece e ganha todas as suas proficiências em perícias"),
        ("Eat Memories", "Comer Memórias"),
        ("Gentle Gusts", "Brisas Suaves"),
        ("Sun and Storms", "Sol e Tempestades"),
        ("Chill", "Frio"),
        ("Cold Gale", "Ventania Fria"),
        ("Armor Class", "Classe de Armadura"),
        ("Hit Points", "pontos de vida"),
    ]
    for en, pt in replaces:
        texto = texto.replace(en, pt)
    return texto


def _fields_for_row(row, catalog):
    nome_en = row["Name"].strip()
    nome_pt = _traduz_nome_criatura(nome_en)
    statblock = _build_statblock(row, catalog)
    return _slug_criatura(nome_en), {
        "nome": nome_pt,
        "tipo": statblock["type"],
        "tamanho": statblock["size"],
        "nd": statblock["cr"],
        "alinhamento": statblock["alignment"],
        "ca": statblock["ac"],
        "pv": statblock["hp"],
        "statblock_json": statblock,
        "tags_json": statblock.get("tags", []),
        "descricao_markdown": _descricao_markdown(row, statblock),
        "comunidade": False,
    }


def _read_rows(path, fontes):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if fontes:
        permitidas = {fonte.strip() for fonte in fontes if fonte.strip()}
        rows = [row for row in rows if row.get("Source", "").strip() in permitidas]
    return rows


def _fix_spell_creature_refs(apply):
    existing = set(TbBestiario.objects.values_list("slug", flat=True))
    alteradas = 0
    missing = {}

    for magia in TbMagia.objects.only("nome", "slug", "tags_json"):
        tags = magia.tags_json or []
        if not isinstance(tags, list):
            continue

        novas_tags = []
        mudou = False
        for tag in tags:
            novo = tag
            if isinstance(tag, str):
                for ref in BESTIARY_REF_RE.findall(tag):
                    if ref in existing:
                        continue
                    destino = TAG_CREATURE_ALIASES.get(ref)
                    if destino and destino in existing:
                        novo = re.sub(
                            rf"\bbestiary\s*\{{\s*{re.escape(ref)}\s*\}}",
                            f"bestiary{{{destino}}}",
                            novo,
                            flags=re.I,
                        )
                        mudou = True
                    else:
                        missing.setdefault(ref, set()).add(magia.slug)
            novas_tags.append(novo)

        if mudou:
            alteradas += 1
            if apply:
                magia.tags_json = novas_tags
                magia.save(update_fields=["tags_json"])

    return alteradas, missing


class Command(BaseCommand):
    help = "Importa criaturas novas; existentes divergentes exigem reparo auditado."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(CSV_PATH), help="Caminho do CSV de bestiario.")
        parser.add_argument("--apply", action="store_true", help="Grava as alteracoes no banco.")
        parser.add_argument("--limite", type=int, default=0, help="Limita a quantidade de linhas processadas.")
        parser.add_argument(
            "--fontes",
            nargs="*",
            default=[],
            help="Filtra fontes. Vazio importa todas as fontes do CSV.",
        )
        parser.add_argument(
            "--sem-fix-magias",
            action="store_true",
            help="Nao tenta corrigir bestiary{} em tags_json de TbMagia.",
        )
        parser.add_argument(
            "--sem-db",
            action="store_true",
            help="Preview sem consultar o banco. Incompativel com --apply.",
        )

    def handle(self, *args, **options):
        path = _repo_path(options["csv"])
        if not path.exists():
            raise SystemExit(f"CSV nao encontrado: {path}")

        apply = options["apply"]
        sem_db = options["sem_db"]
        if apply and sem_db:
            raise SystemExit("--sem-db e apenas para preview; remova --sem-db para usar --apply.")

        alinhamento = _load_spell_alignment()
        if not sem_db:
            alinhamento = _resolve_spell_alignment(alinhamento)
        catalog = _spell_catalog(alinhamento)

        rows = _read_rows(path, options["fontes"])
        if options["limite"]:
            rows = rows[: options["limite"]]

        slugs = [_slug_criatura(row["Name"].strip()) for row in rows]
        if len(slugs) != len(set(slugs)):
            raise CommandError("CSV contem slugs repetidos; revise a origem antes de importar.")

        criadas = inalteradas = 0
        conflitos = []
        unresolved_spells = set()
        exemplos = []

        with transaction.atomic() if apply else nullcontext():
            for row in rows:
                slug, fields = _fields_for_row(row, catalog)
                statblock = fields["statblock_json"]
                for ref in statblock.get("spell_refs", []):
                    if not sem_db and not ref.get("resolved"):
                        unresolved_spells.add(f"{ref['name_en']} -> {ref['slug']}")

                existing = (TbBestiario.objects.select_for_update().filter(slug=slug).first()
                            if apply else TbBestiario.objects.filter(slug=slug).first()) if not sem_db else None
                if existing:
                    changed = [key for key, value in fields.items() if getattr(existing, key) != value]
                    if existing.autor_id is not None:
                        changed.append("autor")
                    if changed:
                        conflitos.append(f"{slug}: {', '.join(changed)}")
                    else:
                        inalteradas += 1
                elif not sem_db and TbBestiario.objects.filter(
                        statblock_json__name_en=row["Name"].strip()).exists():
                    # O nome apenas sinaliza possivel duplicata; nunca prova identidade.
                    conflitos.append(f"{slug}: nome_en ja existe sob outro slug")
                else:
                    if apply:
                        TbBestiario.objects.create(slug=slug, **fields)
                    criadas += 1

                if len(exemplos) < 10:
                    exemplos.append(f"{row['Name']} -> {fields['nome']} [{slug}]")

            spell_ref_updates = missing_refs = None
            if not sem_db and not options["sem_fix_magias"]:
                spell_ref_updates, missing_refs = _fix_spell_creature_refs(apply)

        modo = "APLICADO" if apply else "PREVIEW"
        self.stdout.write(self.style.SUCCESS(f"{modo}: {len(rows)} criaturas processadas."))
        self.stdout.write(f"Criadas: {criadas} | Inalteradas: {inalteradas} | "
                          f"Pendentes de revisao: {len(conflitos)}")
        for conflict in conflitos[:10]:
            self.stdout.write(f"  Revisar {conflict}")
        if len(conflitos) > 10:
            self.stdout.write(f"  ... mais {len(conflitos) - 10} pendencias")
        if conflitos:
            self.stdout.write("Registros existentes nao foram sobrescritos; diferencas exigem revisao e aplicacao separadas.")
        if exemplos:
            self.stdout.write("Exemplos:")
            for item in exemplos:
                self.stdout.write(f"  - {item}")

        if sem_db:
            self.stdout.write("")
            self.stdout.write("Modo sem DB: slugs de magia foram estimados pelo CSV de alinhamento.")

        if unresolved_spells:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"Magias citadas sem match exato no banco: {len(unresolved_spells)}"))
            for item in sorted(unresolved_spells)[:25]:
                self.stdout.write(f"  - {item}")

        if spell_ref_updates is not None:
            self.stdout.write("")
            self.stdout.write(f"Tags de magia com bestiary{{}} corrigiveis: {spell_ref_updates}")
            if missing_refs:
                self.stdout.write(self.style.WARNING("Referencias bestiary{} ainda sem criatura correspondente:"))
                for ref, magias in sorted(missing_refs.items())[:25]:
                    self.stdout.write(f"  - {ref}: {', '.join(sorted(magias)[:8])}")
