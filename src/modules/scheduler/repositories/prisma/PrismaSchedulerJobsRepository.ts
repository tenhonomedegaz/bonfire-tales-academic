import { SchedulerJob } from '@/modules/scheduler/entities/SchedulerJob';
import { ISchedulerJobsRepository } from '@/modules/scheduler/repositories/ISchedulerJobsRepository';
import { PrismaSchedulerJobMapper } from '@/modules/scheduler/repositories/prisma/mappers/PrismaSchedulerJobMapper';
import { prisma } from '@/shared/infra/database/prisma';
import { nowInBrazil } from '@/shared/util/dateTime';

import {
  IFindAllByJobNameAndNextRunAtBeforeThanDTO,
  IFindByJobNameAndUsersIdsDTO,
  IFindQuestPublishJobDTO,
  IFindAllByUsersIdsAndNextRunAtBeforeThanDTO,
  IFindAllByUsersIdsAndNextRunAtAfterThanDTO,
} from '@/modules/scheduler/dto';

export class PrismaSchedulerJobsRepository implements ISchedulerJobsRepository {
  public async deleteById(id: string): Promise<void> {
    await prisma.schedulerJob.delete({
      where: { id },
    });
  }

  public async findAllByJobNameAndUsersIds({
    jobName,
    usersIds,
  }: IFindByJobNameAndUsersIdsDTO): Promise<SchedulerJob[]> {
    const jobs = await prisma.schedulerJob.findMany({
      where: {
        name: jobName,
        nextRunAt: { gte: nowInBrazil() },
      },
    });

    const filtered = jobs.filter(j => {
      const data: any = j.data;
      if (!data?.usersIds) return false;
      const ids = Array.isArray(data.usersIds) ? data.usersIds : [data.usersIds];
      return ids.some((id: string) => usersIds.includes(id));
    });

    return filtered.map(PrismaSchedulerJobMapper.toDomain);
  }

  public async findAllByUsersIdsAndNextRunAtBeforeThan({
    jobName,
    usersIds,
    beforeThanDate,
  }: IFindAllByUsersIdsAndNextRunAtBeforeThanDTO): Promise<SchedulerJob[]> {
    const jobs = await prisma.schedulerJob.findMany({
      where: {
        name: jobName,
        nextRunAt: { lt: beforeThanDate },
      },
    });

    const filtered = jobs.filter(j => {
      const data: any = j.data;
      if (!data?.usersIds) return false;
      const ids = Array.isArray(data.usersIds) ? data.usersIds : [data.usersIds];
      return ids.some((id: string) => usersIds.includes(id));
    });

    return filtered.map(PrismaSchedulerJobMapper.toDomain);
  }

  public async findAllByUsersIdsAndNextRunAtAfterThan({
    jobName,
    usersIds,
    afterThanDate,
  }: IFindAllByUsersIdsAndNextRunAtAfterThanDTO): Promise<SchedulerJob[]> {
    const jobs = await prisma.schedulerJob.findMany({
      where: {
        name: jobName,
        nextRunAt: { gte: afterThanDate },
      },
    });

    const filtered = jobs.filter(j => {
      const data: any = j.data;
      if (!data?.usersIds) return false;
      const ids = Array.isArray(data.usersIds) ? data.usersIds : [data.usersIds];
      return ids.some((id: string) => usersIds.includes(id));
    });

    return filtered.map(PrismaSchedulerJobMapper.toDomain);
  }

  public async findAllByJobNameAndNextRunAtBeforeThan({
    jobName,
    beforeThanDate,
  }: IFindAllByJobNameAndNextRunAtBeforeThanDTO): Promise<SchedulerJob[]> {
    const jobs = await prisma.schedulerJob.findMany({
      where: {
        name: jobName,
        nextRunAt: { lte: beforeThanDate }, 
      },
    });
    // Filter out jobs where nextRunAt might have been mapped to something unexpected, though prisma handles it
    return jobs.map(PrismaSchedulerJobMapper.toDomain);
  }

  public async findQuestPublishJob({
    jobName,
    guildId,
    questId,
  }: IFindQuestPublishJobDTO): Promise<SchedulerJob | null> {
    const jobs = await prisma.schedulerJob.findMany({
      where: {
        name: jobName,
      },
    });

    const job = jobs.find(j => {
      const data: any = j.data;
      return data?.guildId === guildId && data?.questId === questId;
    });

    return job ? PrismaSchedulerJobMapper.toDomain(job) : null;
  }

  public async findLatestJobsByJobNameAndUserId({
    jobName,
    userId,
    limit,
  }: {
    jobName: string;
    userId: string;
    limit: number;
  }): Promise<SchedulerJob[]> {
    const jobs = await prisma.schedulerJob.findMany({
      where: {
        name: jobName,
      },
      orderBy: { id: 'desc' }, 
    });

    const filtered = jobs.filter(j => {
      const data: any = j.data;
      return Array.isArray(data?.usersIds) ? data.usersIds.includes(userId) : data?.usersIds === userId;
    }).slice(0, limit);

    return filtered.map(PrismaSchedulerJobMapper.toDomain);
  }

  public async findActiveJobsByJobNameAndUserId({
    jobName,
    userId,
  }: {
    jobName: string;
    userId: string;
  }): Promise<SchedulerJob[]> {
    const now = nowInBrazil();
    const jobs = await prisma.schedulerJob.findMany({
      where: {
        name: jobName,
      },
      orderBy: { id: 'desc' },
    });
    
    const filtered = jobs.filter(j => {
      const data: any = j.data;
      const isUser = Array.isArray(data?.usersIds) ? data.usersIds.includes(userId) : data?.usersIds === userId;
      if (!isUser) return false;

      const scheduledDateStr = data?.scheduledDate;
      const isFutureScheduled = scheduledDateStr ? new Date(scheduledDateStr) >= now : false;
      return j.nextRunAt >= now || isFutureScheduled;
    });

    return filtered.map(PrismaSchedulerJobMapper.toDomain);
  }
}
