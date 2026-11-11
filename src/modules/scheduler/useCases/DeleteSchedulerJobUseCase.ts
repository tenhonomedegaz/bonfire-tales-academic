import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { ISchedulerJobsRepository } from '@/modules/scheduler/repositories/ISchedulerJobsRepository';

@injectable()
export class DeleteSchedulerJobUseCase implements IBaseUseCase {
  constructor(
    @inject('SchedulerJobsRepository')
    private schedulerJobsRepository: ISchedulerJobsRepository,
  ) {}

  public async execute(jobId: string): Promise<void> {
    await this.schedulerJobsRepository.deleteById(jobId);
  }
}
