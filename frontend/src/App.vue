<script setup>
import { onMounted, ref } from "vue";
import LoginView from "./views/LoginView.vue";
import PlayView from "./views/PlayView.vue";
import { fetchMe } from "./api.js";

/** Какой экран показать: вход или игра (без vue-router — только представления). */
const view = ref("login");
const booting = ref(true);

onMounted(async () => {
  try {
    const me = await fetchMe();
    view.value = me ? "play" : "login";
  } catch {
    view.value = "login";
  } finally {
    booting.value = false;
  }
});

function onLoggedIn() {
  view.value = "play";
}

function onLoggedOut() {
  view.value = "login";
}
</script>

<template>
  <div v-if="booting" class="boot">Загрузка…</div>
  <LoginView v-else-if="view === 'login'" @logged-in="onLoggedIn" />
  <PlayView v-else @logged-out="onLoggedOut" />
</template>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
}

body {
  font-family:
    system-ui,
    -apple-system,
    "Segoe UI",
    Roboto,
    sans-serif;
  -webkit-font-smoothing: antialiased;
  padding-left: env(safe-area-inset-left, 0);
  padding-right: env(safe-area-inset-right, 0);
}

.boot {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #151821;
  color: #a8b0c4;
  font-size: 0.95rem;
}
</style>
