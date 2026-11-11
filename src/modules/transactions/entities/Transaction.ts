export interface Transaction {
  id: string;
  transactionCode: string;
  transactionSource: string;
  paymentDate: Date;
  expirationDate: Date;
  subscriptionPlan: string;
  subscriptionPeriod: string;
  subscriptionReference: string;
  status: number;
  grossAmount: number;
  netAmount: number;
  name: string | null;
  email: string;
  comments: string | null;
  claimed: boolean;
  claimedAt: Date | undefined;
  createdAt: Date;
  updatedAt: Date;
}
