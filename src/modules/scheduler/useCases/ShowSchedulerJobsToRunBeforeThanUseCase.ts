import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { ISchedulerJobsRepository } from '@/modules/scheduler/repositories/ISchedulerJobsRepository';
import { SchedulerJob } from '@/modules/scheduler/entities/SchedulerJob';

interface IRequest {
  jobName: string;
  beforeThanDate: Date;
}

@injectable()
export class ShowSchedulerJobsToRunBeforeThanUseCase implements IBaseUseCase {
  constructor(
    @inject('SchedulerJobsRepository')
    private schedulerJobsRepository: ISchedulerJobsRepository,
  ) {}

  public async execute({ jobName, beforeThanDate }: IRequest): Promise<SchedulerJob[]> {
    const schedulerJobs = await this.schedulerJobsRepository.findAllByJobNameAndNextRunAtBeforeThan(
      {
        jobName,
        beforeThanDate,
      },
    );

    return schedulerJobs;
  }
}
