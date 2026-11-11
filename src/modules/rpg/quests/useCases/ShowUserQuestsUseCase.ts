import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { Quest, QuestStatus } from '@/modules/rpg/quests/entities/Quest';

interface IRequest {
  userId: string;
  searchTerm: string;
  questStatus?: QuestStatus[];
  limit?: number;
}

@injectable()
export class ShowUserQuestsUseCase implements IBaseUseCase {
  constructor(
    @inject('QuestsRepository')
    private questsRepository: IQuestsRepository,
  ) {}

  public async execute({ userId, searchTerm, questStatus, limit }: IRequest): Promise<Quest[]> {
    const quests = await this.questsRepository.findAllUserQuests({
      userId,
      questMaster: userId,
      searchTerm,
      questStatus,
      options: { limit },
    });

    return quests;
  }
}
