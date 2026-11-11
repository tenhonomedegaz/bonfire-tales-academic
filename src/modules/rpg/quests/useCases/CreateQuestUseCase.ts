import { injectable, inject } from 'tsyringe';
import { isBefore, isAfter, addMinutes, addDays, subMinutes } from 'date-fns';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { AppError } from '@/shared/errors/AppError';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { isValidTimeFormat, isValidDateFormat, isValidUrl } from '@/shared/util/validators';
import {
  minMinutesIntervalToCreateQuest,
} from '@/config/bonfire';
import { ISchedulerProvider } from '@/shared/providers/SchedulerProvider/models/ISchedulerProvider';
import { PublishQuestJob } from '@/modules/rpg/jobs/PublishQuestJob';
import { AutoQuestQueueJob } from '@/modules/rpg/jobs/AutoQuestQueueJob';
import { ShowCurrentDedicatedRankUseCase } from '@/modules/rpg/dedicatedRank/useCases/ShowCurrentDedicatedRankUseCase';
import { nowInBrazil, parseBrazilDateTime } from '@/shared/util/dateTime';

type IRequest = {
  guildId: string;
  name: string;
  description: string;
  questDate: string;
  questTime: string;
  playersAmount: number;
  rules: string;
  tags: string[];
  type: string;
  tableUrl: string;
  questMaster: string;
  allowedRanks: string[];
  mandatoryPlayers?: string[];
  highPriorityPlayers: string[];
  createdBy: string;
  scheduler: ISchedulerProvider;
  requestedAt?: Date;
};

function isValidDate(date: unknown) {
  return date instanceof Date && !Number.isNaN(date.getTime());
}

@injectable()
export class CreateQuestUseCase implements IBaseUseCase {
  constructor(
    @inject('QuestsRepository')
    private questsRepository: IQuestsRepository,
    private showCurrentDedicatedRankUseCase: ShowCurrentDedicatedRankUseCase,
  ) {}

  public async execute({
    guildId,
    name,
    description,
    questDate,
    questTime,
    playersAmount,
    rules,
    tags,
    type,
    tableUrl,
    questMaster,
    allowedRanks,
    mandatoryPlayers = [],
    highPriorityPlayers,
    createdBy,
    scheduler,
    requestedAt,
  }: IRequest): Promise<Quest> {
    if (!isValidDateFormat(questDate)) {
      throw new AppError(`Formato da data da missão inválido (dd/mm/aaaa)`);
    }

    if (!isValidTimeFormat(questTime)) {
      throw new AppError(`Formato da hora da missão inválido (hh:mm)`);
    }

    const questDateParsed = parseBrazilDateTime(questDate, questTime);
    if (!isValidDate(questDateParsed)) {
      throw new AppError(`Data para missão inválida ${questDateParsed}`);
    }

    const now = requestedAt ?? nowInBrazil();
    if (isBefore(questDateParsed, addMinutes(now, minMinutesIntervalToCreateQuest))) {
      throw new AppError(
        `A data da missão deve ser posterior a ${minMinutesIntervalToCreateQuest} minutos a partir da data de criação`,
      );
    }

    if (isAfter(questDateParsed, addDays(now, 30))) {
      throw new AppError(
        `A data da missão não pode ser superior a 30 dias a partir da data de criação`,
      );
    }

    if (playersAmount < 3 || playersAmount > 20) {
      throw new AppError(`Quantidade de jogadores inválida, deve ser entre 3 e 20`);
    }

    if (playersAmount === 3 && highPriorityPlayers.length > 0) {
      throw new AppError(`Missões com 3 jogadores não podem ter jopgadores prioritários`);
    }

    if (allowedRanks.length === 0) {
      throw new AppError(`É preciso selecionar ao menos um rank para participar da missão`);
    }

    if (!isValidUrl(rules)) {
      throw new AppError(`Link para as regras da missão inválido`);
    }

    if (!isValidUrl(tableUrl)) {
      throw new AppError(`Link para mesa da missão inválido`);
    }

    // Pega o ranking dedicado atual (se existir)
    const currentDedicatedRank = await this.showCurrentDedicatedRankUseCase.execute({
      guildId,
    });

    const quest = await this.questsRepository.create({
      guildId,
      name,
      description,
      questDate: questDateParsed,
      playersAmount,
      rules,
      tags,
      type,
      tableUrl,
      questMaster,
      allowedRanks,
      mandatoryPlayers,
      highPriorityPlayers,
      createdBy,
      dedicatedRankId: currentDedicatedRank?.id,
    });

    await scheduler.runJob(PublishQuestJob.jobName, {
      guildId,
      questId: quest.id,
      removeJobAfterRun: true,
    });

    const runAutoQueueJobDate = subMinutes(questDateParsed, 20);
    if (isAfter(runAutoQueueJobDate, now)) {
      await scheduler.scheduleJob(AutoQuestQueueJob.jobName, runAutoQueueJobDate, {
        guildId,
        questId: quest.id,
        removeJobAfterRun: true,
      });
    }

    const updatedQuest = await this.questsRepository.findById(quest.id);
    return updatedQuest || quest;
  }
}
