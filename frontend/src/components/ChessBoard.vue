<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import { gamesLegalMoves } from "../api.js";

const props = defineProps({
  gameId: { type: Number, default: null },
  battleField: { type: Object, default: null },
  myTeam: { type: String, default: null },
  whoseMove: { type: String, default: null },
  /** Чей король под шахом (`check_to` с сервера): `white` | `black` | null */
  checkTo: { type: String, default: null },
  /** Партия окончена (мат) — без ходов */
  gameEnded: { type: Boolean, default: false },
});

const emit = defineEmits(["move", "dismiss-move-error"]);

const RANKS_WHITE_BOTTOM = [8, 7, 6, 5, 4, 3, 2, 1];
const FILES_LTR = ["a", "b", "c", "d", "e", "f", "g", "h"];

const ALL_CELLS = FILES_LTR.flatMap((f) =>
  [1, 2, 3, 4, 5, 6, 7, 8].map((r) => `${f}${r}`),
);

const selectedCell = ref(null);
const legalTargets = ref([]);
let legalReqId = 0;

/** Порог в px: меньше — считаем кликом, больше — начинаем drag */
const DRAG_THRESHOLD_SQ = 10 * 10;

const dragSession = ref(null);
/** После drag подавляем следующий click (иначе сработает handleSquareClick на клетке отпускания) */
const suppressClick = ref(false);
/** Активное перетаскивание: призрак под курсором, исходная клетка скрывает фигуру */
const dragGhost = ref(null);

const rankOrder = computed(() =>
  props.myTeam === "black" ? [1, 2, 3, 4, 5, 6, 7, 8] : RANKS_WHITE_BOTTOM,
);

const fileOrder = computed(() =>
  props.myTeam === "black" ? [...FILES_LTR].reverse() : FILES_LTR,
);

const visualFieldOverride = ref(null);
const flying = ref(null);

let animTimer = null;

/** Только JSON-клон: `battle_field` из Vue — реактивный прокси, `structuredClone` даёт DataCloneError */
function cloneBf(bf) {
  if (bf == null || typeof bf !== "object") return bf;
  try {
    return JSON.parse(JSON.stringify(bf));
  } catch {
    return {};
  }
}

function pieceJson(p) {
  return JSON.stringify(p ?? null);
}

function countChangedCells(oldM, newM) {
  let n = 0;
  for (const c of ALL_CELLS) {
    if (pieceJson(oldM?.[c]) !== pieceJson(newM?.[c])) n++;
  }
  return n;
}

function findMoveEndpoints(oldM, newM) {
  if (!oldM || !newM) return null;
  let from = null;
  let piece = null;
  for (const c of ALL_CELLS) {
    const o = oldM[c] ?? null;
    const n = newM[c] ?? null;
    if (pieceJson(o) === pieceJson(n)) continue;
    if (o && !n) {
      from = c;
      piece = o;
      break;
    }
  }
  if (!from || !piece) return null;
  for (const c of ALL_CELLS) {
    if (c === from) continue;
    const o = oldM[c] ?? null;
    const n = newM[c] ?? null;
    if (pieceJson(n) === pieceJson(piece) && pieceJson(o) !== pieceJson(n))
      return { from, to: c, piece };
  }
  return null;
}

/** Пути к SVG в `public/` (`white_king.svg`, …). */
function pieceSvgSrc(piece) {
  if (!piece?.name || !piece?.color) return null;
  const c = piece.color === "white" ? "white" : "black";
  return `/${c}_${piece.name}.svg`;
}

const MOVE_MS = 420;

/** Звук хода (`public/move.mp3`); вызывается при любом изменении позиции после первого снимка. */
function stripMetaForCompare(bf) {
  const o = cloneBf(bf);
  if (o && typeof o === "object" && "_meta" in o) delete o._meta;
  return o;
}

function playMoveSound() {
  try {
    const a = new Audio("/move.mp3");
    a.volume = 0.05;
    void a.play().catch(() => {
      /* автовоспроизведение может быть заблокировано до жеста пользователя */
    });
  } catch {
    /* ignore */
  }
}

