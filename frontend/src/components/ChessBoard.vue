<script setup>
import { computed } from "vue";

const props = defineProps({
  battleField: { type: Object, default: null },
});

/** Начальная позиция (как на бэкенде), если партия ещё не создана */
const DEFAULT_PLACEMENT = [
  ["a1", "rook", "white"],
  ["b1", "knight", "white"],
  ["c1", "bishop", "white"],
  ["d1", "queen", "white"],
  ["e1", "king", "white"],
  ["f1", "bishop", "white"],
  ["g1", "knight", "white"],
  ["h1", "rook", "white"],
  ["a8", "rook", "black"],
  ["b8", "knight", "black"],
  ["c8", "bishop", "black"],
  ["d8", "queen", "black"],
  ["e8", "king", "black"],
  ["f8", "bishop", "black"],
  ["g8", "knight", "black"],
  ["h8", "rook", "black"],
  ..."abcdefgh".split("").map((f) => [`${f}2`, "pawn", "white"]),
  ..."abcdefgh".split("").map((f) => [`${f}7`, "pawn", "black"]),
];

function buildDefaultField() {
  const out = {};
  for (const [cell, name, color] of DEFAULT_PLACEMENT) {
    out[cell] = { name, color };
  }
  return out;
}

const SYMBOLS = {
  white: {
    king: "\u2654",
    queen: "\u2655",
    rook: "\u2656",
    bishop: "\u2657",
    knight: "\u2658",
    pawn: "\u2659",
  },
  black: {
    king: "\u265a",
    queen: "\u265b",
    rook: "\u265c",
    bishop: "\u265d",
    knight: "\u265e",
    pawn: "\u265f",
  },
};

const ranks = [8, 7, 6, 5, 4, 3, 2, 1];
const files = ["a", "b", "c", "d", "e", "f", "g", "h"];

const fieldMap = computed(() => props.battleField ?? buildDefaultField());

function pieceGlyph(cell) {
  const piece = fieldMap.value[cell];
  if (!piece) return "";
  const team = piece.color === "white" ? "white" : "black";
  const key = piece.name;
  return SYMBOLS[team][key] ?? "?";
}

function isLightSquare(fileIdx, rank) {
  return (fileIdx + rank) % 2 === 0;
}
</script>

<template>
  <div class="wrap">
    <div class="files-top">
      <span class="corner" />
      <span v-for="(f, i) in files" :key="f" class="file-label">{{ f }}</span>
    </div>
    <div class="mid">
      <div class="ranks-left">
        <span v-for="r in ranks" :key="r" class="rank-label">{{ r }}</span>
      </div>
      <div class="grid" role="grid" aria-label="Шахматная доска">
        <template v-for="rank in ranks" :key="rank">
          <div
            v-for="(f, fi) in files"
            :key="f + rank"
            class="sq"
            :class="{ light: isLightSquare(fi, rank), dark: !isLightSquare(fi, rank) }"
          >
            <span class="pc">{{ pieceGlyph(f + rank) }}</span>
          </div>
        </template>
      </div>
      <div class="ranks-right">
        <span v-for="r in ranks" :key="'r' + r" class="rank-label">{{ r }}</span>
      </div>
    </div>
    <div class="files-bottom">
      <span class="corner" />
      <span v-for="f in files" :key="'b' + f" class="file-label">{{ f }}</span>
    </div>
  </div>
</template>

<style scoped>
.wrap {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  user-select: none;
}

.mid {
  display: flex;
  align-items: stretch;
  gap: 0.25rem;
}

.files-top,
.files-bottom {
  display: flex;
  width: 100%;
  padding: 0 1.1rem;
  box-sizing: border-box;
}

.corner {
  width: 1rem;
}

.file-label {
  flex: 1;
  text-align: center;
  font-size: 0.7rem;
  color: #8b93a8;
  font-weight: 600;
}

.ranks-left,
.ranks-right {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  width: 1rem;
}

.rank-label {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  color: #8b93a8;
  font-weight: 600;
}

.grid {
  display: grid;
  grid-template-columns: repeat(8, minmax(2.2rem, 4.5vmin));
  grid-template-rows: repeat(8, minmax(2.2rem, 4.5vmin));
  border-radius: 4px;
  overflow: hidden;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.45),
    inset 0 0 0 1px rgba(0, 0, 0, 0.35);
}

.sq {
  display: flex;
  align-items: center;
  justify-content: center;
}

.sq.light {
  background: #e8ecf1;
}

.sq.dark {
  background: #7d9468;
}

.pc {
  font-size: clamp(1.1rem, 3.6vmin, 1.75rem);
  line-height: 1;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
}
</style>
