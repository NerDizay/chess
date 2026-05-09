<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import ChessBoard from "../components/ChessBoard.vue";
import {
  abandonGame,
  bootstrapActiveGame,
  clearCachedGame,
  fetchMatchmakingWaitingHttp,
  fetchMe,
  gamesMove,
  logout,
  matchmakingCancel,
  matchmakingPlay,
  saveCachedGame,
  subscribePush,
  subscribeWsConnection,
} from "../api.js";

const emit = defineEmits(["logged-out"]);

const user = ref(null);
const battleField = ref(null);
const gameInfo = ref(null);
const loading = ref(false);
const error = ref(null);

const waiting = ref(false);
const queuedAt = ref(null);
const elapsedSec = ref(0);
let timerId = null;

const opponentLeftBanner = ref(null);

/** Модалка выхода из партии (крестик у номера партии). */
const showLeaveModal = ref(false);

let unsubPush = () => {};
let unsubWsConn = () => {};

/** Минимальный интервал между полными сверками с сервером (мс). */
const RECONCILE_MIN_MS = 2000;
let lastReconcileAt = 0;

/** Периодический опрос, пока партия на экране (ловим пропущенные push и расхождение кэша). */
let reconcilePollId = null;

/** Очередь подбора: показывать «Есть желающие поиграть». */
const seekersInQueue = ref(false);
const SEEKERS_POLL_MS = 12_000;
let seekersPollId = null;

async function refreshSeekersBanner() {
  try {
    const data = await fetchMatchmakingWaitingHttp();
    const n = data?.waiting_count;
    seekersInQueue.value = typeof n === "number" && n > 0;
  } catch {
    seekersInQueue.value = false;
  }
}

function applyGameSnapshot(g) {
  /** Новый объект, чтобы Vue точно перерисовал доску (не полагаемся на мутации того же ref). */
  const snap = JSON.parse(JSON.stringify(g));
  battleField.value = snap.battle_field;
  gameInfo.value = snap;
}

/** Убрать локальную партию, если на сервере её уже нет. */
function clearLocalGame() {
  battleField.value = null;
  gameInfo.value = null;
  waiting.value = false;
  queuedAt.value = null;
  clearWaitTimer();
  showLeaveModal.value = false;
}

/**
 * Пересинхронизация с HTTP (активная партия + sync по кэшу): после реконнекта WS, вкладки, таймера.
 */
async function reconcileActiveGame() {
  const uid = user.value?.user_id;
  if (!uid) return;
  const now = Date.now();
  if (now - lastReconcileAt < RECONCILE_MIN_MS) return;
  lastReconcileAt = now;
  try {
    const merged = await bootstrapActiveGame(uid);
    if (merged?.id != null) {
      applyGameSnapshot(merged);
      return;
    }
    /** Партия на сервере удалена (напр. соперник вышел), но мат уже был — не сбрасывать доски до кнопки. */
    if (winnerSideNorm.value != null) return;
    if (gameInfo.value?.id != null || battleField.value != null) {
      clearLocalGame();
      await clearCachedGame(uid);
    }
  } catch {
    /* сеть / временный сбой — оставляем текущий UI */
  }
}

const myTeam = computed(() => {
  const g = gameInfo.value;
  const uid = user.value?.user_id;
  if (!g || uid == null || uid === "") return null;
  const sid = String(uid);
  const wid = g.white_user?.id != null ? String(g.white_user.id) : null;
  const bid = g.black_user?.id != null ? String(g.black_user.id) : null;
  if (wid != null && wid === sid) return "white";
  if (bid != null && bid === sid) return "black";
  return null;
});

/** Чей ход — всегда строка white|black (на случай разного типа с бэкенда). */
const whoseMoveNorm = computed(() => {
  const w = gameInfo.value?.whose_move;
  if (w == null || w === "") return null;
  const raw =
    typeof w === "object" && w !== null && "value" in w
      ? /** @type {{ value: string }} */ (w).value
      : w;
  const s = String(raw).toLowerCase();
  return s === "white" || s === "black" ? s : null;
});