watch(
  () => props.battleField,
  (nv, ov) => {
    if (!nv || ov == null) return;
    const before = JSON.stringify(stripMetaForCompare(ov));
    const after = JSON.stringify(stripMetaForCompare(nv));
    if (before === after) return;
    playMoveSound();
  },
  { deep: true },
);

watch(
  () => [props.battleField, props.whoseMove],
  async ([newBf, newWm], oldVals) => {
    const oldBf = oldVals?.[0];
    const oldWm = oldVals?.[1];

    if (animTimer != null) {
      clearTimeout(animTimer);
      animTimer = null;
    }
    flying.value = null;
    visualFieldOverride.value = null;

    if (!oldBf || !newBf || !props.myTeam) return;

    const opponentJustMoved =
      oldWm != null &&
      newWm != null &&
      oldWm !== props.myTeam &&
      newWm === props.myTeam;

    if (!opponentJustMoved) return;
    if (countChangedCells(oldBf, newBf) !== 2) return;

    const move = findMoveEndpoints(oldBf, newBf);
    if (!move) return;

    visualFieldOverride.value = cloneBf(oldBf);
    await nextTick();

    const elFrom = document.querySelector(`[data-cell="${move.from}"]`);
    const elTo = document.querySelector(`[data-cell="${move.to}"]`);
    if (!elFrom || !elTo) {
      visualFieldOverride.value = null;
      return;
    }

    const r1 = elFrom.getBoundingClientRect();
    const r2 = elTo.getBoundingClientRect();
    const cx1 = r1.left + r1.width / 2;
    const cy1 = r1.top + r1.height / 2;
    const cx2 = r2.left + r2.width / 2;
    const cy2 = r2.top + r2.height / 2;

    flying.value = {
      imgSrc: pieceSvgSrc(move.piece),
      x: cx1,
      y: cy1,
      dx: 0,
      dy: 0,
      active: false,
      hideCell: move.from,
    };

    await nextTick();

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (!flying.value) return;
        flying.value = {
          ...flying.value,
          dx: cx2 - cx1,
          dy: cy2 - cy1,
          active: true,
        };
      });
    });

    animTimer = window.setTimeout(() => {
      animTimer = null;
      flying.value = null;
      visualFieldOverride.value = null;
    }, MOVE_MS + 40);
  },
  { deep: true, flush: "post" },
);

watch(
  () => props.battleField,
  () => {
    selectedCell.value = null;
    legalTargets.value = [];
  },
  { deep: true },
);

function detachDragWindowListeners() {
  window.removeEventListener("pointermove", onDragPointerMove);
  window.removeEventListener("pointerup", onDragPointerUp);
  window.removeEventListener("pointercancel", onDragPointerUp);
}

onUnmounted(() => {
  if (animTimer != null) clearTimeout(animTimer);
  detachDragWindowListeners();
  flying.value = null;
  visualFieldOverride.value = null;
  dragSession.value = null;
  dragGhost.value = null;
});

const fieldMap = computed(() => visualFieldOverride.value ?? props.battleField);

const isMyTurn = computed(
  () =>
    props.myTeam != null &&
    props.whoseMove != null &&
    props.whoseMove === props.myTeam,
);

const canMovePieces = computed(
  () => isMyTurn.value && !props.gameEnded,
);

watch(
  [selectedCell, () => props.gameId, () => canMovePieces.value],
  async ([cell, gid, canMove]) => {
    legalTargets.value = [];
    if (!cell || gid == null || !canMove) return;
    const req = ++legalReqId;
    try {
      const data = await gamesLegalMoves(gid, cell);
      if (req !== legalReqId) return;
      legalTargets.value = Array.isArray(data?.targets) ? data.targets : [];
    } catch {
      if (req !== legalReqId) return;
      legalTargets.value = [];
    }
  },
);

function pieceAt(cell) {
  const m = fieldMap.value;
  if (!m || typeof m !== "object") return null;
  return m[cell] ?? null;
}

function pieceImageSrc(cell) {
  return pieceSvgSrc(pieceAt(cell));
}

