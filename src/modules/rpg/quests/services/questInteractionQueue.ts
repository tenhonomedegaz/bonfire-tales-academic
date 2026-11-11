const questQueues = new Map<string, Promise<unknown>>();

export async function runQuestInteractionQueued<T>(
  questId: string,
  task: () => Promise<T>,
): Promise<T> {
  const previous = questQueues.get(questId) ?? Promise.resolve();

  let release!: () => void;
  const current = new Promise<void>((resolve) => {
    release = resolve;
  });

  const queued = previous.then(() => current, () => current);
  questQueues.set(questId, queued);

  await previous.catch(() => undefined);

  try {
    return await task();
  } finally {
    release();
    if (questQueues.get(questId) === queued) {
      questQueues.delete(questId);
    }
  }
}
