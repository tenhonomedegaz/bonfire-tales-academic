export interface IKeyValueStoreProvider<T = any> {
  get: (key: string) => Promise<T | undefined>;

  set: (key: string, value: T) => Promise<boolean>;

  delete(key: string): Promise<boolean>;

  clear(): Promise<void>;
}
