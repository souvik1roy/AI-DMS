import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { del, get, set } from "idb-keyval";

import type { Query } from "@tanstack/react-query";

// Tiny async-storage adapter on top of idb-keyval (IndexedDB).
const idbStorage = {
  getItem: (key: string) => get(key).then((v) => (v == null ? null : (v as string))),
  setItem: (key: string, value: string) => set(key, value).then(() => undefined),
  removeItem: (key: string) => del(key),
};

export const persister = createAsyncStoragePersister({
  storage: idbStorage,
  key: "organiseai.query-cache.v1",
  // Throttle dehydration so rapid mutations don't slam IndexedDB.
  throttleTime: 1_000,
});

// Persist most read queries; skip the live-progress job query — it has its own
// 800 ms refetch loop and persisting in-flight statuses would render stale on relaunch.
export function shouldDehydrateQuery(query: Query): boolean {
  return query.queryKey[0] !== "job" && query.queryKey[0] !== "recent-log";
}
