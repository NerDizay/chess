const jsonHeaders = { "Content-Type": "application/json" };
const API = "/api";

let socket = null;
let reqCounter = 0;
const pending = new Map();

function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${API}/ws`;
}

/** После HTTP login/logout cookie меняется — нужен новый handshake WS (HttpOnly не попадает в JS). */
export function resetWebSocket() {
  if (socket) {
    socket.close();
    socket = null;
  }
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
    };
    ws.onopen = () => {
      socket = ws;
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

export async function logout() {
  await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
  resetWebSocket();
}

export async function createGame() {
  return sendWs("games.create");
}
