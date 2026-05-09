<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { ArrowUp, Database, Sparkles, Square, Copy, Check, ChevronDown, FolderOpen, ArrowRight, StopCircle, Download } from "lucide-vue-next";
import { renderMarkdown } from "@/services/markdown";
import { exportSession, exportSessionAsync, downloadExport, downloadFile, addUploadWsListener, removeUploadWsListener } from "@/services/workspace";

const props = defineProps({
  session: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  prompt: { type: String, default: "" },
  providerLabel: { type: String, default: "" },
  suggestions: { type: Array, default: () => [] },
  welcomeMessage: { type: String, default: "" },
  sendShortcut: { type: String, default: "enter" },
  showKnowledgeTips: { type: Boolean, default: true },
  answerMode: { type: String, default: "auto" },
  chatModelId: { type: String, default: "" },
  chatModelOptions: { type: Array, default: () => [] },
});

const emit = defineEmits([
  "update:prompt", "update:answer-mode", "update:chat-model",
  "submit", "stop", "choose-suggestion", "open-knowledge",
]);

const messagePaneRef = ref(null);
const showModelMenu = ref(false);
const showModeMenu = ref(false);
const copiedMsgId = ref(null);
const exporting = ref(false);

const answerModeOptions = [
  { label: "自动", value: "auto", desc: "自动判断是否需要检索知识库" },
  { label: "知识库", value: "knowledge", desc: "只根据知识库资料回答" },
  { label: "聊天", value: "chat", desc: "不使用知识库，自由对话" },
];

const showHero = computed(() => !props.session.messages || props.session.messages.length === 0);
const renderedMessages = computed(() => showHero.value ? [] : props.session.messages);

const messageScrollSignature = computed(() =>
  (props.session.messages || []).map((m) => `${m.id || ""}:${String(m.content || "").length}:${m.sources?.length || 0}`).join("|")
);

const hasStreamingAssistant = computed(() => {
  const msgs = renderedMessages.value;
  const last = msgs[msgs.length - 1];
  return props.busy && last?.role === "assistant" && String(last.id || "").startsWith("local-assistant-");
});

const showTyping = computed(() => props.busy && !hasStreamingAssistant.value);

const sendShortcutLabel = computed(() =>
  props.sendShortcut === "ctrl-enter" ? "Ctrl+Enter 发送" : "Enter 发送"
);

const currentModelLabel = computed(() => {
  const found = props.chatModelOptions.find((m) => m.id === props.chatModelId);
  return found?.label || "默认模型";
});

const currentModelProvider = computed(() => {
  const found = props.chatModelOptions.find((m) => m.id === props.chatModelId);
  return found?.provider_label || props.providerLabel;
});

const currentModeLabel = computed(() => {
  return answerModeOptions.find((m) => m.value === props.answerMode)?.label || "自动";
});

const typingCopy = computed(() => {
  if (props.answerMode === "chat") return "正在组织回答...";
  if (props.answerMode === "knowledge") return "正在检索知识库并组织回答...";
  return "正在判断是否需要知识库...";
});

function submitPrompt() {
  if (props.prompt.trim() && !props.busy) {
    emit("submit", props.prompt);
  }
}

function handleKeydown(e) {
  if (props.busy) return;
  if (props.sendShortcut === "ctrl-enter") {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      submitPrompt();
    }
    return;
  }
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submitPrompt();
  }
}

function renderMessageHtml(message) {
  if (message?.role !== "assistant") return "";
  return renderMarkdown(message.content);
}

