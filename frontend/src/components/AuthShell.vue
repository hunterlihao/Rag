<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: "",
  },
  title: {
    type: String,
    default: "",
  },
  subtitle: {
    type: String,
    default: "",
  },
  switchLabel: {
    type: String,
    default: "",
  },
  switchTo: {
    type: String,
    default: "",
  },
  switchText: {
    type: String,
    default: "",
  },
});
</script>

<template>
  <div class="page-shell auth-page">
    <div class="auth-grid">
      <section class="auth-showcase glass-panel">
        <div class="auth-brand">
          <div class="auth-mark">
            <span></span>
          </div>
          <div>
            <div class="auth-brand__name">RAG Studio</div>
            <div class="auth-brand__meta">知识库问答工作台</div>
          </div>
        </div>

        <div class="auth-showcase__content">
          <p class="auth-eyebrow">{{ eyebrow }}</p>
          <h1 class="auth-title">{{ title }}</h1>
          <p class="auth-subtitle">{{ subtitle }}</p>
        </div>

        <div class="auth-feature-list">
          <div class="auth-feature">
            <strong>统一工作台</strong>
          </div>
          <div class="auth-feature">
            <strong>前后端解耦</strong>
          </div>
        </div>
      </section>

      <section class="auth-card soft-card">
        <div class="auth-card__switch">
          <span class="muted-copy">{{ switchText }}</span>
          <router-link :to="switchTo" class="auth-switch-link">
            {{ switchLabel }}
          </router-link>
        </div>
        <slot />
      </section>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-grid {
  width: min(1200px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(420px, 0.8fr);
  gap: 24px;
}

.auth-showcase {
  position: relative;
  overflow: hidden;
  padding: 38px;
  border-radius: 36px;
  min-height: 720px;
  background:
    radial-gradient(circle at 20% 18%, rgba(122, 177, 255, 0.28), transparent 18%),
    radial-gradient(circle at 82% 22%, rgba(36, 87, 214, 0.2), transparent 18%),
    linear-gradient(160deg, rgba(243, 248, 255, 0.88), rgba(255, 255, 255, 0.68));
}

.auth-brand {
  display: inline-flex;
  align-items: center;
  gap: 16px;
  padding: 12px 18px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.66);
  border: 1px solid rgba(255, 255, 255, 0.7);
}

.auth-mark {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  background: linear-gradient(145deg, #1f56d9, #7cb4ff);
  display: grid;
  place-items: center;
  box-shadow: 0 18px 36px rgba(31, 86, 217, 0.2);
}

.auth-mark span {
  display: block;
  width: 26px;
  height: 26px;
  border: 4px solid #ffffff;
  border-left-color: transparent;
  border-radius: 999px;
  transform: rotate(18deg);
}

.auth-brand__name {
  font-size: 1.1rem;
  font-weight: 800;
}

.auth-brand__meta {
  color: var(--muted);
  font-size: 0.9rem;
}

.auth-showcase__content {
  padding-top: 88px;
  max-width: 620px;
}

.auth-eyebrow {
  display: inline-flex;
  align-items: center;
  padding: 10px 16px;
  border-radius: 999px;
  color: var(--accent);
  background: rgba(36, 87, 214, 0.1);
  font-size: 0.9rem;
  font-weight: 700;
}

.auth-title {
  margin: 18px 0 14px;
  font-size: clamp(2.8rem, 6vw, 4.6rem);
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.auth-subtitle {
  margin: 0;
  max-width: 560px;
  color: var(--muted);
  font-size: 1.05rem;
}

.auth-feature-list {
  display: grid;
  gap: 16px;
  margin-top: 54px;
}

.auth-feature {
  display: grid;
  gap: 8px;
  padding: 20px 22px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.72);
}

.auth-feature strong {
  font-size: 1rem;
}

.auth-feature span {
  color: var(--muted);
  font-size: 0.93rem;
}

.auth-card {
  padding: 30px 30px 26px;
  border-radius: 36px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.auth-card__switch {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 28px;
}

.auth-switch-link {
  color: var(--accent);
  font-weight: 700;
}

@media (max-width: 960px) {
  .auth-grid {
    grid-template-columns: 1fr;
  }

  .auth-showcase {
    min-height: auto;
  }

  .auth-showcase__content {
    padding-top: 56px;
  }
}
</style>
