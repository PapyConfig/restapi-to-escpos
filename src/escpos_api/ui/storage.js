// Browser storage, every access guarded: private windows or blocked storage must not break the UI.

const PREFIX = "escpos-ui:";
export const HISTORY_MAX = 30;
export const HISTORY_MAX_BYTES = 400_000;

export function makeStore(backend) {
  const read = (key, fallback) => {
    try {
      const raw = backend?.getItem(PREFIX + key);
      return raw === null || raw === undefined ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  };
  const write = (key, value) => {
    try {
      backend?.setItem(PREFIX + key, JSON.stringify(value));
      return true;
    } catch {
      return false;
    }
  };
  const remove = (key) => {
    try {
      backend?.removeItem(PREFIX + key);
    } catch {
      /* ignore */
    }
  };
  return { read, write, remove };
}

/** Strip image data from a job that is too large to keep in history. */
export function compactJob(job) {
  if (JSON.stringify(job).length <= HISTORY_MAX_BYTES) return job;
  const commands = job.commands.filter((c) => c.type !== "image");
  return { ...job, commands, imagesRemoved: true };
}

export function addHistory(history, entry) {
  const next = [{ ...entry, job: compactJob(entry.job) }, ...history];
  return next.slice(0, HISTORY_MAX);
}

export const EXPORT_VERSION = 1;

export function exportTemplates(templates) {
  return JSON.stringify({ version: EXPORT_VERSION, templates }, null, 2);
}

/** Parse an export file; returns valid templates only (name + non-empty blocks). */
export function importTemplates(text) {
  const data = JSON.parse(text);
  if (!data || data.version !== EXPORT_VERSION || !Array.isArray(data.templates)) {
    throw new Error("Fichier non reconnu : ce n'est pas un export de modèles.");
  }
  return data.templates
    .filter((t) => t && typeof t.name === "string" && Array.isArray(t.blocks) && t.blocks.length)
    .filter((t) => t.blocks.every((b) => b && typeof b.type === "string"))
    .map((t) => ({ id: String(t.id ?? `u${Date.now()}`), name: t.name.slice(0, 60), blocks: t.blocks, createdAt: t.createdAt ?? new Date().toISOString() }));
}
