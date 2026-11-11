import { Item } from '@/modules/rpg/items/entities/Item';
import { ICreateItemDTO, IFindAllRollableDTO, IFindAllByNameDTO } from '@/modules/rpg/items/dtos';

export interface IItemsRepository {
  create(data: ICreateItemDTO): Promise<Item>;
  findById(id: string): Promise<Item | null>;
  findAllRollable(data: IFindAllRollableDTO): Promise<Item[]>;
  findAllByName(data: IFindAllByNameDTO): Promise<Item[]>;
}
