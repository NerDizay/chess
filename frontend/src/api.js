import {
  clearCachedGame,
  loadCachedGame,
  saveCachedGame,
} from "./gameCache.js";

const jsonHeaders = { "Content-Type": "application/json" };
const API = "/api";

let socket = null;
let reqCounter = 0;
const pending = new Map();
/** @type {Set<(msg: object) => void>} */
const pushSubscribers = new Set();

/** Вызывается при каждом успешном WebSocket `open` (первое подключение и реконнект). */
/** @type {Set<() => void>} */
const wsOpenSubscribers = new Set();

function notifyWsOpen() {
  for (const fn of wsOpenSubscribers) {
    try {
      fn();
    } catch {
      /* ignore */
    }
  }
}

/**
 * Подписка на установление соединения WS (удобно для пересинхронизации после реконнекта).
 * @returns {() => void} отписка
 */
export function subscribeWsConnection(handler) {
  wsOpenSubscribers.add(handler);
  if (typeof WebSocket !== "undefined" && socket && socket.readyState === WebSocket.OPEN) {
    queueMicrotask(() => {
      try {
        handler();
      } catch {
        /* ignore */
      }
    });
  }
  return () => {
    wsOpenSubscribers.delete(handler);
  };
}

/** На следующий `onclose` после `resetWebSocket()` не запускать авто-переподключение */
let suppressReconnectOnClose = false;
let reconnectTimer = null;
let reconnectAttempts = 0;
const MAX_WS_RECONNECT_ATTEMPTS = 12;

function clearReconnectTimer() {
  if (reconnectTimer != null) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function rejectAllPendingDisconnected() {
  const err = wsError({
    detail: "WebSocket disconnected",
    code: 4400,
  });
  for (const [, { reject: rej }] of pending) {
    try {
      rej(err);
    } catch {
      /* ignore */
    }
  }
  pending.clear();
}

function scheduleWsReconnect() {
  clearReconnectTimer();
  if (reconnectAttempts >= MAX_WS_RECONNECT_ATTEMPTS) {
    reconnectAttempts = 0;
    return;
  }
  const delay = Math.min(30_000, 400 * Math.pow(2, reconnectAttempts));
  reconnectAttempts += 1;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWs()
      .then(() => {
        reconnectAttempts = 0;
      })
      .catch(() => {
        scheduleWsReconnect();
      });
  }, delay);
}

