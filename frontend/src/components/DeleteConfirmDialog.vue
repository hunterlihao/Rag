<script setup>
import { computed } from "vue";
import { X, AlertTriangle, LogOut, CheckCircle } from "lucide-vue-next";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: "删除确认" },
  badgeText: { type: String, default: "删除后不可恢复" },
  tone: { type: String, default: "danger" },
  summary: { type: String, default: "" },
  hint: { type: String, default: "" },
  items: { type: Array, default: () => [] },
  extra: { type: String, default: "" },
  confirmText: { type: String, default: "确认删除" },
  cancelText: { type: String, default: "取消" },
  loading: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "confirm"]);

const isPrimary = computed(() => props.tone === "primary");
const isSuccess = computed(() => props.tone === "success");

function closeDialog() {
  if (props.loading) return;
  emit("update:modelValue", false);
}

function handleConfirm() {
  emit("confirm");
}
</script>

<template>
  <div v-if="modelValue" class="fixed inset-0 z-[100] flex items-center justify-center">
    <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="closeDialog" />
    <div class="relative bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full mx-4" style="animation: fade-in 0.2s ease-out, slide-up 0.2s ease-out;">
      <button @click="closeDialog" class="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors" :disabled="loading">
        <X class="w-5 h-5" />
      </button>

      <!-- Icon header -->
      <div class="flex items-center gap-3 mb-4">
        <div :class="['w-10 h-10 rounded-full flex items-center justify-center', isSuccess ? 'bg-green-50' : isPrimary ? 'bg-zinc-100' : 'bg-red-50']">
          <CheckCircle v-if="isSuccess" class="w-5 h-5 text-green-500" />
          <LogOut v-else-if="isPrimary" class="w-5 h-5 text-zinc-500" />
          <AlertTriangle v-else class="w-5 h-5 text-red-500" />
        </div>
        <div>
          <h3 class="text-lg font-semibold text-zinc-900">{{ title }}</h3>
          <span :class="['inline-block px-2 py-0.5 rounded-full text-xs font-medium mt-0.5', isSuccess ? 'bg-green-50 text-green-600' : isPrimary ? 'bg-zinc-100 text-zinc-600' : 'bg-red-50 text-red-600']">{{ badgeText }}</span>
        </div>
      </div>

      <!-- Summary -->
      <p v-if="summary" class="text-sm text-zinc-600 mb-3">{{ summary }}</p>

      <!-- Hint -->
      <p v-if="hint" class="text-xs text-zinc-400 mb-4">{{ hint }}</p>

      <!-- Items list -->
      <div v-if="items.length" class="space-y-1.5 mb-4">
        <div v-for="(item, i) in items" :key="i" class="px-3 py-2 bg-zinc-50 border border-zinc-100 rounded-lg text-sm text-zinc-700 truncate">
          {{ item.name || item.title || item }}
        </div>
      </div>

      <!-- Extra -->
      <p v-if="extra" class="text-xs text-zinc-400 mb-4">{{ extra }}</p>

      <!-- Actions -->
      <div class="flex gap-3">
        <button v-if="!isSuccess" @click="closeDialog" :disabled="loading" class="flex-1 px-4 py-2.5 border border-zinc-200 text-zinc-900 rounded-xl text-sm font-medium hover:bg-zinc-50 transition-colors disabled:opacity-50">
          {{ cancelText }}
        </button>
        <button @click="handleConfirm" :disabled="loading" :class="['flex-1 px-4 py-2.5 text-white rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-70', isSuccess ? 'bg-green-500 hover:bg-green-600' : isPrimary ? 'bg-zinc-900 hover:bg-zinc-800' : 'bg-red-500 hover:bg-red-600']">
          <svg v-if="loading" class="animate-spin w-4 h-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
          {{ loading ? '处理中...' : confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>