async function copyMessage(message) {
  const content = String(message?.content || "");
  if (!content.trim()) return;
  try {
    if (navigator.clipboard?.writeText && window.isSecureContext) {
      await navigator.clipboard.writeText(content);
    } else {
      const ta = document.createElement("textarea");
      ta.value = content;
      ta.style.position = "fixed"; ta.style.top = "-9999px"; ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select(); ta.setSelectionRange(0, ta.value.length);
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    copiedMsgId.value = message.id;
    setTimeout(() => { copiedMsgId.value = null; }, 2000);
  } catch { /* silent */ }
}

function selectAnswerMode(mode) {
  if (props.busy) return;
  emit("update:answer-mode", mode);
  showModeMenu.value = false;
}

function selectChatModel(id) {
  if (props.busy) return;
  emit("update:chat-model", id);
  showModelMenu.value = false;
}

function openKnowledgeFromMenu() {
  showModeMenu.value = false;
  emit("open-knowledge");
}

function closePopovers() {
  showModelMenu.value = false;
  showModeMenu.value = false;
}

const exportTaskId = ref("");

async function handleExport(format = "json") {
  if (!props.session?.id || exporting.value) return;

  exporting.value = true;
  try {
    const result = await exportSessionAsync(props.session.id, format);
    if (result.task_id) {
      exportTaskId.value = result.task_id;
      // 等待 WebSocket export_complete 事件触发下载
    } else {
      // 同步回退
      const blob = await exportSession(props.session.id, format);
      const filename = `chat_${props.session.id.slice(0, 8)}.${format}`;
      downloadFile(blob, filename);
      exporting.value = false;
    }
  } catch (error) {
    console.error("导出失败:", error);
    alert(error.message || "导出失败，请稍后重试");
    exporting.value = false;
  }
}

function handleExportWsMessage(data) {
  if (data.type === "export_complete" && data.task_id === exportTaskId.value) {
    exporting.value = false;
    exportTaskId.value = "";
    if (data.status === "success" && data.download_url) {
      downloadExport(data.download_url).then((blob) => {
        downloadFile(blob, data.filename || "export.json");
      }).catch(() => {
        alert("下载导出文件失败，请重试。");
      });
    } else {
      alert(data.message || "导出失败，请重试。");
    }
  }
}

onMounted(() => {
  addUploadWsListener(handleExportWsMessage);
});

onUnmounted(() => {
  removeUploadWsListener(handleExportWsMessage);
});

watch(() => messageScrollSignature.value, async () => {
  await nextTick();
  if (messagePaneRef.value) {
    messagePaneRef.value.scrollTop = messagePaneRef.value.scrollHeight;
  }
}, { immediate: true });
</script>

<template>
  <div class="flex-1 flex flex-col min-w-0 h-full bg-white" @click="closePopovers">
    <!-- ===== HERO / EMPTY STATE ===== -->
    <div v-if="showHero" class="flex-1 flex flex-col items-center justify-center px-6">
      <div class="w-14 h-14 rounded-xl bg-zinc-100 flex items-center justify-center mb-5 ring-1 ring-zinc-200">
        <Sparkles class="w-7 h-7 text-zinc-600" />
      </div>
      <h1 class="text-2xl font-semibold text-zinc-900 mb-1.5 tracking-[-0.01em]">今天想让我帮你处理什么？</h1>
      <p class="text-sm text-zinc-500 mb-8">{{ welcomeMessage }}</p>

      <div v-if="suggestions.length" class="max-w-[600px] w-full mb-10">
        <div class="flex flex-wrap gap-2 justify-center">
          <button v-for="(s, i) in suggestions" :key="i" @click="emit('choose-suggestion', s)" class="px-3 py-2 text-xs text-zinc-600 bg-white border border-zinc-200 rounded-md hover:bg-zinc-50 hover:border-zinc-300 transition-colors">{{ s }}</button>
        </div>
      </div>
    </div>

    <!-- ===== CONVERSATION STATE ===== -->
    <template v-else>
      <div class="px-6 py-3 border-b border-zinc-200 bg-white flex items-center justify-between shrink-0">
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center shrink-0">
            <Sparkles class="w-4 h-4 text-zinc-600" />
          </div>
          <div>
            <h2 class="text-[13px] font-semibold text-zinc-900">{{ session.title || '新对话' }}</h2>
            <p class="text-[11px] text-zinc-500">{{ renderedMessages.length }} 条消息 · {{ providerLabel }}</p>
          </div>
        </div>
        
        <!-- 导出按钮 -->
        <div v-if="renderedMessages.length > 0" class="flex items-center gap-2">
          <div class="relative">
            <button 
              @click.stop="handleExport('json')" 
              :disabled="exporting"
              class="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-zinc-600 bg-zinc-100 hover:bg-zinc-200 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="导出为 JSON"
            >
              <Download class="w-3.5 h-3.5" />
              <span class="hidden sm:inline">{{ exporting ? '导出中...' : '导出' }}</span>
            </button>
          </div>
        </div>
      </div>

      <div ref="messagePaneRef" class="flex-1 overflow-y-auto px-6 py-6 bg-zinc-50">
        <div class="max-w-[640px] mx-auto space-y-5">
          <div v-for="message in renderedMessages" :key="message.id">
            <div v-if="message.role === 'user'" class="flex flex-col items-end">
              <div class="max-w-[75%] px-4 py-2.5 bg-zinc-900 text-white rounded-lg rounded-br-sm text-sm leading-relaxed whitespace-pre-wrap">{{ message.content }}</div>
            </div>

            <div v-else class="flex gap-3">
              <div class="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center shrink-0 mt-0.5 ring-1 ring-zinc-200">
                <Sparkles class="w-4 h-4 text-zinc-500" />
              </div>
              <div class="flex-1 min-w-0">
                <span class="text-[11px] font-medium text-zinc-500 mb-1.5 block">AI 助手</span>
                <div class="bg-white border border-zinc-200 rounded-lg">
                  <div class="px-4 py-3">
                    <div class="markdown-content text-sm text-zinc-900 leading-relaxed" v-html="renderMessageHtml(message)"></div>
                  </div>
                </div>
                <div v-if="message.sources?.length" class="mt-3">
                  <div class="text-xs font-medium text-zinc-500 mb-2">参考来源</div>
                  <div class="space-y-2">
                    <div
                      v-for="(source, idx) in message.sources.slice(0, 5)"
                      :key="idx"
                      class="bg-white border border-zinc-200 rounded-lg p-3 hover:border-zinc-300 transition-colors"
                    >
                      <div class="flex items-center justify-between mb-1.5 gap-2">
                        <span class="text-sm font-medium text-zinc-800 break-all">{{ source.filename }}</span>
                        <span class="text-xs text-zinc-400 shrink-0">{{ source.score }}</span>
                      </div>
                      <p class="text-xs text-zinc-500 leading-relaxed whitespace-pre-wrap">{{ source.preview }}</p>
                    </div>
                    <div v-if="message.sources.length > 5" class="text-xs text-zinc-400 text-center py-1">
                      还有 {{ message.sources.length - 5 }} 个来源未显示
                    </div>
                  </div>
                </div>
                <div class="flex items-center gap-1 mt-1">
                  <button @click="copyMessage(message)" class="p-1 text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 rounded transition-colors" title="复制回答">
                    <Check v-if="copiedMsgId === message.id" class="w-3.5 h-3.5 text-emerald-500" />
                    <Copy v-else class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="showTyping" class="flex gap-3">
            <div class="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center shrink-0 ring-1 ring-zinc-200">
              <Sparkles class="w-4 h-4 text-zinc-500" />
            </div>
            <div class="bg-white border border-zinc-200 rounded-lg px-4 py-3">
              <div class="flex gap-1.5 mb-2">
                <span class="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" />
                <span class="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
                <span class="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
              </div>
              <p class="text-xs text-zinc-400">{{ typingCopy }}</p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ===== BOTTOM INPUT ===== -->
    <div class="px-6 py-3 border-t border-zinc-200 bg-white shrink-0">
      <div class="max-w-[640px] mx-auto">
        <div class="flex items-end gap-2">
          <div class="flex-1 flex items-end gap-2 bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2.5 focus-within:border-zinc-300 focus-within:bg-white transition-colors">
            <textarea
              :value="prompt"
              @input="emit('update:prompt', $event.target.value)"
              @keydown="handleKeydown"
              :placeholder="showHero ? '发送消息...' : '继续提问...'"
              rows="1"
              :disabled="busy"
              class="flex-1 text-sm bg-transparent placeholder:text-zinc-400 resize-none focus:outline-none min-h-[22px] leading-6"
            />
          </div>

          <button
            v-if="busy"
            @click="emit('stop')"
            class="shrink-0 w-9 h-9 bg-red-500 text-white rounded-full flex items-center justify-center hover:bg-red-600 transition-colors shadow-sm"
            title="停止回答"
          >
            <Square class="w-4 h-4" />
          </button>
          <button
            v-else
            @click="submitPrompt"
            :disabled="!prompt.trim()"
            class="shrink-0 w-9 h-9 bg-zinc-900 text-white rounded-full flex items-center justify-center hover:bg-zinc-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed shadow-sm"
            title="发送"
          >
            <ArrowUp class="w-4 h-4" />
          </button>
        </div>

        <div class="flex items-center justify-between mt-2.5">
          <div class="flex items-center gap-2 flex-wrap">
            <button @click="emit('open-knowledge')" class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs text-zinc-600 bg-zinc-100 hover:bg-zinc-200 rounded-full transition-colors">
              <FolderOpen class="w-3.5 h-3.5" /> 知识库
            </button>
            <span class="text-xs text-zinc-400">{{ sendShortcutLabel }}</span>
            <span v-if="showKnowledgeTips" class="text-xs text-zinc-400 hidden sm:inline">{{ providerLabel }}</span>
          </div>

          <div class="flex items-center gap-1.5">
            <!-- Answer mode popover -->
            <div class="relative">
              <button @click.stop="showModeMenu = !showModeMenu; showModelMenu = false" :disabled="busy" class="inline-flex items-center gap-1 px-2.5 py-1 text-xs text-zinc-600 bg-zinc-100 hover:bg-zinc-200 rounded-full transition-colors disabled:opacity-50">
                模式: <span class="font-medium text-zinc-800">{{ currentModeLabel }}</span>
                <ChevronDown class="w-3 h-3" />
              </button>
              <div v-if="showModeMenu" class="absolute bottom-full right-0 mb-2 w-52 bg-white rounded-xl shadow-lg border border-zinc-200 overflow-hidden z-50" @click.stop>
                <button v-for="opt in answerModeOptions" :key="opt.value" @click="selectAnswerMode(opt.value)" :class="['w-full flex items-center justify-between px-3 py-2.5 text-sm text-left hover:bg-zinc-50 transition-colors', props.answerMode === opt.value ? 'text-zinc-900 font-medium bg-zinc-50' : 'text-zinc-600']">
                  <div>
                    <div class="font-medium">{{ opt.label }}</div>
                    <div class="text-xs text-zinc-400">{{ opt.desc }}</div>
                  </div>
                  <Check v-if="props.answerMode === opt.value" class="w-4 h-4 text-zinc-900 shrink-0" />
                </button>
                <div class="border-t border-zinc-100" />
                <button @click="openKnowledgeFromMenu" class="w-full flex items-center justify-between px-3 py-2.5 text-sm text-zinc-600 hover:bg-zinc-50 transition-colors">
                  <span>知识库管理</span>
                  <ArrowRight class="w-4 h-4 text-zinc-400" />
                </button>
              </div>
            </div>

            <!-- Model selector popover -->
            <div v-if="chatModelOptions.length" class="relative">
              <button @click.stop="showModelMenu = !showModelMenu; showModeMenu = false" :disabled="busy" class="inline-flex items-center gap-1 px-2.5 py-1 text-xs text-zinc-600 bg-zinc-100 hover:bg-zinc-200 rounded-full transition-colors disabled:opacity-50">
                模型: <span class="font-medium text-zinc-800 truncate max-w-[100px]">{{ currentModelLabel }}</span>
                <ChevronDown class="w-3 h-3" />
              </button>
              <div v-if="showModelMenu" class="absolute bottom-full right-0 mb-2 w-64 bg-white rounded-xl shadow-lg border border-zinc-200 overflow-hidden z-50" @click.stop>
                <button v-for="opt in chatModelOptions" :key="opt.id" @click="selectChatModel(opt.id)" :class="['w-full flex items-center justify-between px-3 py-2.5 text-sm text-left hover:bg-zinc-50 transition-colors', props.chatModelId === opt.id ? 'text-zinc-900 font-medium bg-zinc-50' : 'text-zinc-600']">
                  <div>
                    <div class="font-medium">{{ opt.label }}</div>
                    <div class="text-xs text-zinc-400">{{ opt.provider_label }}</div>
                  </div>
                  <Check v-if="props.chatModelId === opt.id" class="w-4 h-4 text-zinc-900 shrink-0" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