function isLightSquare(cell) {
  const fi = FILES_LTR.indexOf(cell[0]);
  const rank = Number.parseInt(cell[1], 10);
  if (fi < 0 || Number.isNaN(rank)) return true;
  return (fi + rank) % 2 === 0;
}

function isLegalTarget(cell) {
  return legalTargets.value.includes(cell);
}

function isLegalCaptureHint(cell) {
  if (!isLegalTarget(cell)) return false;
  const p = pieceAt(cell);
  return p != null && p.color !== props.myTeam;
}

/**
 * Подсветка короля под шахом: свой — красная, соперника (мы поставили шах) — зелёная.
 * @returns {null | 'self' | 'opponent'}
 */
function kingCheckKind(cell) {
  const ct = props.checkTo;
  if (ct == null || ct === "" || props.myTeam == null) return null;
  const p = pieceAt(cell);
  if (p == null || p.name !== "king" || p.color !== ct) return null;
  return ct === props.myTeam ? "self" : "opponent";
}

async function legalTargetsForCell(fromCell) {
  if (props.gameId == null || !fromCell) return [];
  try {
    const data = await gamesLegalMoves(props.gameId, fromCell);
    return Array.isArray(data?.targets) ? data.targets : [];
  } catch {
    return [];
  }
}

function cellUnderPointer(clientX, clientY) {
  const stack = document.elementsFromPoint(clientX, clientY);
  if (!stack) return null;
  for (const el of stack) {
    const sq = el.closest?.("[data-cell]");
    if (!sq) continue;
    const c = sq.getAttribute("data-cell") ?? sq.dataset?.cell;
    if (c) return c;
  }
  return null;
}

async function finalizeDrag(fromCell, clientX, clientY) {
  const toCell = cellUnderPointer(clientX, clientY);
  const targets = await legalTargetsForCell(fromCell);
  if (
    toCell &&
    toCell !== fromCell &&
    targets.includes(toCell)
  ) {
    emit("move", fromCell, toCell);
  }
}

function onDragPointerMove(ev) {
  const s = dragSession.value;
  if (!s || ev.pointerId !== s.pointerId) return;
  const dx = ev.clientX - s.x0;
  const dy = ev.clientY - s.y0;
  if (!s.dragging && dx * dx + dy * dy >= DRAG_THRESHOLD_SQ) {
    dragSession.value = { ...s, dragging: true };
    selectedCell.value = s.from;
    const p = pieceAt(s.from);
    const src = pieceSvgSrc(p);
    if (src) {
      dragGhost.value = {
        from: s.from,
        imgSrc: src,
        x: ev.clientX,
        y: ev.clientY,
      };
    }
  }
  const s2 = dragSession.value;
  if (s2?.dragging && dragGhost.value) {
    dragGhost.value = {
      ...dragGhost.value,
      x: ev.clientX,
      y: ev.clientY,
    };
  }
}

function onDragPointerUp(ev) {
  const s = dragSession.value;
  if (!s || ev.pointerId !== s.pointerId) return;
  detachDragWindowListeners();

  const wasDragging = s.dragging;
  const from = s.from;
  const cx = ev.clientX;
  const cy = ev.clientY;
  dragSession.value = null;

  if (wasDragging) {
    suppressClick.value = true;
    dragGhost.value = null;
    selectedCell.value = null;
    legalTargets.value = [];
    void finalizeDrag(from, cx, cy);
    return;
  }
  dragGhost.value = null;
}

function piecePointerDown(cell, ev) {
  if (!fieldMap.value || !canMovePieces.value || props.myTeam == null) return;
  const piece = pieceAt(cell);
  if (!piece || piece.color !== props.myTeam) return;
  if (dragSession.value) return;
  emit("dismiss-move-error");
  dragSession.value = {
    from: cell,
    pointerId: ev.pointerId,
    x0: ev.clientX,
    y0: ev.clientY,
    dragging: false,
  };
  window.addEventListener("pointermove", onDragPointerMove);
  window.addEventListener("pointerup", onDragPointerUp);
  window.addEventListener("pointercancel", onDragPointerUp);
}