/** Над доской: чей ход с точки зрения игрока. */
const turnHeadline = computed(() => {
  if (!gameInfo.value || whoseMoveNorm.value == null || myTeam.value == null) return null;
  return whoseMoveNorm.value === myTeam.value ? "Ваш ход" : "Ход противника";
});

/** Нормализованный `check_to` с сервера: чей король под шахом. */
const checkToNorm = computed(() => {
  const raw = gameInfo.value?.check_to;
  if (raw == null || raw === "") return null;
  const v =
    typeof raw === "object" && raw !== null && "value" in raw
      ? /** @type {{ value: string }} */ (raw).value
      : raw;
  const s = String(v).toLowerCase();
  return s === "white" || s === "black" ? s : null;
});

/** Шах именно нашему королю (предупреждение и красная подсветка). */
const iAmInCheck = computed(() => {
  const team = myTeam.value;
  const ct = checkToNorm.value;
  if (team == null || ct == null) return false;
  return ct === team;
});

/** Мы поставили шах — надпись и зелёная подсветка короля соперника. */
const iDeliveredCheck = computed(() => {
  const team = myTeam.value;
  const ct = checkToNorm.value;
  if (team == null || ct == null) return false;
  return ct !== team;
});

/** Сторона-победитель после мата (`winner_side` с API). */
const winnerSideNorm = computed(() => {
  const raw = gameInfo.value?.winner_side;
  if (raw == null || raw === "") return null;
  const v =
    typeof raw === "object" && raw !== null && "value" in raw
      ? /** @type {{ value: string }} */ (raw).value
      : raw;
  const s = String(v).toLowerCase();
  return s === "white" || s === "black" ? s : null;
});

const iWonByMate = computed(() => {
  const ws = winnerSideNorm.value;
  const team = myTeam.value;
  return ws != null && team != null && ws === team;
});

const iLostByMate = computed(() => {
  const ws = winnerSideNorm.value;
  const team = myTeam.value;
  return ws != null && team != null && ws !== team;
});

const gameEndedMate = computed(() => winnerSideNorm.value != null);

/** Текст кнопки закрытия экрана после мата. */
const mateDismissButtonLabel = computed(() =>
  iWonByMate.value ? "Хорошо" : "Понятно...",
);

function clearWaitTimer() {
  if (timerId != null) {
    clearInterval(timerId);
    timerId = null;
  }
}

function startWaitTimer(fromMs) {
  clearWaitTimer();
  const base = fromMs;
  const tick = () => {
    elapsedSec.value = Math.max(0, Math.floor((Date.now() - base) / 1000));
  };
  tick();
  timerId = setInterval(tick, 1000);
}

function onPush(msg) {
  if (msg.event === "matchmaking.matched" && msg.data?.game) {
    applyGameSnapshot(msg.data.game);
    waiting.value = false;
    queuedAt.value = null;
    clearWaitTimer();
    opponentLeftBanner.value = null;
    void refreshSeekersBanner();
    return;
  }
  if (msg.event === "games.updated" && msg.data?.game) {
    applyGameSnapshot(msg.data.game);
    return;
  }
  if (msg.event === "games.opponent_left") {
    /** После мата оставляем доску и надписи; баннер про выход соперника не показываем. */
    if (winnerSideNorm.value != null) {
      return;
    }
    battleField.value = null;
    gameInfo.value = null;
    waiting.value = false;
    queuedAt.value = null;
    clearWaitTimer();
    showLeaveModal.value = false;
    opponentLeftBanner.value = "Противник вышел из партии.";
    if (user.value?.user_id) void clearCachedGame(user.value.user_id);
  }
}

function onVisibilityChange() {
  if (document.visibilityState === "visible") {
    void reconcileActiveGame();
    void refreshSeekersBanner();
  }
}

function onOnline() {
  void reconcileActiveGame();
  void refreshSeekersBanner();
}

