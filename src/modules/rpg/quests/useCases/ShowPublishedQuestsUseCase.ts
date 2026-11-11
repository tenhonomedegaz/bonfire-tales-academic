import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { Quest } from '@/modules/rpg/quests/entities/Quest';

interface IRequest {
  searchTerm: string;
  limit?: number;
  questStatus?: string[];
  questDateAfter?: Date;
  questDateBefore?: Date;
}

@injectable()
export class ShowPublishedQuestsUseCase implements IBaseUseCase {
  constructor(
    @inject('QuestsRepository')
    private questsRepository: IQuestsRepository,
  ) {}

  public async execute({ searchTerm, limit, questStatus, questDateAfter, questDateBefore }: IRequest): Promise<Quest[]> {
    const quests = await this.questsRepository.findAllPublishedQuests({
      searchTerm,
      questStatus,
      questDateAfter,
      questDateBefore,
      options: { limit },
    });

    return quests;
  }
}
