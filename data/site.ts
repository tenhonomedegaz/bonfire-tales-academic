
import { SiteData } from '../types';

export const SITE_DATA: SiteData = {
  "site": {
    "name": "Bonfire Tales",
    "tagline": "RPG Dark Fantasy & Living World",
    "logoPath": "https://i.imgur.com/rIDQh7r.png",
    "links": {
      "discord": "https://discord.gg/bonfire-placeholder",
      "catarse": "https://www.catarse.me/bonfire-placeholder"
    }
  },
  "header": {
    "search": {
      "enabled": true,
      "placeholder": "Buscar regras, itens ou monstros..."
    },
    "nav": [
      {
        "label": "Sistemas",
        "type": "mega",
        "columns": [
          {
            "title": "Fundamentos",
            "items": [
              { "label": "Regras e Punições", "href": "/sistemas/regras-e-punicoes" },
              { "label": "Glossário", "href": "/sistemas/glossario" }
            ]
          },
          {
            "title": "Aventurando-se",
            "items": [
              { "label": "Criação de Ficha", "href": "/sistemas/criacao-de-ficha" },
              { "label": "Missões e Ranks", "href": "/sistemas/missoes" }
            ]
          }
        ]
      },
      {
        "label": "Jogador",
        "type": "mega",
        "columns": [
          {
            "title": "Construção",
            "items": [
              { "label": "Raça", "href": "/jogador/raca" },
              { "label": "Classes", "href": "/jogador/classes" },
              { "label": "Antecedente", "href": "/jogador/antecedente" }
            ]
          },
          {
            "title": "Detalhes",
            "items": [
              { "label": "Talentos", "href": "/jogador/talentos" },
              { "label": "Idiomas", "href": "/jogador/idiomas" },
              { "label": "Ferramentas", "href": "/jogador/ferramentas" }
            ]
          },
          {
            "title": "Recursos",
            "items": [
              { "label": "Opções Adicionais", "href": "/jogador/opcoes-adicionais" },
              { "label": "Familiares", "href": "/jogador/familiares" },
              { "label": "Companheiros", "href": "/jogador/companheiros" }
            ]
          }
        ]
      },
      {
        "label": "Mestre",
        "type": "mega",
        "columns": [
          {
            "title": "Guia",
            "items": [
              { "label": "Se tornando mestre", "href": "/mestre/se-tornando-mestre" },
              { "label": "Bestiario", "href": "/mestre/bestiario" }
            ]
          },
          {
            "title": "Desafios",
            "items": [
              { "label": "Armadilhas e Perigos de Área", "href": "/mestre/armadilhas-e-perigos" },
              { "label": "Condições", "href": "/mestre/condicoes" }
            ]
          },
          {
            "title": "Gestão",
            "items": [
              { "label": "Mercado de Mestre", "href": "/mestre/mercado-de-mestre" },
              { "label": "Tipos de Missões", "href": "/mestre/tipos-de-missoes" }
            ]
          }
        ]
      },
      {
        "label": "Mercado",
        "type": "mega",
        "columns": [
          {
            "title": "Equipamento",
            "items": [
              { "label": "Armas", "href": "/mercado/armas" },
              { "label": "Itens Mundanos", "href": "/mercado/itens-mundanos" },
              { "label": "Itens Mágicos", "href": "/mercado/itens-magicos" }
            ]
          },
          {
            "title": "Comércio",
            "items": [
              { "label": "Negociações", "href": "/mercado/negociacoes" },
              { "label": "Veiculos", "href": "/mercado/veiculos" },
              { "label": "Criaturas", "href": "/mercado/criaturas" }
            ]
          }
        ]
      },
      {
        "label": "Magias",
        "type": "mega",
        "columns": [
          {
            "title": "Grimório",
            "items": [
              { "label": "Escolas de Magias", "href": "/magias/escolas" },
              { "label": "Listas de Magias", "href": "/magias/listas" },
              { "label": "Congregação Magica", "href": "/magias/congregacao" }
            ]
          }
        ]
      },
      { "label": "Mapa", "type": "link", "href": "/mapa" },
      {
        "label": "Mundo",
        "type": "mega",
        "columns": [
          {
            "title": "Lore",
            "items": [
              { "label": "Cosmo", "href": "/mundo/cosmo" },
              { "label": "Linha do Tempo", "href": "/mundo/linha-do-tempo" }
            ]
          },
          {
            "title": "Atlas",
            "items": [
              { "label": "Regiões", "href": "/mundo/regioes" },
              { "label": "Organizações", "href": "/mundo/organizacoes" },
              { "label": "Jornal", "href": "/mundo/jornal" }
            ]
          }
        ]
      },
      { "label": "Atualizações", "type": "link", "href": "/atualizacoes" }
    ],
    "ctas": {
      "collaborator": { "label": "Colaborador", "href": "/colaborador" },
      "catarse": { "label": "Catarse", "href": "/catarse" }
    },
    "social": [
      { "label": "Discord", "href": "https://discord.gg/placeholder", "iconId": "discord" },
      { "label": "X / Twitter", "href": "https://twitter.com/placeholder", "iconId": "twitter" },
      { "label": "YouTube", "href": "https://youtube.com/placeholder", "iconId": "youtube" },
      { "label": "Instagram", "href": "https://instagram.com/placeholder", "iconId": "instagram" },
      { "label": "TikTok", "href": "https://tiktok.com/@placeholder", "iconId": "tiktok" }
    ]
  },
  "home": {
    "hero": {
      "headline": "A Fogueira chama.",
      "subhead": "Um mundo vivo de Dark Fantasy onde suas escolhas moldam a história do servidor. Jogue via Discord, explore o mapa e sobreviva.",
      "ctaPrimary": { "label": "Entrar no Discord", "href": "/discord" },
      "ctaSecondary": { "label": "Ler o Sistema", "href": "/sistemas/regras-e-punicoes" }
    },
    "video": {
      "title": "O que é o Bonfire?",
      "description": "60 segundos para entender como funciona um RPG West Marches vivo.",
      "embedUrl": "https://www.youtube.com/embed/xxFmq9Qk5nw"
    },
    "howToPlay": {
      "title": "Jornada do Iniciante",
      "steps": [
        "Acesse o Discord e leia o Grimório básico.",
        "Crie seu personagem usando nosso bot ou planilha.",
        "Aguarde o anúncio de missões no canal #contratos."
      ]
    },
    "features": {
      "title": "Por que o Bonfire?",
      "items": [
        {
          "title": "Mundo Vivo",
          "description": "O mapa e a política mudam com base no que os jogadores fazem nas sessões.",
          "iconId": "globe"
        },
        {
          "title": "Progressão West Marches",
          "description": "Jogue quando puder. Sem horários fixos obrigatórios, apenas quando houver contratos.",
          "iconId": "clock"
        },
        {
          "title": "Acessibilidade Nativa",
          "description": "Suporte a Libras e Braille integrados ao sistema de jogo e lore.",
          "iconId": "accessibility"
        }
      ]
    },
    "map": {
      "title": "Atlas de Eldoria",
      "text": "Navegue pelas regiões seguras e terras selvagens. O mapa atualiza conforme os jogadores descobrem novos locais.",
      "cta": { "label": "Explorar Mapa", "href": "/mapa" }
    },
    "updates": {
      "title": "Últimas do Grimório",
      "items": [
        { "title": "Patch 1.2 — Nova Classe: O Arcanista de Sangue", "date": "12 Fev", "href": "/atualizacoes" },
        { "title": "Evento de Mundo: A Lua Vermelha", "date": "05 Fev", "href": "/atualizacoes" },
        { "title": "Hotfix: Ajuste de Dano em Armas Pesadas", "date": "01 Fev", "href": "/atualizacoes" }
      ]
    },
    "journal": {
      "title": "Crônicas",
      "text": "Leia os relatos das últimas campanhas e como elas alteraram a política do mundo.",
      "cta": { "label": "Ler Crônicas", "href": "/mundo/jornal" }
    },
    "collaborator": {
      "title": "Mantenha a Chama Acesa",
      "text": "O Bonfire Tales é mantido pela comunidade. Colaboradores ganham acesso antecipado a playtests, skins exclusivas no Discord e votam nos rumos do mundo.",
      "cta": { "label": "Ver Benefícios", "href": "/colaborador" },
      "secondary": { "label": "Catarse", "href": "/catarse" }
    },
    "about": {
      "title": "Quem Somos",
      "text": "Somos um coletivo apaixonado de narradores, designers e artistas dedicados a criar a próxima geração de RPG de texto e voz organizado. Nosso objetivo é transformar campanhas isoladas em um universo compartilhado massivo.",
      "cta": { "label": "Saiba mais", "href": "/quem-somos" }
    },
    "liveNow": {
      "enabled": true,
      "status": "online",
      "title": "Mesa Oficial: As Cinzas de Velkar",
      "platform": "twitch",
      "href": "https://twitch.tv/placeholder",
      "scheduleText": "Toda terça às 20h"
    },
    "socialSection": {
      "title": "Conecte-se",
      "text": "Siga nossas redes para não perder nenhum anúncio, arte conceitual ou evento.",
      "links": [
         { "label": "Discord", "href": "https://discord.gg/placeholder", "iconId": "discord" },
         { "label": "X / Twitter", "href": "https://twitter.com/placeholder", "iconId": "twitter" },
         { "label": "YouTube", "href": "https://youtube.com/placeholder", "iconId": "youtube" },
         { "label": "Instagram", "href": "https://instagram.com/placeholder", "iconId": "instagram" },
         { "label": "TikTok", "href": "https://tiktok.com/@placeholder", "iconId": "tiktok" }
      ]
    }
  }
};
