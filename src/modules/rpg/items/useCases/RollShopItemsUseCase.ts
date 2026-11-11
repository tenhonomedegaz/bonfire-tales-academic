import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IItemsRepository } from '@/modules/rpg/items/repositories/IItemsRepository';
import { Item } from '@/modules/rpg/items/entities/Item';
import { rollUniqueWeightedItems } from '../util/rollUniqueWeightedItems';

@injectable()
export class RollShopItemsUseCase implements IBaseUseCase {
  constructor(
    @inject('ItemsRepository')
    private itemsRepository: IItemsRepository,
  ) {}

  public async execute({
    shopType,
    itemsAmountToRoll,
  }: {
    shopType: string;
    itemsAmountToRoll: number;
  }): Promise<Item[]> {
    const items = await this.itemsRepository.findAllRollable({
      shopType,
      // consumable:
      // rarity: 'Incomum',
      // rarity: 'Raro',
      // alwaysOnTheStore: false,
    });

    if (items.length >= 1) {
      const itemsToRoll = items
        .filter((item) => item.alwaysOnTheStore === false)
        .map((item) => ({
          id: item.id,
          weight: item.rollChance,
        }));

      const rolledItems = rollUniqueWeightedItems(itemsToRoll, itemsAmountToRoll);

      const shopItems = items.filter(
        (item) => item.alwaysOnTheStore === true || rolledItems.includes(item.id),
      );

      return shopItems;
    }

    return [];
  }
}