onMounted(async () => {
  try {
    user.value = await fetchMe();
    if (user.value?.user_id) {
      const restored = await bootstrapActiveGame(user.value.user_id);
      if (restored?.id != null) {
        applyGameSnapshot(restored);
      }
    }
  } catch {
    user.value = null;
  }
  /** Не дублировать `reconcileActiveGame` сразу после bootstrap (WS уже открыт из `fetchMe`). */
  lastReconcileAt = Date.now();
  unsubPush = subscribePush(onPush);
  unsubWsConn = subscribeWsConnection(() => {
    void reconcileActiveGame();
    void refreshSeekersBanner();
  });
  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("online", onOnline);
  void refreshSeekersBanner();
  seekersPollId = setInterval(() => void refreshSeekersBanner(), SEEKERS_POLL_MS);
});

watch(gameInfo, (g) => {
  if (reconcilePollId != null) {
    clearInterval(reconcilePollId);
    reconcilePollId = null;
  }
  if (g?.id == null) return;
  reconcilePollId = setInterval(() => {
    void reconcileActiveGame();
  }, 45_000);
});

watch(
  () => [gameInfo.value, battleField.value],
  async ([g, bf]) => {
    const uid = user.value?.user_id;
    if (!uid || g?.id == null) return;
    const payload =
      bf != null ? { ...g, battle_field: bf } : g;
    await saveCachedGame(uid, payload);
  },
  { deep: true },
);

/** После матча в профиле должен быть user_id; без него myTeam=null и доска не реагирует. */
watch(
  gameInfo,
  async (g) => {
    if (!g?.white_user || !g?.black_user) return;
    if (user.value?.user_id) return;
    try {
      const me = await fetchMe();
      if (me) user.value = me;
    } catch {
      /* ignore */
    }
  },
  { flush: "post" },
);

onUnmounted(() => {
  unsubPush();
  unsubWsConn();
  document.removeEventListener("visibilitychange", onVisibilityChange);
  window.removeEventListener("online", onOnline);
  if (reconcilePollId != null) {
    clearInterval(reconcilePollId);
    reconcilePollId = null;
  }
  if (seekersPollId != null) {
    clearInterval(seekersPollId);
    seekersPollId = null;
  }
  clearWaitTimer();
});

watch(waiting, (w) => {
  if (!w) clearWaitTimer();
});

watch(gameInfo, (g) => {
  if (g == null) showLeaveModal.value = false;
});