function handleSquareClick(cell) {
  if (suppressClick.value) {
    suppressClick.value = false;
    return;
  }
  if (!fieldMap.value || !canMovePieces.value || props.myTeam == null) return;

  emit("dismiss-move-error");

  const piece = pieceAt(cell);
  const sel = selectedCell.value;

  if (!sel) {
    if (piece && piece.color === props.myTeam) {
      selectedCell.value = cell;
    }
    return;
  }

  if (cell === sel) {
    selectedCell.value = null;
    return;
  }

  if (piece && piece.color === props.myTeam) {
    selectedCell.value = cell;
    return;
  }

  emit("move", sel, cell);
  selectedCell.value = null;
}

function hidePieceOnSquare(cell) {
  if (flying.value?.hideCell === cell) return true;
  if (dragGhost.value?.from === cell) return true;
  return false;
}

</script>

<template>
  <div class="wrap">
    <p v-if="!props.battleField" class="nodata">Нет данных доски с сервера.</p>
    <template v-else>
      <div class="board-wrap" :class="{ 'is-dragging-piece': dragGhost }">
        <!-- Те же 8 колонок, что у .grid — буквы по центру столбцов -->
        <div class="files-row">
          <span class="rank-gutter" />
          <div class="file-cells">
            <span v-for="f in fileOrder" :key="'t' + f" class="file-label">{{ f }}</span>
          </div>
          <span class="rank-gutter" />
        </div>

        <div class="body-row">
          <div class="rank-col">
            <span v-for="r in rankOrder" :key="'l' + r" class="rank-label">{{ r }}</span>
          </div>
          <div class="grid" role="grid" aria-label="Шахматная доска">
            <template v-for="rank in rankOrder" :key="rank">
              <button
                v-for="f in fileOrder"
                :key="f + rank"
                type="button"
                class="sq"
                :data-cell="f + rank"
                :class="{
                  light: isLightSquare(f + rank),
                  dark: !isLightSquare(f + rank),
                  selected: selectedCell === f + rank,
                  canPlay: canMovePieces && props.myTeam != null,
                  'legal-hint': isLegalTarget(f + rank),
                  'legal-capture': isLegalCaptureHint(f + rank),
                  'king-check': kingCheckKind(f + rank) === 'self',
                  'king-check-delivered': kingCheckKind(f + rank) === 'opponent',
                }"
                @pointerdown="piecePointerDown(f + rank, $event)"
                @click="handleSquareClick(f + rank)"
              >
                <img
                  v-if="!hidePieceOnSquare(f + rank) && pieceImageSrc(f + rank)"
                  class="pc"
                  :src="pieceImageSrc(f + rank)"
                  alt=""
                  draggable="false"
                />
              </button>
            </template>
          </div>
          <div class="rank-col">
            <span v-for="r in rankOrder" :key="'r' + r" class="rank-label">{{ r }}</span>
          </div>
        </div>

        <div class="files-row">
          <span class="rank-gutter" />
          <div class="file-cells">
            <span v-for="f in fileOrder" :key="'b' + f" class="file-label">{{ f }}</span>
          </div>
          <span class="rank-gutter" />
        </div>
      </div>

      <Teleport to="body">
        <div
          v-if="flying"
          class="flying-layer"
          :class="{ 'is-active': flying.active }"
          :style="{
            left: `${flying.x}px`,
            top: `${flying.y}px`,
            '--dx': `${flying.dx}px`,
            '--dy': `${flying.dy}px`,
          }"
        >
          <img
            v-if="flying.imgSrc"
            class="flying-pc"
            :src="flying.imgSrc"
            alt=""
            draggable="false"
          />
        </div>
        <div
          v-if="dragGhost"
          class="drag-ghost-layer"
          :style="{ left: `${dragGhost.x}px`, top: `${dragGhost.y}px` }"
        >
          <img
            class="drag-ghost-pc"
            :src="dragGhost.imgSrc"
            alt=""
            draggable="false"
          />
        </div>
      </Teleport>
    </template>
  </div>
