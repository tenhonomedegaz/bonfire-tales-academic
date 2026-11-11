import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { Quest, QuestStatus } from '@/modules/rpg/quests/entities/Quest';

interface IRequest {
  userIdToExclude: string;
  searchTerm: string;
  questStatus?: QuestStatus[];
  limit?: number;
}

@injectable()
export class ShowOthersUsersQuestsUseCase implements IBaseUseCase {
  constructor(
    @inject('QuestsRepository')
    private questsRepository: IQuestsRepository,
  ) {}

  public async execute({
    userIdToExclude,
    searchTerm,
    questStatus,
    limit,
  }: IRequest): Promise<Quest[]> {
    const quests = await this.questsRepository.findAllOthersQuests({
      userId: userIdToExclude,
      searchTerm,
      questStatus,
      options: { limit },
    });

    return quests;
  }
}
