<script setup>
defineProps({
  icon: {
    type: [Object, Function, String],
    default: null,
  },
  title: {
    type: String,
    default: "",
  },
  badgeText: {
    type: String,
    default: "",
  },
  description: {
    type: String,
    default: "",
  },
  tone: {
    type: String,
    default: "primary",
  },
});
</script>

<template>
  <div :class="['dialog-hero-header', `dialog-hero-header--${tone}`]">
    <div v-if="icon" class="dialog-hero-header__icon">
      <el-icon><component :is="icon" /></el-icon>
    </div>
    <div class="dialog-hero-header__copy">
      <div class="dialog-hero-header__title">{{ title }}</div>
      <div v-if="badgeText" class="dialog-hero-header__badge">{{ badgeText }}</div>
      <div v-if="description" class="dialog-hero-header__description">{{ description }}</div>
    </div>
  </div>
</template>

<style scoped>
.dialog-hero-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.dialog-hero-header__icon {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(46, 108, 246, 0.16), rgba(46, 108, 246, 0.08));
  color: var(--accent);
  font-size: 22px;
  flex: none;
}

.dialog-hero-header--danger .dialog-hero-header__icon {
  background: linear-gradient(180deg, rgba(239, 68, 68, 0.16), rgba(239, 68, 68, 0.08));
  color: #cb4343;
}

.dialog-hero-header__copy {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.dialog-hero-header__title {
  font-size: 1.04rem;
  font-weight: 800;
  color: var(--ink);
}

.dialog-hero-header__badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(46, 108, 246, 0.1);
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 700;
}

.dialog-hero-header--danger .dialog-hero-header__badge {
  background: rgba(239, 68, 68, 0.1);
  color: #c23b3b;
}

.dialog-hero-header__description {
  color: var(--muted);
  font-size: 0.84rem;
  line-height: 1.6;
}
</style>
