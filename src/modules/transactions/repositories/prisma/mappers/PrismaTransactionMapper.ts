import { Transaction } from '@/modules/transactions/entities/Transaction';
import { Transaction as PrismaTransaction } from '@prisma/client';

export class PrismaTransactionMapper {
  static toDomain(transaction: PrismaTransaction): Transaction {
    return {
      id: transaction.id,
      transactionCode: transaction.transactionCode,
      transactionSource: transaction.transactionSource ?? '',
      paymentDate: transaction.paymentDate,
      expirationDate: transaction.expirationDate,
      subscriptionPlan: transaction.subscriptionPlan,
      subscriptionPeriod: transaction.subscriptionPeriod,
      subscriptionReference: transaction.subscriptionReference ?? '-',
      status: transaction.status,
      grossAmount: transaction.grossAmount,
      netAmount: transaction.netAmount,
      name: transaction.name,
      email: transaction.email,
      comments: transaction.comments,
      claimed: transaction.claimed,
      claimedAt: transaction.claimedAt ?? undefined,
      createdAt: transaction.createdAt,
      updatedAt: transaction.updatedAt,
    };
  }

  static toPersistence(transaction: Transaction): any {
    return {
      id: transaction.id,
      transactionCode: transaction.transactionCode,
      transactionSource: transaction.transactionSource,
      paymentDate: transaction.paymentDate,
      expirationDate: transaction.expirationDate,
      subscriptionPlan: transaction.subscriptionPlan,
      subscriptionPeriod: transaction.subscriptionPeriod,
      subscriptionReference: transaction.subscriptionReference,
      status: transaction.status,
      grossAmount: transaction.grossAmount,
      netAmount: transaction.netAmount,
      name: transaction.name,
      email: transaction.email,
      comments: transaction.comments,
      claimed: transaction.claimed,
      claimedAt: transaction.claimedAt,
      createdAt: transaction.createdAt,
      updatedAt: transaction.updatedAt,
    };
  }
}
