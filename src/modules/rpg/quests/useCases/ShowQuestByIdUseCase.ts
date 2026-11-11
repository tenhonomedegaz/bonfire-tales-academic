import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { Quest } from '@/modules/rpg/quests/entities/Quest';

@injectable()
export class ShowQuestByIdUseCase implements IBaseUseCase {
  constructor(
    @inject('QuestsRepository')
    private questsRepository: IQuestsRepository,
  ) {}

  public async execute(id: string): Promise<Quest | null> {
    const quest = await this.questsRepository.findById(id);

    return quest;
  }
}
