import { prisma } from '@/shared/infra/database/prisma';
import { PrismaTransactionsRepository } from '@/modules/transactions/repositories/prisma/PrismaTransactionsRepository';

jest.mock('@/shared/infra/database/prisma', () => ({
  prisma: { transaction: { findMany: jest.fn().mockResolvedValue([]) } },
}));

describe('shared Colab subscription eligibility', () => {
  it('limits both bot subscription reads to paid, active Colab transactions', async () => {
    const repository = new PrismaTransactionsRepository();

    await repository.findAllActive();
    await repository.findAllActiveByEmail('member@example.test');

    const findMany = prisma.transaction.findMany as jest.Mock;
    expect(findMany).toHaveBeenCalledTimes(2);
    for (const [call] of findMany.mock.calls) {
      expect(call.where).toEqual(expect.objectContaining({
        status: 1,
        subscriptionPlan: { startsWith: 'colaborador-' },
        expirationDate: { gte: expect.any(Date) },
      }));
    }
    expect(findMany.mock.calls[1][0].where.email).toBe('member@example.test');
  });
});
