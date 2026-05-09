/** Кэш активной партии: IndexedDB + дублирование в localStorage (fallback). */

const DB_NAME = "chess-app";
const STORE = "gameSnapshots";
const LS_KEY = "chess_cached_game_v1";

function idbOpen() {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open(DB_NAME, 1);
    r.onerror = () => reject(r.error);
    r.onupgradeneeded = () => {
      r.result.createObjectStore(STORE);
    };
    r.onsuccess = () => resolve(r.result);
  });
}

/**
 * @param {string} userId
 * @returns {Promise<object|null>} объект партии с сервера или null
 */
export async function loadCachedGame(userId) {
  if (!userId) return null;
  try {
    const db = await idbOpen();
    const rec = await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const q = tx.objectStore(STORE).get(String(userId));
      q.onsuccess = () => resolve(q.result);
      q.onerror = () => reject(q.error);
    });
    db.close();
    if (rec?.game) return rec.game;
  } catch {
    /* use localStorage */
  }
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const o = JSON.parse(raw);
    if (o.userId === String(userId) && o.game) return o.game;
  } catch {
    /* ignore */
  }
  return null;
}

/**
 * @param {string} userId
 * @param {object} game полный снимок (`battle_field`, `state_version`, …)
 */
export async function saveCachedGame(userId, game) {
  if (!userId || game?.id == null) return;
  const key = String(userId);
  const record = { game, userId: key, savedAt: Date.now() };
  try {
    const db = await idbOpen();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(record, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch {
    /* ignore */
  }
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({ userId: key, game }));
  } catch {
    /* quota */
  }
}

/** @param {string} userId */
export async function clearCachedGame(userId) {
  if (!userId) return;
  const key = String(userId);
  try {
    const db = await idbOpen();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).delete(key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch {
    /* ignore */
  }
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) {
      const o = JSON.parse(raw);
      if (o.userId === key) localStorage.removeItem(LS_KEY);
    }
  } catch {
    localStorage.removeItem(LS_KEY);
  }
}
