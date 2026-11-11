import { Quest } from '@/modules/rpg/quests/entities/Quest';
import {
  ICreateQuestDTO,
  IFindAllUserQuestsDTO,
  IFindAllOthersQuestsDTO,
  IFindAllPublishedQuestsDTO,
  IFindAllSubscribedInIntervalDTO,
  IFindAllQuestsCreatedInIntervalDTO,
} from '@/modules/rpg/quests/dtos';

export interface IQuestsRepository {
  create(data: ICreateQuestDTO): Promise<Quest>;
  save(data: Quest): Promise<Quest>;
  deleteById(id: string): Promise<void>;
  findById(id: string): Promise<Quest | null>;
  findByChannelId(channelId: string): Promise<Quest | null>;
  findAllUserQuests(data: IFindAllUserQuestsDTO): Promise<Quest[]>;
  findAllOthersQuests(data: IFindAllOthersQuestsDTO): Promise<Quest[]>;
  findAllPublishedQuests(data: IFindAllPublishedQuestsDTO): Promise<Quest[]>;
  findAllSubscribedInInterval(data: IFindAllSubscribedInIntervalDTO): Promise<Quest[]>;
  findAllQuestsCreatedInInterval(data: IFindAllQuestsCreatedInIntervalDTO): Promise<Quest[]>;
}
