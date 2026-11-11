import { injectable, inject } from 'tsyringe';
import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { AppError } from '@/shared/errors/AppError';
import { IDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/IDedicatedRankRepository';
import { DedicatedRank } from '@/modules/rpg/dedicatedRank/entities/DedicatedRank';

type IRequest = {
  guildId: string;
};

@injectable()
export class ShowCurrentDedicatedRankUseCase implements IBaseUseCase {
  constructor(
    @inject('DedicatedRankRepository')
    private dedicatedRankRepository: IDedicatedRankRepository,
  ) {}

  public async execute({ guildId }: IRequest): Promise<DedicatedRank | null> {
    const dedicatedRank = await this.dedicatedRankRepository.findCurrentByGuildId(guildId);
    return dedicatedRank;
  }
}
