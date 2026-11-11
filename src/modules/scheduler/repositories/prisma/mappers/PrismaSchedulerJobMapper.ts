import { SchedulerJob } from '@/modules/scheduler/entities/SchedulerJob';
import { SchedulerJob as PrismaSchedulerJob } from '@prisma/client';

export class PrismaSchedulerJobMapper {
  static toDomain(job: PrismaSchedulerJob): SchedulerJob {
    return {
      id: job.id,
      name: job.name,
      data: job.data as any,
      nextRunAt: job.nextRunAt,
    };
  }

  static toPersistence(job: SchedulerJob): any {
    return {
      id: job.id,
      name: job.name,
      data: job.data,
      nextRunAt: job.nextRunAt,
    };
  }
}
