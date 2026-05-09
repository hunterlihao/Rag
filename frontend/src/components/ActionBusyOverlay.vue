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
          <div class="flex gap-1">
            <span class="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" />
            <span class="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>
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
