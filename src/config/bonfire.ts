// =========================
//  BONFIRE ROLES
// =========================

export const bonfireRoles = {
  adminRoleName: 'Administração',
  moderatorRoleName: 'Moderação',
  subscriberRoleName: 'Colaborador',
  noviceRoleName: 'Novato (Primeiras Missões)',
  infractorRoleName: 'INFRATOR',
  masterRoleName: 'Mestre',
  testMasterRoleName: 'Mestre em Teste',
};

export const bonfireBotAdminUserIds = [
  '328308594305007618',
  '246030794718445568',
];

// =========================
//  RPG RANK ROLES
// =========================

export type RpgRankRole = {
  rank: number;
  name: string;
};

export const bonfireRpgRankRoles: RpgRankRole[] = [
  { rank: 1, name: 'Obsidiana (1-4)' },
  { rank: 2, name: 'Ametista (5-8)' },
  { rank: 3, name: 'Topázio (9-12)' },
  { rank: 4, name: 'Esmeralda (13-16)' },
  { rank: 5, name: 'Âmbar (17-19)' },
  { rank: 6, name: 'Rubi (20)' },
  { rank: 7, name: 'Diamante (Ascendido)' },
];

// Mapeamento de palavras-chave do rank para o emoji customizado do Discord
const RANK_EMOJI_MAP: Record<string, string> = {
  obsidiana: ':Obsidiana:',
  ametista: ':Ametista:',
  topazio: ':Topazio:',
  esmeralda: ':Esmeralda:',
  ambar: ':Ambar:',
  rubi: ':Rubi:',
  diamante: ':Diamante:',
};

/**
 * Retorna o nome do rank prefixado com seu emoji customizado do Discord.
 * Ex: "Obsidiana (1-4)" → ":Obsidiana: Obsidiana (1-4)"
 */
export function rankWithEmoji(rankName: string): string {
  const normalized = rankName
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .split(' ')[0]; // pega só a primeira palavra (ex: "obsidiana")

  const emoji = RANK_EMOJI_MAP[normalized];
  return emoji ? `${emoji} ${rankName}` : rankName;
}

// =========================
//  QUEST CONFIG
// =========================

export const minMinutesToPublishQuest = 1;
export const maxMinutesToPublishQuest = 10;
export const minMinutesIntervalToCreateQuest = 30;
export const minMinutesBeforeQuestStartToJoinQuest = 10;
export const minMinutesBeforeQuestStartToLeaveQuest = 10;

// =========================
//  CHANNELS
// =========================

export const bonfireChannels = {
  logChannelName: '🔧configuração-bots',
  questReportChannelName: '📂relatório-de-missões',
};

// =========================
//  TOKENS
// =========================

export const bonfireTokens = [
  { id: 'boost', name: '💥 Boost' },
  { id: 'missão', name: '⚔️ Missão Especial' },
  { id: 'superboost', name: '🚀 Superboost' },
];

// =========================
//  SHOP LIST
// =========================

export const shopList = [
  { shopType: 'Objetos Mágicos', shopChannelName: '🌀objetos-mágicos' },
  { shopType: 'Forja', shopChannelName: '🔨forja' },
  { shopType: 'Alquimista', shopChannelName: '🧪alquimista' },
  { shopType: 'Joalheria', shopChannelName: '💍joalheria' },
  { shopType: 'Estábulos', shopChannelName: '🏇🏿estábulos' },
];

// =========================
//  BASE SUBSCRIPTION PRODUCTS
//  These determine how many tokens each TIER grants monthly.
// =========================

export const bonfireProducts = [
  {
    subscriptionPlanName: 'token-missao',
    tokenXpBoost: 0,
    tokenMission: 1,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'token-boost',
    tokenXpBoost: 1,
    tokenMission: 0,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'token-superboost',
    tokenXpBoost: 0,
    tokenMission: 0,
    tokenSuperboost: 1,
  },
  {
    subscriptionPlanName: 'colaborador-conde-1m',
    tokenXpBoost: 0,
    tokenMission: 0,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-conde-3m',
    tokenXpBoost: 0,
    tokenMission: 0,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-conde-6m',
    tokenXpBoost: 0,
    tokenMission: 0,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-conde-12m',
    tokenXpBoost: 0,
    tokenMission: 0,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-marques-1m',
    tokenXpBoost: 0,
    tokenMission: 1,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-marques-3m',
    tokenXpBoost: 0,
    tokenMission: 3,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-marques-6m',
    tokenXpBoost: 0,
    tokenMission: 6,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-marques-12m',
    tokenXpBoost: 0,
    tokenMission: 12,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-duque-1m',
    tokenXpBoost: 1,
    tokenMission: 1,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-duque-3m',
    tokenXpBoost: 3,
    tokenMission: 3,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-duque-6m',
    tokenXpBoost: 6,
    tokenMission: 6,
    tokenSuperboost: 0,
  },
  {
    subscriptionPlanName: 'colaborador-duque-12m',
    tokenXpBoost: 12,
    tokenMission: 12,
    tokenSuperboost: 0,
  },
];

// =========================
//  SUBSCRIPTION OFFERS (NEW)
//  Used for MULTI-MONTH plans & discounts
// =========================

export type SubscriptionOffer = {
  id: string;
  tier: 'conde' | 'marques' | 'duque';
  months: number;
  bonusDays: number;
  price: number;
  displayName: string;
};

