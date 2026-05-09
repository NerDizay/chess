<script setup>
import { onMounted, ref } from "vue";
import ChessBoard from "../components/ChessBoard.vue";
import { createGame, fetchMe, logout } from "../api.js";

const emit = defineEmits(["logged-out"]);

const user = ref(null);
const battleField = ref(null);
const gameInfo = ref(null);
const loading = ref(false);
const error = ref(null);

onMounted(async () => {
  try {
    user.value = await fetchMe();
  } catch {
    user.value = null;
  }
});

async function startGame() {
  error.value = null;
  loading.value = true;
  try {
    const game = await createGame();
    battleField.value = game.battle_field;
    gameInfo.value = game;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

async function doLogout() {
  await logout();
  battleField.value = null;
  gameInfo.value = null;
  emit("logged-out");
}
</script>

<template>
  <div class="play">
    <aside class="sidebar">
      <p class="welcome">
        {{ user?.name ?? "Игрок" }}
      </p>
      <button type="button" class="btn play-btn" :disabled="loading" @click="startGame">
        Играть
      </button>
      <button type="button" class="btn ghost" :disabled="loading" @click="doLogout">
        Выйти
      </button>
      <p v-if="gameInfo?.id != null" class="meta">Партия #{{ gameInfo.id }}</p>
      <p v-if="gameInfo?.whose_move" class="meta subtle">
        Ход: {{ gameInfo.whose_move === "white" ? "белые" : "чёрные" }}
      </p>
      <p v-if="error" class="err">{{ error }}</p>
    </aside>

    <main class="stage">
      <ChessBoard :battle-field="battleField" />
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
  padding: 1.5rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(20, 24, 32, 0.85);
}

.welcome {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: #e8ecf3;
  word-break: break-word;
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

.play-btn {
  background: linear-gradient(180deg, #51cf66, #37b24d);
  color: #0d1f12;
}

.ghost {
  background: transparent;
  color: #a8b0c4;
  border: 1px solid #353c4d;
}

.meta {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: #c5cad8;
}

.meta.subtle {
  color: #8b93a8;
}

.err {
  margin: 0;
  font-size: 0.8rem;
  color: #fa8686;
  line-height: 1.35;
}

.stage {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  min-width: 0;
}

@media (max-width: 640px) {
  .play {
    flex-direction: column;
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
}
</style>