function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${API}/ws`;
}

/** После HTTP login/logout cookie меняется — нужен новый handshake WS (HttpOnly не попадает в JS). */
export function resetWebSocket() {
  clearReconnectTimer();
  reconnectAttempts = 0;
  suppressReconnectOnClose = true;
  if (socket) {
    const w = socket;
    socket = null;
    w.close();
  } else {
    suppressReconnectOnClose = false;
  }
}

/**
 * Подписка на server push (`type: "push"`, без поля `id` в ответе на конкретный запрос).
 * @returns {() => void} отписка
 */
export function subscribePush(handler) {
  pushSubscribers.add(handler);
  return () => {
    pushSubscribers.delete(handler);
  };
}

function wsError(err) {
  const e = new Error(err?.detail || "request failed");
  if (err?.code != null) e.code = err.code;
  return e;
}

function connectWs() {
  return new Promise((resolve, reject) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      resolve(socket);
      return;
    }
    const ws = new WebSocket(wsUrl());
    ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (msg.type === "push") {
        for (const fn of pushSubscribers) {
          try {
            fn(msg);
          } catch {
            /* ignore */
          }
        }
        return;
      }
      const mid = msg.id;
      if (mid != null && pending.has(mid)) {
        const { resolve: res, reject: rej } = pending.get(mid);
        pending.delete(mid);
        if (msg.ok) res(msg.data);
        else rej(wsError(msg.error ?? {}));
      }
    };
    ws.onerror = () => reject(new Error("WebSocket connection failed"));
    ws.onclose = () => {
      if (socket === ws) socket = null;
      rejectAllPendingDisconnected();
      const skipReconnect = suppressReconnectOnClose;
      suppressReconnectOnClose = false;
      if (!skipReconnect) {
        scheduleWsReconnect();
      }
    };
    ws.onopen = () => {
      socket = ws;
      reconnectAttempts = 0;
      notifyWsOpen();
      resolve(ws);
    };
  });
}

async function sendWs(action, extra = {}) {
  const ws = await connectWs();
  const id = String(++reqCounter);
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    try {
      ws.send(JSON.stringify({ id, action, ...extra }));
    } catch (err) {
      pending.delete(id);
      reject(err);
    }
  });
}

export async function fetchMe() {
  try {
    return await sendWs("auth.me");
  } catch (e) {
    if (e.code === 401) return null;
    throw e;
  }
}

export async function loginAnonymous(name) {
  const r = await fetch(`${API}/auth/anonymous`, {
    method: "POST",
    credentials: "include",
    headers: jsonHeaders,
    body: JSON.stringify({ name: name?.trim() || null }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    const detail = err.detail;
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail ?? err),
    );
  }
  resetWebSocket();
  return r.json();
}

/** @param {string} [userIdForCache] очистить IndexedDB/localStorage этой партии до сброса cookie */
export async function logout(userIdForCache) {
  if (userIdForCache) await clearCachedGame(String(userIdForCache));
  await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
  resetWebSocket();
}

/** Подбор соперника: `{ status: 'matched', game }` или `{ status: 'waiting', queued_at }`. */
export async function matchmakingPlay() {
  return sendWs("matchmaking.play");
}

export async function matchmakingCancel() {
  return sendWs("matchmaking.cancel");
}

/** Отказаться от партии (противник получит push `games.opponent_left`). */
export async function abandonGame(gameId) {
  return sendWs("games.abandon", { game_id: gameId });
}

export async function createGame() {
  return sendWs("games.create");
}

/** Ход в партии; ответ `{ game }` — полная партия (battle_field целиком), не дельта. Соперник получает push `games.updated`. */
export async function gamesMove(gameId, fromCell, toCell) {
  return sendWs("games.move", {
    game_id: gameId,
    from_cell: fromCell,
    to_cell: toCell,
  });
}

/** Допустимые ходы с клетки `{ targets: string[] }`. */
export async function gamesLegalMoves(gameId, fromCell) {
  return sendWs("games.legal_moves", {
    game_id: gameId,
    from_cell: fromCell,
  });
}

/** GET: текущая парная партия или `{ game: null }`. */
export async function fetchActiveGameHttp() {
  const r = await fetch(`${API}/games/active`, { credentials: "include" });
  if (r.status === 401) return { game: null };
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

/** GET: `{ waiting_count: number }` — сколько других в очереди (без текущего пользователя). */
export async function fetchMatchmakingWaitingHttp() {
  const r = await fetch(`${API}/matchmaking/waiting`, { credentials: "include" });
  if (r.status === 401) return { waiting_count: 0 };
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

/**
 * POST: дельта относительно кэша.
 * `{ status: 'unchanged'|'patch'|'full', ... }`
 */
export async function syncGameHttp({ game_id, client_version, battle_field }) {
  const r = await fetch(`${API}/games/sync`, {
    method: "POST",
    credentials: "include",
    headers: jsonHeaders,
    body: JSON.stringify({
      game_id,
      client_version: client_version ?? null,
      battle_field: battle_field ?? null,
    }),
  });
  if (r.status === 401) throw new Error("Not authenticated");
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

/**
 * Применить ответ `/games/sync` к локальному снимку партии.
 * @param {object|null} cachedGame
 * @param {object} sync
 */
export function mergeSyncIntoGame(cachedGame, sync) {
  if (!sync || sync.status === "full") return sync?.game ?? null;
  if (sync.status === "unchanged") return cachedGame;
  if (sync.status === "patch" && cachedGame) {
    const bf = { ...cachedGame.battle_field };
    for (const [k, v] of Object.entries(sync.battle_field_patch || {})) {
      if (v == null || v === undefined) delete bf[k];
      else bf[k] = v;
    }
    const merged = {
      ...cachedGame,
      battle_field: bf,
      whose_move: sync.whose_move,
      state_version: sync.state_version,
    };
    if (Object.prototype.hasOwnProperty.call(sync, "check_to")) {
      merged.check_to = sync.check_to;
    }
    if (Object.prototype.hasOwnProperty.call(sync, "winner_side")) {
      merged.winner_side = sync.winner_side;
    }
    return merged;
  }
  return cachedGame;
}

/**
 * Восстановление после F5: дельта по кэшу, иначе полная активная партия с сервера.
 * @param {string} userId
 * @returns {Promise<object|null>}
 */
export async function bootstrapActiveGame(userId) {
  if (!userId) return null;
  const cached = await loadCachedGame(userId);
  if (cached?.id != null) {
    try {
      const sync = await syncGameHttp({
        game_id: cached.id,
        client_version:
          cached.state_version !== undefined ? cached.state_version : null,
        battle_field: cached.battle_field ?? null,
      });
      const merged = mergeSyncIntoGame(cached, sync);
      if (merged) {
        await saveCachedGame(userId, merged);
        return merged;
      }
    } catch {
      /* ниже — только активная партия */
    }
  }
  try {
    const { game } = await fetchActiveGameHttp();
    if (!game) {
      await clearCachedGame(userId);
      return null;
    }
    await saveCachedGame(userId, game);
    return game;
  } catch {
    return cached ?? null;
  }
}

export { clearCachedGame, loadCachedGame, saveCachedGame };
