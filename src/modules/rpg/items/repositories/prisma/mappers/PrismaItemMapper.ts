import { Item } from '@/modules/rpg/items/entities/Item';
import { Item as PrismaItem } from '@prisma/client';

export class PrismaItemMapper {
  static toDomain(item: PrismaItem): Item {
    return {
      id: item.id,
      shopType: item.shopType as any,
      name: item.name,
      translatedName: item.translatedName,
      rarity: item.rarity as any,
      tier: item.tier as any,
      rollChance: item.rollChance,
      consumable: item.consumable,
      sintonization: item.sintonization as any,
      type: item.type as any,
      description: item.description,
      baseBook: item.baseBook,
      alwaysOnTheStore: item.alwaysOnTheStore,
      price: item.price,
      createdAt: item.createdAt,
      updatedAt: item.updatedAt,
    };
  }

  static toPersistence(item: Item): any {
    return {
      id: item.id,
      shopType: item.shopType,
      name: item.name,
      translatedName: item.translatedName,
      rarity: item.rarity,
      tier: item.tier,
      rollChance: item.rollChance,
      consumable: item.consumable,
      sintonization: item.sintonization,
      type: item.type,
      description: item.description,
      baseBook: item.baseBook,
      alwaysOnTheStore: item.alwaysOnTheStore,
      price: item.price,
      createdAt: item.createdAt,
      updatedAt: item.updatedAt,
    };
  }
}
