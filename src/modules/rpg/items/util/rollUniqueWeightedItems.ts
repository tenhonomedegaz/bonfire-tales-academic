import { Chance } from 'chance';

interface ItemTable {
  id: string | number;
  weight: number;
}

export function rollUniqueWeightedItems(
  itemsTable: ItemTable[],
  quantityToPick: number,
): (string | number)[] {
  const chance = new Chance();

  const items = itemsTable.map((item) => item.id);
  const weights = itemsTable.map((item) => item.weight);

  if (items.length !== weights.length) {
    throw new Error('Missing items or weights');
  }

  const rolledItems = [...Array(quantityToPick).keys()].map(() => {
    const rolledItem = chance.weighted(items, weights);

    // Remove o item que saiu da tabela pra não repetir
    const rolledItemIdx = items.findIndex((element) => element === rolledItem);
    items.splice(rolledItemIdx, 1);
    weights.splice(rolledItemIdx, 1);

    return rolledItem;
  });

  return rolledItems;
}
