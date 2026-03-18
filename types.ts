


export interface LinkItem {
  label: string;
  href: string;
  kind?: 'spell' | 'item' | 'rule';
}

export interface ContractCardData {
  rank: string;
  type: string;
  title: string;
  description: string;
  reward: string;
}

export interface MegaColumn {
  title: string;
  items: LinkItem[];
}

export interface NavItem {
  label: string;
  type: 'link' | 'mega';
  href?: string;
  columns?: MegaColumn[];
}

export interface SocialLink {
  label: string;
  href: string;
  iconId?: string;
}

export interface HeaderData {
  nav: NavItem[];
  search: {
    enabled: boolean;
    placeholder: string;
  };
  ctas: {
    collaborator: LinkItem;
    catarse: LinkItem;
  };
  social: SocialLink[];
}

export interface HeroSection {
  headline: string;
  subhead: string;
  ctaPrimary: LinkItem;
  ctaSecondary: LinkItem;
}

export interface VideoSection {
  title: string;
  description: string;
  embedUrl: string;
}

export interface HowToPlaySection {
  title: string;
  steps: string[];
}

export interface FeatureItem {
  title: string;
  description: string;
  iconId: string;
}

export interface FeaturesSection {
  title: string;
  items: FeatureItem[];
}

export interface MapSection {
  title: string;
  text: string;
  cta: LinkItem;
}

export interface UpdateItem {
  title: string;
  date: string;
  href: string;
}

export interface UpdatesSection {
  title: string;
  items: UpdateItem[];
}

export interface JournalSection {
  title: string;
  text: string;
  cta: LinkItem;
}

export interface CollaboratorSection {
  title: string;
  text: string;
  cta: LinkItem;
  secondary: LinkItem;
}

export interface AboutSection {
  title: string;
  text: string;
  cta: LinkItem;
}

export interface LiveNowSection {
  enabled: boolean;
  status: 'online' | 'offline';
  title: string;
  platform: 'twitch' | 'youtube';
  href: string;
  scheduleText?: string;
}

export interface SocialSection {
  title: string;
  text: string;
  links: SocialLink[];
}

export interface HomeData {
  hero: HeroSection;
  video: VideoSection;
  howToPlay: HowToPlaySection;
  features: FeaturesSection;
  map: MapSection;
  updates: UpdatesSection;
  journal: JournalSection;
  collaborator: CollaboratorSection;
  about: AboutSection;
  liveNow: LiveNowSection;
  socialSection: SocialSection;
}

export interface SiteInfo {
  name: string;
  tagline: string;
  logoPath: string;
  links: {
    discord: string;
    catarse: string;
  };
}

export interface SiteData {
  site: SiteInfo;
  header: HeaderData;
  home: HomeData;
}

export interface GlossaryTable {
  title?: string;
  headers: string[];
  rows: string[][];
}

export interface GlossaryItem {
  slug: string;
  term: string;
  summary: string;
  body: string;
  categories?: string[];
  aliases?: string[];
  table?: GlossaryTable;
}

// --- IDIOMAS ---

export interface WritingSystem {
  name: string;
  direction: 'ltr' | 'rtl' | 'vertical';
  type: 'Alfabeto' | 'Runas' | 'Ideogramas' | 'Abjad' | 'Tátil';
  notes?: string;
}

export interface Glyph {
  char: string;
  translit: string;
  ipa?: string;
  notes?: string;
}

export interface LanguagePhrase {
  pt: string;
  native: string;
  translit: string;
  usage: string;
}

export interface BasicSign {
  slug: string;
  label: string;
  description: string;
}

