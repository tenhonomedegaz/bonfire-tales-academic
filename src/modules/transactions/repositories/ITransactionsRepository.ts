import { Transaction } from '@/modules/transactions/entities/Transaction';
import {
  ICreateTransactionDTO,
  IFindUnclaimedUserTransactionsDTO,
} from '@/modules/transactions/dtos';

export interface ITransactionsRepository {
  create(data: ICreateTransactionDTO): Promise<Transaction>;
  save(data: Transaction): Promise<Transaction>;
  findAllActive(): Promise<Transaction[]>;
  findUnclaimedUserTransactions(data: IFindUnclaimedUserTransactionsDTO): Promise<Transaction[]>;
  findByTransactionCode(transactionCode: string): Promise<Transaction | null>;
  findAllActiveByEmail(email: string): Promise<Transaction[]>;
}
