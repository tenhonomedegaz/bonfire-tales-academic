import { container } from 'tsyringe';

import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { PrismaMembersRepository } from '@/modules/members/repositories/prisma/PrismaMembersRepository';

import { ITransactionsRepository } from '@/modules/transactions/repositories/ITransactionsRepository';
import { PrismaTransactionsRepository } from '@/modules/transactions/repositories/prisma/PrismaTransactionsRepository';

import { ISchedulerJobsRepository } from '@/modules/scheduler/repositories/ISchedulerJobsRepository';
import { PrismaSchedulerJobsRepository } from '@/modules/scheduler/repositories/prisma/PrismaSchedulerJobsRepository';

import { IItemsRepository } from '@/modules/rpg/items/repositories/IItemsRepository';
import { PrismaItemsRepository } from '@/modules/rpg/items/repositories/prisma/PrismaItemsRepository';

import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { PrismaQuestsRepository } from '@/modules/rpg/quests/repositories/prisma/PrismaQuestsRepository';

import { IDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/IDedicatedRankRepository';
import { PrismaDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/prisma/PrismaDedicatedRankRepository';

/**
 * `registerSingleton` loads only one instance of the class, no matter how many
 * times it is instanciated.
 * If we need the objects to be different, use `container.register`
 */

const registeredRepositories = {
  membersRepository: 'MembersRepository',
  transactionsRepository: 'TransactionsRepository',
  schedulerJobsRepository: 'SchedulerJobsRepository',
  itemsRepository: 'ItemsRepository',
  questRepository: 'QuestsRepository',
  dedicatedRankRepository: 'DedicatedRankRepository',
};

function registerRepositories(): void {
  container.registerSingleton<IMembersRepository>(
    registeredRepositories.membersRepository,
    PrismaMembersRepository,
  );

  container.registerSingleton<ITransactionsRepository>(
    registeredRepositories.transactionsRepository,
    PrismaTransactionsRepository,
  );

  container.registerSingleton<ISchedulerJobsRepository>(
    registeredRepositories.schedulerJobsRepository,
    PrismaSchedulerJobsRepository,
  );

  container.registerSingleton<IItemsRepository>(
    registeredRepositories.itemsRepository,
    PrismaItemsRepository,
  );

  container.registerSingleton<IQuestsRepository>(
    registeredRepositories.questRepository,
    PrismaQuestsRepository,
  );

  container.registerSingleton<IDedicatedRankRepository>(
    registeredRepositories.dedicatedRankRepository,
    PrismaDedicatedRankRepository,
  );
}

export { registeredRepositories, registerRepositories };
