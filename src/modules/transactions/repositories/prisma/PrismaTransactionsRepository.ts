import { startOfDay } from 'date-fns';

import { Transaction } from '@/modules/transactions/entities/Transaction';
import { ITransactionsRepository } from '@/modules/transactions/repositories/ITransactionsRepository';
import { PrismaTransactionMapper } from '@/modules/transactions/repositories/prisma/mappers/PrismaTransactionMapper';
import {
  ICreateTransactionDTO,
  IFindUnclaimedUserTransactionsDTO,
} from '@/modules/transactions/dtos';
import { prisma } from '@/shared/infra/database/prisma';
import { nowInBrazil } from '@/shared/util/dateTime';

export class PrismaTransactionsRepository implements ITransactionsRepository {
  public async create(data: ICreateTransactionDTO): Promise<Transaction> {
    const transaction = await prisma.transaction.create({
      data: {
        ...data,
      },
    });
    return PrismaTransactionMapper.toDomain(transaction);
  }

  public async save(data: Transaction): Promise<Transaction> {
    const raw = PrismaTransactionMapper.toPersistence(data);
    const { id, ...updateData } = raw;

    const transaction = await prisma.transaction.update({
      where: { id },
      data: updateData,
    });

    return PrismaTransactionMapper.toDomain(transaction);
  }

  public async findAllActive(): Promise<Transaction[]> {
    const today = startOfDay(nowInBrazil());
    const transactions = await prisma.transaction.findMany({
      where: {
        expirationDate: { gte: today },
        subscriptionPlan: { startsWith: 'colaborador-' },
        status: 1,
      },
    });
    return transactions.map(PrismaTransactionMapper.toDomain);
  }

  public async findAllActiveByEmail(email: string): Promise<Transaction[]> {
    const today = startOfDay(nowInBrazil());
    const transactions = await prisma.transaction.findMany({
      where: {
        email,
        expirationDate: { gte: today },
        subscriptionPlan: { startsWith: 'colaborador-' },
        status: 1,
      },
    });
    return transactions.map(PrismaTransactionMapper.toDomain);
  }

  public async findUnclaimedUserTransactions({
    email,
  }: IFindUnclaimedUserTransactionsDTO): Promise<Transaction[]> {
    const transactions = await prisma.transaction.findMany({
      where: { email, claimed: false },
    });
    return transactions.map(PrismaTransactionMapper.toDomain);
  }

  public async findByTransactionCode(transactionCode: string): Promise<Transaction | null> {
    const transaction = await prisma.transaction.findUnique({
      where: { transactionCode },
    });
    return transaction ? PrismaTransactionMapper.toDomain(transaction) : null;
  }
}
