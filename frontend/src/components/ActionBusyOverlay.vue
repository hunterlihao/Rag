<script setup>
import { Loading } from "@element-plus/icons-vue";

defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  badgeText: {
    type: String,
    default: "处理中",
  },
  title: {
    type: String,
    default: "请稍候",
  },
  description: {
    type: String,
    default: "",
  },
});
</script>

<template>
  <transition name="action-busy-fade">
    <div v-if="visible" class="action-busy-overlay" aria-live="polite" aria-busy="true">
      <div class="action-busy-overlay__card">
        <div class="action-busy-overlay__badge">{{ badgeText }}</div>
        <div class="action-busy-overlay__spinner">
          <el-icon class="is-loading"><Loading /></el-icon>
        </div>
        <strong>{{ title }}</strong>
        <span v-if="description">{{ description }}</span>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.action-busy-overlay {
  position: fixed;
  inset: 0;
  z-index: 1900;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(244, 248, 255, 0.78);
  backdrop-filter: blur(10px);
}

.action-busy-overlay__card {
  width: min(360px, calc(100vw - 40px));
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 28px 24px;
  border-radius: 24px;
  border: 1px solid rgba(31, 74, 160, 0.1);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 22px 60px rgba(31, 64, 128, 0.16);
  text-align: center;
}

.action-busy-overlay__badge {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(46, 108, 246, 0.1);
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 700;
}

.action-busy-overlay__spinner {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(46, 108, 246, 0.08);
  color: var(--accent);
  font-size: 30px;
}

.action-busy-overlay__card strong {
  font-size: 1.05rem;
  color: var(--ink);
}

.action-busy-overlay__card span {
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.65;
}

.action-busy-fade-enter-active,
.action-busy-fade-leave-active {
  transition: opacity 0.18s ease;
}

.action-busy-fade-enter-from,
.action-busy-fade-leave-to {
  opacity: 0;
}
</style>