async function playOnline() {
  error.value = null;
  opponentLeftBanner.value = null;
  loading.value = true;
  try {
    const result = await matchmakingPlay();
    if (result.status === "matched") {
      applyGameSnapshot(result.game);
      waiting.value = false;
      queuedAt.value = null;
    } else if (result.status === "waiting") {
      waiting.value = true;
      const t = Date.parse(result.queued_at);
      queuedAt.value = Number.isFinite(t) ? t : Date.now();
      startWaitTimer(queuedAt.value);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
    void refreshSeekersBanner();
  }
}

function userFacingMoveError(e) {
  const m = e instanceof Error ? e.message : String(e);
  if (/illegal move/i.test(m.trim())) return "Так нельзя";
  return m;
}

async function cancelWaiting() {
  error.value = null;
  loading.value = true;
  try {
    await matchmakingCancel();
    waiting.value = false;
    queuedAt.value = null;
    clearWaitTimer();
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
    void refreshSeekersBanner();
  }
}

async function onBoardMove(fromCell, toCell) {
  if (gameInfo.value?.id == null) return;
  error.value = null;
  loading.value = true;
  try {
    const { game } = await gamesMove(gameInfo.value.id, fromCell, toCell);
    applyGameSnapshot(game);
  } catch (e) {
    error.value = userFacingMoveError(e);
  } finally {
    loading.value = false;
  }
}

async function confirmLeaveGame() {
  if (gameInfo.value?.id == null) return;
  error.value = null;
  loading.value = true;
  try {
    await abandonGame(gameInfo.value.id);
    battleField.value = null;
    gameInfo.value = null;
    showLeaveModal.value = false;
    opponentLeftBanner.value = null;
    if (user.value?.user_id) await clearCachedGame(user.value.user_id);
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

function dismissLeaveModal() {
  showLeaveModal.value = false;
}

async function doLogout() {
  loading.value = true;
  error.value = null;
  try {
    if (gameInfo.value?.id != null) {
      await abandonGame(gameInfo.value.id);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
  await logout(user.value?.user_id);
  battleField.value = null;
  gameInfo.value = null;
  waiting.value = false;
  queuedAt.value = null;
  clearWaitTimer();
  showLeaveModal.value = false;
  emit("logged-out");
}

function formatElapsed(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function dismissMoveError() {
  error.value = null;
}

/** Закрыть экран окончённой партии (мат); по возможности убрать запись на сервере. */
async function dismissFinishedGame() {
  const uid = user.value?.user_id;
  const gid = gameInfo.value?.id;
  error.value = null;
  loading.value = true;
  try {
    if (gid != null) {
      try {
        await abandonGame(gid);
      } catch {
        /* партия уже удалена соперником */
      }
    }
    clearLocalGame();
    opponentLeftBanner.value = null;
    if (uid) await clearCachedGame(String(uid));
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="play">
    <Teleport to="body">
      <div
        v-if="showLeaveModal"
        class="modal-root"
        role="dialog"
        aria-modal="true"
        aria-labelledby="leave-title"
        @click.self="dismissLeaveModal"
      >
        <div class="modal-card">
          <p id="leave-title" class="modal-text">
            Точно хотите покинуть игру?
          </p>
          <div class="modal-actions">
            <button type="button" class="btn modal-absolutely" :disabled="loading" @click="confirmLeaveGame">
              Абсолютно
            </button>
            <button type="button" class="btn modal-no" @click="dismissLeaveModal">
              Нет нет нет!
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <aside class="sidebar">
      <p class="welcome">
        {{ user?.name ?? "Игрок" }}
      </p>
      <button type="button" class="btn ghost" :disabled="loading" @click="doLogout">
        Выйти
      </button>

      <p v-if="seekersInQueue" class="seekers-hint">
        Есть желающие поиграть
      </p>

      <div v-if="gameInfo?.id != null" class="party-row">
        <span class="meta party-label">Партия #{{ gameInfo.id }}</span>
        <button
          type="button"
          class="icon-close"
          title="Покинуть партию"
          aria-label="Покинуть партию"
          :disabled="loading"
          @click="showLeaveModal = true"
        >
          ×
        </button>
      </div>

      <p v-if="gameInfo && myTeam == null" class="meta warn">
        Не удалось сопоставить вас с белыми/чёрными — обновите страницу или войдите снова.
      </p>
      <p v-if="error" class="err">{{ error }}</p>
    </aside>

    <main class="stage">
      <p v-if="opponentLeftBanner" class="banner">{{ opponentLeftBanner }}</p>

      <div v-if="gameInfo && battleField != null" class="in-game">
        <div v-if="gameEndedMate" class="mate-dismiss-row">
          <button
            type="button"
            class="btn mate-dismiss-btn"
            :disabled="loading"
            @click="dismissFinishedGame"
          >
            {{ mateDismissButtonLabel }}
          </button>
        </div>
        <p v-if="iWonByMate" class="status-strip mate-win" aria-live="polite">
          Вы победили!
        </p>
        <p v-else-if="iLostByMate" class="status-strip mate-lose" aria-live="polite">
          Вы проиграли...
        </p>
        <p
          v-else
          class="check-banner"
          :class="{ 'check-banner-delivered': iDeliveredCheck && !iAmInCheck }"
          :style="{ visibility: iAmInCheck || iDeliveredCheck ? 'visible' : 'hidden' }"
          :aria-hidden="!(iAmInCheck || iDeliveredCheck)"
          aria-live="polite"
        >
          Шах
        </p>
        <p v-if="turnHeadline && !gameEndedMate" class="turn-headline">{{ turnHeadline }}</p>
        <ChessBoard
          :game-id="gameInfo?.id ?? null"
          :battle-field="battleField"
          :my-team="myTeam"
          :whose-move="whoseMoveNorm"
          :check-to="checkToNorm"
          :game-ended="gameEndedMate"
          @move="onBoardMove"
          @dismiss-move-error="dismissMoveError"
        />
      </div>

      <div v-else-if="waiting" class="matchmaking">
        <p class="wait-label">Ищем соперника…</p>
        <p class="timer">{{ formatElapsed(elapsedSec) }}</p>
        <button type="button" class="btn ghost wide" :disabled="loading" @click="cancelWaiting">
          Отменить ожидание
        </button>
      </div>

      <div v-else class="idle-center">
        <button type="button" class="btn play-big" :disabled="loading" @click="playOnline">
          Играть
        </button>
      </div>
    </main>
  </div>
</template>

<style scoped>
.play {
  min-height: 100vh;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  background: radial-gradient(ellipse at center, #252b38 0%, #12151c 70%);
}

.sidebar {
  width: 11rem;
  flex-shrink: 0;
  padding: clamp(0.65rem, 3vw, 1.5rem) clamp(0.65rem, 2.5vw, 1rem);
  padding-top: max(clamp(0.65rem, 3vw, 1.5rem), env(safe-area-inset-top, 0px));
  display: flex;
  flex-direction: column;
  gap: clamp(0.45rem, 2vw, 0.75rem);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(20, 24, 32, 0.85);
}

.party-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  margin-top: 0.25rem;
}

.party-label {
  margin: 0;
  flex: 1;
  min-width: 0;
}

.icon-close {
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
  color: #c5cad8;
  font-size: 1.35rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-close:hover:not(:disabled) {
  background: rgba(220, 90, 90, 0.35);
  color: #ffb4b4;
}

.icon-close:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.modal-root {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(8, 10, 14, 0.72);
  backdrop-filter: blur(4px);
}

.modal-card {
  width: 100%;
  max-width: 22rem;
  padding: 1.35rem 1.25rem;
  border-radius: 12px;
  background: #1e2430;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
}

.modal-text {
  margin: 0 0 1.15rem;
  font-size: 1rem;
  color: #e8ecf3;
  text-align: center;
  line-height: 1.45;
}

.modal-actions {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.modal-absolutely {
  background: linear-gradient(180deg, #e03131, #c92a2a);
  color: #fff;
}

.modal-no {
  background: transparent;
  color: #a8b0c4;
  border: 1px solid #353c4d;
}

.welcome {
  margin: 0;
  font-size: clamp(0.78rem, 3.2vw, 0.9rem);
  font-weight: 600;
  color: #e8ecf3;
  word-break: break-word;
}

.seekers-hint {
  margin: 0.35rem 0 0;
  padding: 0;
  font-size: clamp(0.72rem, 3vw, 0.82rem);
  font-weight: 600;
  color: #3ecf6b;
  line-height: 1.35;
}

.btn {
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  border: none;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.play-big {
  padding: clamp(0.85rem, 4vw, 1.25rem) clamp(1.5rem, 8vw, 3rem);
  font-size: clamp(1.05rem, 4.5vw, 1.35rem);
  background: linear-gradient(180deg, #51cf66, #37b24d);
  color: #0d1f12;
  border-radius: clamp(10px, 2vw, 14px);
  box-shadow: 0 8px 28px rgba(81, 207, 102, 0.25);
  max-width: calc(100vw - 2rem);
}

.ghost {
  background: transparent;
  color: #a8b0c4;
  border: 1px solid #353c4d;
}

.wide {
  align-self: stretch;
  text-align: center;
}

.meta {
  font-size: 0.8rem;
  color: #c5cad8;
}

.meta.subtle {
  margin: 0;
  color: #8b93a8;
}

.meta.warn {
  margin: 0.25rem 0 0;
  color: #ffb4b4;
  line-height: 1.35;
}

.check-banner {
  margin: 0 0 0.25rem;
  padding-inline: 0.35rem;
  font-size: clamp(1rem, 4.5vw, 1.25rem);
  font-weight: 800;
  color: #ff4444;
  text-align: center;
  letter-spacing: 0.06em;
  text-shadow: 0 0 12px rgba(255, 68, 68, 0.45);
  max-width: 100%;
}

.check-banner-delivered {
  color: #3ecf6b;
  text-shadow: 0 0 12px rgba(62, 207, 107, 0.5);
}

.status-strip {
  margin: 0 0 0.25rem;
  padding-inline: 0.35rem;
  font-size: clamp(1rem, 4.5vw, 1.25rem);
  font-weight: 800;
  text-align: center;
  letter-spacing: 0.06em;
  max-width: 100%;
}

.mate-win {
  color: #3ecf6b;
  text-shadow: 0 0 12px rgba(62, 207, 107, 0.45);
}

.mate-lose {
  color: #ff4444;
  text-shadow: 0 0 12px rgba(255, 68, 68, 0.45);
}

.mate-dismiss-row {
  display: flex;
  justify-content: center;
  width: 100%;
  margin: 0 0 clamp(0.35rem, 2vw, 0.6rem);
}

.mate-dismiss-btn {
  min-width: clamp(8rem, 42vw, 12rem);
  padding: clamp(0.5rem, 2.5vw, 0.65rem) clamp(1rem, 4vw, 1.5rem);
  font-size: clamp(0.9rem, 3.8vw, 1.05rem);
  background: rgba(55, 62, 78, 0.95);
  color: #e8ecf3;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: clamp(8px, 2vw, 12px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

.mate-dismiss-btn:hover:not(:disabled) {
  background: rgba(68, 76, 94, 0.98);
}

.turn-headline {
  margin: 0 0 clamp(0.5rem, 2vw, 1rem);
  padding-inline: 0.35rem;
  font-size: clamp(0.95rem, 4.2vw, 1.15rem);
  font-weight: 700;
  color: #e8ecf3;
  text-align: center;
  letter-spacing: 0.02em;
  max-width: 100%;
}

.err {
  margin: 0;
  font-size: 0.8rem;
  color: #fa8686;
  line-height: 1.35;
}

.banner {
  position: absolute;
  left: 50%;
  top: 25%;
  transform: translate(-50%, -50%);
  z-index: 2;
  margin: 0;
  padding: 0.65rem 1rem;
  border-radius: 8px;
  background: rgba(255, 180, 80, 0.12);
  border: 1px solid rgba(255, 200, 120, 0.25);
  color: #ffd8a8;
  font-size: 0.9rem;
  max-width: min(28rem, calc(100% - 2rem));
  text-align: center;
  box-sizing: border-box;
}

.stage {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: clamp(0.4rem, 3vw, 1.5rem);
  padding-bottom: max(clamp(0.5rem, 3vw, 1.5rem), env(safe-area-inset-bottom, 0px));
  min-width: 0;
}

.idle-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.matchmaking {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.wait-label {
  margin: 0;
  font-size: 1rem;
  color: #c5cad8;
}

.timer {
  margin: 0;
  font-family: ui-monospace, monospace;
  font-size: clamp(1.35rem, 8vw, 2rem);
  font-weight: 600;
  color: #e8ecf3;
  letter-spacing: 0.06em;
}

.in-game {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 100%;
}

@media (max-width: 640px) {
  .play {
    flex-direction: column;
    min-height: 100dvh;
    min-height: 100vh;
  }

  .sidebar {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    border-right: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .welcome {
    width: 100%;
  }

  .seekers-hint {
    width: 100%;
  }

  .party-row {
    width: 100%;
  }

  .banner {
    position: fixed;
    left: 50%;
    top: max(12%, env(safe-area-inset-top));
    transform: translate(-50%, 0);
    font-size: clamp(0.78rem, 3.2vw, 0.9rem);
  }

  .modal-root {
    padding: clamp(0.5rem, 4vw, 1rem);
    padding-bottom: max(1rem, env(safe-area-inset-bottom));
  }

  .modal-card {
    padding: clamp(1rem, 4vw, 1.35rem);
  }
}

@media (max-width: 360px) {
  .btn {
    padding: 0.5rem 0.55rem;
    font-size: clamp(0.78rem, 3.5vw, 0.9rem);
  }

  .party-label {
    font-size: clamp(0.72rem, 3.2vw, 0.85rem);
  }
}
</style>
