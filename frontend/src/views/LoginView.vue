<script setup>
import { ref } from "vue";
import { loginAnonymous } from "../api.js";

const emit = defineEmits(["logged-in"]);

const name = ref("");
const loading = ref(false);
const error = ref(null);

async function submitAnonymous() {
  error.value = null;
  loading.value = true;
  try {
    await loginAnonymous(name.value);
    emit("logged-in");
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

function googleLogin() {
  window.location.assign("/api/auth/google");
}
</script>

<template>
  <div class="login">
    <div class="card">
      <h1 class="title">Шахматы</h1>
      <p class="subtitle">Войдите, чтобы играть</p>

      <label class="label">
        Имя (необязательно)
        <input
          v-model="name"
          type="text"
          maxlength="30"
          placeholder="Гость"
          autocomplete="username"
          class="input"
          @keydown.enter.prevent="submitAnonymous"
        />
      </label>

      <button
        type="button"
        class="btn primary"
        :disabled="loading"
        @click="submitAnonymous"
      >
        Войти без аккаунта
      </button>

      <div class="divider">или</div>

      <button type="button" class="btn google" disabled @click="googleLogin">
        Войти через Google
      </button>

      <p v-if="error" class="err">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.login {
  min-height: 100dvh;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(0.65rem, 4vw, 1.5rem);
  padding-bottom: max(clamp(0.65rem, 4vw, 1.5rem), env(safe-area-inset-bottom, 0px));
  padding-top: max(clamp(0.65rem, 4vw, 1.5rem), env(safe-area-inset-top, 0px));
  background: radial-gradient(ellipse at top, #2a3142 0%, #151821 55%);
}

.card {
  width: 100%;
  max-width: 22rem;
  padding: clamp(1rem, 5vw, 2rem);
  border-radius: clamp(10px, 2vw, 12px);
  background: #1e2430;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.title {
  margin: 0;
  font-size: clamp(1.35rem, 6vw, 1.75rem);
  font-weight: 650;
  letter-spacing: -0.02em;
  color: #f0f2f7;
}

.subtitle {
  margin: 0.35rem 0 1.5rem;
  color: #8b93a8;
  font-size: 0.95rem;
}

.label {
  display: block;
  font-size: 0.8rem;
  color: #a8b0c4;
  margin-bottom: 1rem;
}

.input {
  display: block;
  width: 100%;
  margin-top: 0.35rem;
  padding: 0.55rem 0.65rem;
  border-radius: 8px;
  border: 1px solid #353c4d;
  background: #151821;
  color: #f0f2f7;
  font-size: 1rem;
  box-sizing: border-box;
}

.input:focus {
  outline: none;
  border-color: #5c7cfa;
}

.btn {
  display: block;
  width: 100%;
  padding: 0.65rem 1rem;
  border-radius: 8px;
  border: none;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.05s;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn:not(:disabled):active {
  transform: scale(0.99);
}

.primary {
  background: linear-gradient(180deg, #5c7cfa, #4c6ef5);
  color: #fff;
}

.google {
  background: #fff;
  color: #1f2937;
}

.divider {
  text-align: center;
  margin: 1rem 0;
  font-size: 0.8rem;
  color: #6b7289;
}

.err {
  margin-top: 1rem;
  color: #fa8686;
  font-size: 0.9rem;
}
</style>
