export interface Item {
  id: string;
  shopType: string;
  name: string;
  translatedName: string;
  rarity: string;
  tier: string;
  rollChance: number;
  consumable: boolean;
  sintonization: string;
  type: string;
  description: string;
  baseBook: string;
  alwaysOnTheStore: boolean;
  price: string;
  createdAt: Date;
  updatedAt: Date;
}
