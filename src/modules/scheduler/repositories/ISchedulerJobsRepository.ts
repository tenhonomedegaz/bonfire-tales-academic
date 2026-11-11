import { SchedulerJob } from '@/modules/scheduler/entities/SchedulerJob';
import {
  IFindByJobNameAndUsersIdsDTO,
  IFindAllByJobNameAndNextRunAtBeforeThanDTO,
  IFindQuestPublishJobDTO,
  IFindAllByUsersIdsAndNextRunAtBeforeThanDTO,
  IFindAllByUsersIdsAndNextRunAtAfterThanDTO,
} from '@/modules/scheduler/dto';

export interface ISchedulerJobsRepository {
  deleteById(id: string): Promise<void>;
  findAllByJobNameAndUsersIds(data: IFindByJobNameAndUsersIdsDTO): Promise<SchedulerJob[]>;
  findAllByJobNameAndNextRunAtBeforeThan(
    data: IFindAllByJobNameAndNextRunAtBeforeThanDTO,
  ): Promise<SchedulerJob[]>;
  findAllByUsersIdsAndNextRunAtBeforeThan(
    data: IFindAllByUsersIdsAndNextRunAtBeforeThanDTO,
  ): Promise<SchedulerJob[]>;
  findAllByUsersIdsAndNextRunAtAfterThan(
    data: IFindAllByUsersIdsAndNextRunAtAfterThanDTO,
  ): Promise<SchedulerJob[]>;
  findQuestPublishJob(data: IFindQuestPublishJobDTO): Promise<SchedulerJob | null>;
  findLatestJobsByJobNameAndUserId(data: { jobName: string; userId: string; limit: number }): Promise<SchedulerJob[]>;
  findActiveJobsByJobNameAndUserId(data: { jobName: string; userId: string }): Promise<SchedulerJob[]>;
}