export interface Language {
  slug: string;
  name: string;
  nativeName: string;
  category: 'Comum' | 'Regional' | 'Exótico' | 'Planar' | 'Sinais' | 'Escrita';
  modality: 'spoken' | 'signed' | 'script';
  family: string;
  regions: string[];
  peoples: string[];
  status: 'Comum' | 'Litúrgico' | 'Acadêmico' | 'Proibido' | 'Arcaico' | 'Secreto' | 'Inclusivo';
  description: string[];
  referenceLanguage: string;
  writingSystem: WritingSystem;
  glyphs?: Glyph[];
  pronunciationTips?: string[];
  phrases?: LanguagePhrase[];
  dictionary?: Record<string, string>;
  
  // Engines
  transliterationEngine: 'latin' | 'runic' | 'tengwar' | 'draconic' | 'braille';
  ttsEngine: 'gemini' | 'webspeech' | 'none';
  
  // Accessibility
  accessibility?: {
    supportsBraille?: boolean;
    supportsSign?: boolean;
    manualAlphabet?: Record<string, string>;
    basicSigns?: BasicSign[];
  };

  // Lore
  dialects?: { name: string; desc: string }[];
  namingCustoms?: { title: string; body: string; examples: string[] }[];
}

export interface GameOption {
  name: string;
  slug: string;
  type: "Estilo de Luta" | "Invocação Mística" | "Estilo de Ki" | "Manobra de Combate" | "Infusão";
  classes: string[];
  level: number;
  tags: string[];
  description: string;
  effect: string;
  prerequisites: {
    abilitiesAll: { ability: string; min: number }[];
    abilitiesAny: { group: string; options: { ability: string; min: number }[] }[];
    skills: string[];
  };
}
// FIX: Added missing Familiar and FamiliarData types
// --- FAMILIARES & COMPANHEIROS ---

export interface FamiliarTrait {
  name: string;
  frequency?: string;
  text: string;
  bullets?: string[];
}

export interface FamiliarAction {
  name: string;
  recharge?: string;
  trigger?: string;
  type?: string;
  attack?: {
    toHit: string;
    reach: string;
    targets: string;
  };
  damage?: {
    dice: string;
    avg: number;
    type: string;
  }[];
  effect?: string;
  effects?: (string | { name: string; text: string })[];
}

export interface FamiliarSpellcasting {
  ability: string;
  saveDC: number;
  attackBonus: string;
  lists: {
    atWill?: string[];
    perDay?: Record<string, string[]>;
  };
}

export interface FamiliarRandomTable {
  name: string;
  roll: string;
  rows: {
    result: string;
    text: string;
  }[];
}

export interface FamiliarVariant {
  slug: string;
  name: string;
  image?: string;
  overrides: any; 
}

export interface Familiar {
  slug: string;
  name: string;
  subtitle?: string;
  tags: string[];
  size: string;
  creatureType: {
    type: string;
    typeKey: string;
    subtype?: string;
    subtypeKey?: string;
  };
  images: {
    portrait: string;
  };
  combat: {
    challenge: {
      cr: string;
      pb: string;
    };
    ac: {
      value: number;
      source: string;
    };
    hp: {
      average: number;
      formula: string;
    };
    speeds: {
      type: string;
      value: string;
    }[];
    abilities: {
      str: number;
      dex: number;
      con: number;
      int: number;
      wis: number;
      cha: number;
    };
    skills?: { name: string; value: string }[];
    damage?: {
      resistances?: string[];
      immunities?: string[];
      vulnerabilities?: string[];
    };
    conditions?: {
      immunities?: string[];
    };
    senses?: { name: string; range: string }[];
    languages?: {
      understands?: string[];
      telepathy?: {
        range: string;
      };
    };
  };
  traits?: FamiliarTrait[];
  actions?: FamiliarAction[];
  bonusActions?: FamiliarAction[];
  reactions?: FamiliarAction[];
  spellcasting?: FamiliarSpellcasting;
  lore?: {
    habitat: string;
    behavior: string;
    narrative: string;
  };
  randomTables?: FamiliarRandomTable[];
  variants?: FamiliarVariant[];
}

export interface FamiliarData {
  entries: Familiar[];
  typeGlossary: Record<string, {
    title: string;
    text: string;
  }>;
}
