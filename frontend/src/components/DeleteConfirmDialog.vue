<script setup>
import { computed } from "vue";
import { SwitchButton, WarningFilled } from "@element-plus/icons-vue";

import DialogHeroHeader from "@/components/DialogHeroHeader.vue";

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: "删除确认",
  },
  badgeText: {
    type: String,
    default: "删除后不可恢复",
  },
  tone: {
    type: String,
    default: "danger",
  },
  summary: {
    type: String,
    default: "",
  },
  hint: {
    type: String,
    default: "",
  },
  items: {
    type: Array,
    default: () => [],
  },
  extra: {
    type: String,
    default: "",
  },
  confirmText: {
    type: String,
    default: "确认删除",
  },
  cancelText: {
    type: String,
    default: "取消",
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:modelValue", "confirm"]);
const dialogIcon = computed(() => (props.tone === "primary" ? SwitchButton : WarningFilled));
const confirmButtonType = computed(() => (props.tone === "primary" ? "primary" : "danger"));

function closeDialog() {
  if (props.loading) {
    return;
  }
  emit("update:modelValue", false);
}

function handleConfirm() {
  emit("confirm");
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :class="['delete-confirm-dialog', `delete-confirm-dialog--${tone}`]"
    width="460px"
    :show-close="!loading"
    :close-on-click-modal="!loading"
    :close-on-press-escape="!loading"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <DialogHeroHeader
        :icon="dialogIcon"
        :title="title"
        :badge-text="badgeText"
        :tone="tone"
      />
    </template>

    <div class="delete-confirm-dialog__panel">
      <div v-if="summary" class="delete-confirm-dialog__summary">{{ summary }}</div>
      <div v-if="hint" class="delete-confirm-dialog__hint">{{ hint }}</div>

      <div v-if="items.length" class="delete-confirm-dialog__list">
        <div
          v-for="item in items"
          :key="item.id || item.name || item"
          class="delete-confirm-dialog__list-item"
        >
          {{ item.name || item }}
        </div>
      </div>

      <div v-if="extra" class="delete-confirm-dialog__extra">{{ extra }}</div>
    </div>

    <template #footer>
      <div class="delete-confirm-dialog__footer">
        <el-button :disabled="loading" @click="closeDialog">{{ cancelText }}</el-button>
        <el-button :type="confirmButtonType" :loading="loading" @click="handleConfirm">{{ confirmText }}</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
:deep(.delete-confirm-dialog) {
  width: min(460px, calc(100vw - 32px));
  border-radius: 26px;
  border: 1px solid rgba(31, 74, 160, 0.08);
  box-shadow: 0 30px 72px rgba(31, 64, 128, 0.16);
  overflow: hidden;
}

:deep(.delete-confirm-dialog .el-dialog__header) {
  margin: 0;
  padding: 22px 22px 0;
}

:deep(.delete-confirm-dialog .el-dialog__body) {
  padding: 14px 22px 8px;
}

:deep(.delete-confirm-dialog .el-dialog__footer) {
  padding: 8px 22px 22px;
}

:deep(.delete-confirm-dialog .el-button--danger) {
  border-color: transparent;
  background: linear-gradient(135deg, #d84b4b, #ef6a5b);
}

:deep(.delete-confirm-dialog .el-button--primary) {
  border-color: transparent;
  background: linear-gradient(135deg, #2e6cf6, #4b84ff);
}

.delete-confirm-dialog__panel {
  display: grid;
  gap: 14px;
}

.delete-confirm-dialog__summary {
  font-size: 0.98rem;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.68;
}

.delete-confirm-dialog__hint,
.delete-confirm-dialog__extra {
  color: var(--muted);
  font-size: 0.84rem;
  line-height: 1.68;
}

.delete-confirm-dialog__list {
  display: grid;
  gap: 8px;
}

.delete-confirm-dialog__list-item {
  padding: 11px 12px;
  border-radius: 14px;
  border: 1px solid rgba(31, 74, 160, 0.08);
  background: linear-gradient(180deg, rgba(247, 250, 255, 0.98), rgba(241, 246, 255, 0.94));
  color: var(--ink);
  font-size: 0.84rem;
  line-height: 1.55;
  word-break: break-word;
}

.delete-confirm-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
