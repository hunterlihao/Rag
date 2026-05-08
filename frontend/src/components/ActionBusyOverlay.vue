<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  badgeText: { type: String, default: "处理中" },
  title: { type: String, default: "请稍候" },
  description: { type: String, default: "" },
});
</script>

<template>
  <Transition name="busy-fade">
    <div v-if="visible" class="fixed inset-0 z-[1900] flex items-center justify-center bg-white/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-lg border border-zinc-100 px-8 py-6 text-center max-w-sm mx-4">
        <span class="inline-block px-3 py-1 rounded-full bg-zinc-100 text-zinc-500 text-xs font-medium mb-4">{{ badgeText }}</span>
        <div class="w-10 h-10 mx-auto mb-3 rounded-full bg-zinc-100 flex items-center justify-center">
          <svg class="animate-spin w-5 h-5 text-zinc-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
        </div>
        <h3 class="text-sm font-semibold text-zinc-900 mb-1">{{ title }}</h3>
        <p v-if="description" class="text-xs text-zinc-500">{{ description }}</p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.busy-fade-enter-active { transition: opacity 0.18s ease; }
.busy-fade-leave-active { transition: opacity 0.18s ease; }
.busy-fade-enter-from,
.busy-fade-leave-to { opacity: 0; }
</style>
