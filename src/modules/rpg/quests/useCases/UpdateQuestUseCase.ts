import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { Quest } from '@/modules/rpg/quests/entities/Quest';

type IRequest = Quest;

@injectable()
export class UpdateQuestUseCase implements IBaseUseCase {
  constructor(
    @inject('QuestsRepository')
    private questsRepository: IQuestsRepository,
  ) {}

  public async execute(quest: IRequest): Promise<Quest> {
    const updatedQuest = await this.questsRepository.save(quest);

    return updatedQuest;
  }
}
