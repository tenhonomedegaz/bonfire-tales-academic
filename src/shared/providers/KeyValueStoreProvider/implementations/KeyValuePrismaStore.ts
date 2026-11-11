import { IKeyValueStoreProvider } from '@/shared/providers/KeyValueStoreProvider/models/IKeyValueStoreProvider';
import { prisma } from '@/shared/infra/database/prisma';

export class KeyValuePrismaStore implements IKeyValueStoreProvider {
  // async initialization - kept for compatibility with existing code
  public static async build(): Promise<KeyValuePrismaStore> {
    // Prisma connects automatically on first query, but we can do a dummy query to ensure it's up
    await prisma.$connect();
    return new KeyValuePrismaStore();
  }

  async get(key: string): Promise<string | undefined> {
    const record = await prisma.keyValueStore.findUnique({
      where: { key },
    });

    if (!record) {
      return undefined;
    }
    return record.value as string;
  }

  async set(key: string, value: string): Promise<boolean> {
    const record = await prisma.keyValueStore.upsert({
      where: { key },
      update: { value },
      create: { key, value },
    });

    return !!record;
  }

  async delete(key: string): Promise<boolean> {
    try {
      const record = await prisma.keyValueStore.delete({
        where: { key },
      });
      return !!record;
    } catch {
      return false; // Record to delete does not exist
    }
  }

  async clear(): Promise<void> {
    await prisma.keyValueStore.deleteMany();
  }
}
