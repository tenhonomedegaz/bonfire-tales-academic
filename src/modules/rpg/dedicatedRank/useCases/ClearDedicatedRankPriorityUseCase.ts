import { injectable, inject } from 'tsyringe';
import { addDays } from 'date-fns';
import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { AppError } from '@/shared/errors/AppError';
import { IDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/IDedicatedRankRepository';
import { DedicatedRank } from '@/modules/rpg/dedicatedRank/entities/DedicatedRank';
import { nowInBrazil } from '@/shared/util/dateTime';


type IRequest = {
  guildId: string;
};

@injectable()
export class ClearDedicatedRankPriorityUseCase implements IBaseUseCase {
  constructor(
    @inject('DedicatedRankRepository')
    private dedicatedRankRepository: IDedicatedRankRepository,
  ) {}

  public async execute({ guildId }: IRequest): Promise<DedicatedRank> {
    const currentDedicatedRank = await this.dedicatedRankRepository.findCurrentByGuildId(guildId);

    if (!currentDedicatedRank?.isPriorityLocked) {
      throw new AppError('Não existe prioridade travada no ranque dedicado atual');
    }

    currentDedicatedRank.isPriorityLocked = false;
    currentDedicatedRank.priorityRankName = undefined;
    currentDedicatedRank.validUntil = addDays(nowInBrazil(), 7);
    currentDedicatedRank.updatedAt = nowInBrazil();

    return this.dedicatedRankRepository.update(currentDedicatedRank);
  }
}
