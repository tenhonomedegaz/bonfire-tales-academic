import { Item } from '@/modules/rpg/items/entities/Item';
import { IItemsRepository } from '@/modules/rpg/items/repositories/IItemsRepository';
import { PrismaItemMapper } from '@/modules/rpg/items/repositories/prisma/mappers/PrismaItemMapper';
import { ICreateItemDTO, IFindAllRollableDTO, IFindAllByNameDTO } from '@/modules/rpg/items/dtos';
import { prisma } from '@/shared/infra/database/prisma';

export class PrismaItemsRepository implements IItemsRepository {
  public async create(data: ICreateItemDTO): Promise<Item> {
    const item = await prisma.item.create({
      data,
    });
    return PrismaItemMapper.toDomain(item);
  }

  public async findAllRollable({ shopType }: IFindAllRollableDTO): Promise<Item[]> {
    const items = await prisma.item.findMany({
      where: { shopType },
    });
    return items.map(PrismaItemMapper.toDomain);
  }

  public async findById(id: string): Promise<Item | null> {
    const item = await prisma.item.findUnique({
      where: { id },
    });
    return item ? PrismaItemMapper.toDomain(item) : null;
  }

  public async findAllByName({ itemName, options }: IFindAllByNameDTO): Promise<Item[]> {
    const items = await prisma.item.findMany({
      where: {
        OR: [
          { name: { contains: itemName, mode: 'insensitive' } },
          { translatedName: { contains: itemName, mode: 'insensitive' } },
        ],
      },
      take: options?.limit || undefined,
    });
    return items.map(PrismaItemMapper.toDomain);
  }
}
