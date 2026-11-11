import { injectable, inject } from 'tsyringe';
import { Quest } from '../entities/Quest';
import { IQuestsRepository } from '../repositories/IQuestsRepository';

@injectable()
export class ShowQuestByChannelIdUseCase {
  constructor(
    @inject('QuestsRepository')
    private questsRepository: IQuestsRepository
  ) {}

  async execute(channelId: string): Promise<Quest | null> {
    const quest = await this.questsRepository.findByChannelId(channelId);
    return quest || null;
  }
}