export const bonfireSubscriptionOffers: SubscriptionOffer[] = [
  // CONDE
  { id: 'colaborador-conde-1m', tier: 'conde', months: 1, bonusDays: 0, price: 19.90, displayName: 'Conde — 1 mês' },
  { id: 'colaborador-conde-3m', tier: 'conde', months: 3, bonusDays: 0, price: 53.73, displayName: 'Conde — 3 meses (10% OFF)' },
  { id: 'colaborador-conde-6m', tier: 'conde', months: 6, bonusDays: 0, price: 101.49, displayName: 'Conde — 6 meses (15% OFF)' },
  { id: 'colaborador-conde-12m', tier: 'conde', months: 12, bonusDays: 0, price: 179.10, displayName: 'Conde — 12 meses (25% OFF)' },

  // MARQUES
  { id: 'colaborador-marques-1m', tier: 'marques', months: 1, bonusDays: 0, price: 29.90, displayName: 'Marquês — 1 mês' },
  { id: 'colaborador-marques-3m', tier: 'marques', months: 3, bonusDays: 0, price: 80.73, displayName: 'Marquês — 3 meses (10% OFF)' },
  { id: 'colaborador-marques-6m', tier: 'marques', months: 6, bonusDays: 0, price: 152.49, displayName: 'Marquês — 6 meses (15% OFF)' },
  { id: 'colaborador-marques-12m', tier: 'marques', months: 12, bonusDays: 0, price: 269.10, displayName: 'Marquês — 12 meses (25% OFF)' },

  // DUQUE
  { id: 'colaborador-duque-1m', tier: 'duque', months: 1, bonusDays: 0, price: 39.90, displayName: 'Duque — 1 mês' },
  { id: 'colaborador-duque-3m', tier: 'duque', months: 3, bonusDays: 0, price: 107.73, displayName: 'Duque — 3 meses (10% OFF)' },
  { id: 'colaborador-duque-6m', tier: 'duque', months: 6, bonusDays: 0, price: 203.49, displayName: 'Duque — 6 meses (15% OFF)' },
  { id: 'colaborador-duque-12m', tier: 'duque', months: 12, bonusDays: 0, price: 359.10, displayName: 'Duque — 12 meses (25% OFF)' },
];

// =========================
//  THUMBNAILS
// =========================

export const thumbnails = {
  coins: 'https://cdn.discordapp.com/attachments/829816121665388555/910340297232351252/coins.png',
  map: 'https://cdn.discordapp.com/attachments/829816121665388555/910340380925526016/map.png',
  diamond: 'https://cdn.discordapp.com/attachments/829816121665388555/910340336394600478/diamond.png',
  dice: 'https://cdn.discordapp.com/attachments/829816121665388555/910340342744764446/dice.png',
  dices: 'https://cdn.discordapp.com/attachments/829816121665388555/910340350076403794/dices.png',
  gems: 'https://cdn.discordapp.com/attachments/829816121665388555/910340355499646976/gem.png',
  scroll: 'https://cdn.discordapp.com/attachments/829816121665388555/910340228403843103/scroll.png',
  scroll2: 'https://cdn.discordapp.com/attachments/829816121665388555/910340237346078771/scroll2.png',
  scroll3: 'https://cdn.discordapp.com/attachments/829816121665388555/910340242987433984/scroll3.png',
  queue: 'https://cdn.discordapp.com/attachments/829816121665388555/910340608336478288/queue.png',
  clock: 'https://cdn.discordapp.com/attachments/829816121665388555/910340291804938291/clock.png',
  stopwatch: 'https://cdn.discordapp.com/attachments/829816121665388555/910873111770038332/stopwatch.png',
  hourglass: 'https://cdn.discordapp.com/attachments/829816121665388555/910873114244702268/hourglass.png',
  notes: 'https://cdn.discordapp.com/attachments/829816121665388555/910340387032424458/notes.png',
  rpgGame: 'https://cdn.discordapp.com/attachments/829816121665388555/910340221785210880/rpg-game.png',
  wand: 'https://cdn.discordapp.com/attachments/829816121665388555/910340283303080046/wand.png',
  sword: 'https://cdn.discordapp.com/attachments/829816121665388555/910340248192565278/sword.png',
  tokenStar: 'https://cdn.discordapp.com/attachments/829816121665388555/910340265401806888/token-star.png',
  gift: 'https://cdn.discordapp.com/attachments/829816121665388555/910340365343670332/gift.png',
  tokens: 'https://cdn.discordapp.com/attachments/829816121665388555/910340254748246066/token.png',
  crown: 'https://cdn.discordapp.com/attachments/829816121665388555/910340304278786068/crown.png',
  crown1: 'https://cdn.discordapp.com/attachments/829816121665388555/910340310943547452/crown1.png',
  crown2: 'https://cdn.discordapp.com/attachments/829816121665388555/910340319013388298/crown2.png',
  crown3: 'https://cdn.discordapp.com/attachments/829816121665388555/910340330220576830/crown3.png',
  mods: 'https://cdn.discordapp.com/attachments/829816121665388555/910340277250699284/users.png',
  jewel: 'https://cdn.discordapp.com/attachments/829816121665388555/910340372146831390/jewel.png',
};