</template>

<style scoped>
.wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 100%;
  user-select: none;
  container-type: inline-size;
  container-name: chessboard;
}

.nodata {
  margin: 0;
  padding: 1rem;
  color: #8b93a8;
  font-size: 0.9rem;
}

/*
  Сторона поля 8×8 — `--board-side`; каждая клетка ровно `--cell` = board-side / 8.
*/
.board-wrap.is-dragging-piece {
  cursor: grabbing;
  touch-action: none;
}

.board-wrap.is-dragging-piece .sq.canPlay {
  cursor: grabbing;
}

.board-wrap {
  --rank-w: clamp(0.65rem, 3.5vw, 1.75rem);
  --g: clamp(0.08rem, 0.55vw, 0.25rem);
  --board-side: min(
    calc(
      100vw - 1.25rem - env(safe-area-inset-left, 0px) - env(safe-area-inset-right, 0px) -
        2 * var(--rank-w) - 2 * var(--g)
    ),
    calc(100dvh - 11rem),
    min(560px, 88vmin)
  );
  --cell: calc(var(--board-side) / 8);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--g);
  width: calc(2 * var(--rank-w) + 2 * var(--g) + var(--board-side));
  max-width: 100%;
  margin-inline: auto;
  box-sizing: border-box;
}

@supports (width: 1cqw) {
  .board-wrap {
    --board-side: min(
      calc(100cqw - 2 * var(--rank-w) - 2 * var(--g)),
      calc(100dvh - 11rem),
      min(560px, 88vmin)
    );
    --cell: calc(var(--board-side) / 8);
  }
}

.files-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: var(--g);
  width: calc(2 * var(--rank-w) + 2 * var(--g) + var(--board-side));
  max-width: 100%;
  box-sizing: border-box;
}

.rank-gutter {
  width: var(--rank-w);
  flex: 0 0 var(--rank-w);
}

.file-cells {
  flex: 0 0 var(--board-side);
  width: var(--board-side);
  max-width: 100%;
  display: grid;
  grid-template-columns: repeat(8, var(--cell));
  box-sizing: border-box;
}

.file-label {
  display: flex;
  align-items: center;
  justify-content: center;
  height: clamp(0.85rem, 3.5vw, 1.35rem);
  font-size: clamp(0.62rem, 2.8vw, 0.85rem);
  color: #8b93a8;
  font-weight: 600;
}

.body-row {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: center;
  gap: var(--g);
  width: calc(2 * var(--rank-w) + 2 * var(--g) + var(--board-side));
  max-width: 100%;
  box-sizing: border-box;
}

.rank-col {
  flex: 0 0 var(--rank-w);
  width: var(--rank-w);
  height: var(--board-side);
  max-height: 100%;
  display: grid;
  grid-template-rows: repeat(8, var(--cell));
  box-sizing: border-box;
}

.rank-label {
  display: flex;
  align-items: center;
  justify-content: center;
  height: var(--cell);
  font-size: clamp(0.62rem, 2.8vw, 0.85rem);
  color: #8b93a8;
  font-weight: 600;
}

.grid {
  flex: 0 0 var(--board-side);
  width: var(--board-side);
  height: var(--board-side);
  max-width: 100%;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: repeat(8, var(--cell));
  grid-template-rows: repeat(8, var(--cell));
  border-radius: clamp(2px, 0.8vw, 4px);
  overflow: hidden;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.45),
    inset 0 0 0 1px rgba(0, 0, 0, 0.35);
}

.sq {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0;
  border: none;
  cursor: default;
  width: var(--cell);
  height: var(--cell);
  box-sizing: border-box;
}

.sq.canPlay {
  cursor: pointer;
}

.sq.light {
  background: #e8ecf1;
}

.sq.dark {
  background: #7d9468;
}

.sq.selected {
  z-index: 2;
  box-shadow: inset 0 0 0 clamp(2px, 0.65vw, 3px) rgba(255, 200, 80, 0.85);
}

.sq.king-check {
  z-index: 3;
  animation: king-check-pulse 1.15s ease-in-out infinite;
}

