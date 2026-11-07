/** Matches @tldraw/editor LocalIndexedDb store id (TLDRAW_DOCUMENT_v2 + persistenceKey). */
export function tldrawDocumentDbName(persistenceKey: string): string {
  return `TLDRAW_DOCUMENT_v2${persistenceKey}`;
}

export function deleteTldrawDocument(persistenceKey: string): Promise<void> {
  const name = tldrawDocumentDbName(persistenceKey);
  return new Promise((resolve, reject) => {
    const request = indexedDB.deleteDatabase(name);
    request.onerror = () => reject(request.error ?? new Error(`Could not delete ${name}`));
    request.onblocked = () => resolve();
    request.onsuccess = () => resolve();
  });
}

export async function resetCanvasPersistence(keys: string[]): Promise<void> {
  for (const key of keys) {
    try {
      await deleteTldrawDocument(key);
    } catch {
      // Ignore missing DB.
    }
  }
}