.sq.king-check-delivered {
  z-index: 3;
  animation: king-check-delivered-pulse 1.15s ease-in-out infinite;
}

@keyframes king-check-pulse {
  0%,
  100% {
    box-shadow:
      inset 0 0 0 2px rgba(220, 50, 50, 0.95),
      inset 0 0 14px rgba(255, 70, 70, 0.35);
  }

  50% {
    box-shadow:
      inset 0 0 0 3px rgba(255, 130, 130, 1),
      inset 0 0 22px rgba(255, 100, 100, 0.55);
  }
}

@keyframes king-check-delivered-pulse {
  0%,
  100% {
    box-shadow:
      inset 0 0 0 2px rgba(40, 170, 85, 0.95),
      inset 0 0 14px rgba(80, 220, 120, 0.35);
  }

  50% {
    box-shadow:
      inset 0 0 0 3px rgba(120, 240, 160, 1),
      inset 0 0 22px rgba(90, 230, 140, 0.5);
  }
}

.sq.legal-hint:not(.selected)::before {
  content: "";
  position: absolute;
  width: 32%;
  height: 32%;
  border-radius: 50%;
  pointer-events: none;
  z-index: 1;
}

.sq.light.legal-hint:not(.selected):not(.legal-capture)::before {
  background: rgba(0, 0, 0, 0.22);
}

.sq.dark.legal-hint:not(.selected):not(.legal-capture)::before {
  background: rgba(255, 255, 255, 0.38);
}

.sq.legal-hint.legal-capture:not(.selected)::before {
  width: 88%;
  height: 88%;
  border-radius: clamp(2px, 0.65vw, 4px);
  background: transparent;
  box-shadow: inset 0 0 0 clamp(2px, 0.55vw, 3px) rgba(255, 200, 80, 0.65);
}

.pc {
  width: min(calc(var(--cell) * 0.86), 3.35rem);
  height: min(calc(var(--cell) * 0.86), 3.35rem);
  object-fit: contain;
  pointer-events: none;
  filter:
    drop-shadow(1px 0 0 rgba(0, 0, 0, 0.38))
    drop-shadow(-1px 0 0 rgba(0, 0, 0, 0.38))
    drop-shadow(0 1px 0 rgba(0, 0, 0, 0.38))
    drop-shadow(0 -1px 0 rgba(0, 0, 0, 0.38));
}
</style>

<style>
.flying-layer {
  position: fixed;
  z-index: 9999;
  margin: 0;
  pointer-events: none;
  transform: translate(-50%, -50%);
  transition: none;
}

.flying-layer.is-active {
  transition: transform 0.42s cubic-bezier(0.25, 0.1, 0.25, 1);
  transform: translate(calc(-50% + var(--dx, 0px)), calc(-50% + var(--dy, 0px)));
}

.flying-pc {
  width: clamp(2rem, 12vmin, 3.35rem);
  height: clamp(2rem, 12vmin, 3.35rem);
  object-fit: contain;
  filter:
    drop-shadow(1px 0 0 rgba(0, 0, 0, 0.38))
    drop-shadow(-1px 0 0 rgba(0, 0, 0, 0.38))
    drop-shadow(0 1px 0 rgba(0, 0, 0, 0.38))
    drop-shadow(0 -1px 0 rgba(0, 0, 0, 0.38));
}

.drag-ghost-layer {
  position: fixed;
  z-index: 10000;
  margin: 0;
  pointer-events: none;
  transform: translate(-50%, -50%);
}

.drag-ghost-pc {
  width: clamp(2rem, 12vmin, 3.35rem);
  height: clamp(2rem, 12vmin, 3.35rem);
  object-fit: contain;
  opacity: 0.92;
  filter:
    drop-shadow(1px 0 0 rgba(0, 0, 0, 0.38))
    drop-shadow(-1px 0 0 rgba(0, 0, 0, 0.38))
    drop-shadow(0 1px 0 rgba(0, 0, 0, 0.38))
    drop-shadow(0 -1px 0 rgba(0, 0, 0, 0.38));
}
</style>
