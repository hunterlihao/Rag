<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import {
  ArrowDown,
  ArrowRight,
  Check,
  CopyDocument,
  FolderAdd,
  Promotion,
  VideoPause,
} from "@element-plus/icons-vue";
import { renderMarkdown } from "@/services/markdown";

const props = defineProps({
  session: {
    type: Object,
    required: true,
  },
  busy: {
    type: Boolean,
    default: false,
  },
  prompt: {
    type: String,
    default: "",
  },
  providerLabel: {
    type: String,
    default: "",
  },
  suggestions: {
    type: Array,
    default: () => [],
  },
  welcomeMessage: {
    type: String,
    default: "",
  },
  sendShortcut: {
    type: String,
    default: "enter",
  },
  showKnowledgeTips: {
    type: Boolean,
    default: true,
  },
  answerMode: {
    type: String,
    default: "auto",
  },
  chatModelId: {
    type: String,
    default: "",
  },
  chatModelOptions: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits([
  "update:prompt",
  "update:answer-mode",
  "update:chat-model",
  "submit",
  "stop",
  "choose-suggestion",
  "open-knowledge",
]);

const messagePaneRef = ref(null);
const answerModeMenuOpen = ref(false);
const chatModelMenuOpen = ref(false);
const answerModeOptions = [
  { label: "自动", value: "auto" },
  { label: "知识库", value: "knowledge" },
  { label: "聊天", value: "chat" },
];

const showHero = computed(() => props.session.messages.length === 0);
const renderedMessages = computed(() => (showHero.value ? [] : props.session.messages));
const messageScrollSignature = computed(() =>
  props.session.messages
    .map((message) => `${message.id || ""}:${String(message.content || "").length}`)
    .join("|"),
);
const hasStreamingAssistant = computed(() => {
  const lastMessage = renderedMessages.value[renderedMessages.value.length - 1];
  return (
    props.busy &&
    lastMessage?.role === "assistant" &&
    String(lastMessage.id || "").startsWith("local-assistant-")
  );
});
const showTyping = computed(() => props.busy && !hasStreamingAssistant.value);
const sendShortcutLabel = computed(() =>
  props.sendShortcut === "ctrl-enter" ? "Ctrl+Enter 发送" : "Enter 发送",
);
const currentAnswerModeLabel = computed(
  () => answerModeOptions.find((item) => item.value === props.answerMode)?.label || "自动",
);
const currentChatModel = computed(() => {
  return (
    props.chatModelOptions.find((item) => item.id === props.chatModelId) ||
    props.chatModelOptions[0] || {
      id: "",
      label: "默认模型",
      provider_label: props.providerLabel,
      model: props.providerLabel,
    }
  );
});
const currentChatModelLabel = computed(() => currentChatModel.value.label || "默认模型");
const typingCopy = computed(() => {
  if (props.answerMode === "chat") {
    return "正在组织回答...";
  }
  if (props.answerMode === "knowledge") {
    return "正在检索知识库并组织回答...";
  }
  return "正在判断是否需要知识库...";
});

function submitCurrentPrompt() {
  emit("submit", props.prompt);
}

function stopCurrentAnswer() {
  emit("stop");
}

function renderMessageContent(message) {
  if (message?.role !== "assistant") {
    return "";
  }
  return renderMarkdown(message.content);
}

async function writeTextToClipboard(text) {
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return true;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  document.body.removeChild(textarea);
  return copied;
}

async function copyMessageContent(message) {
  const content = String(message?.content || "");
  if (!content.trim()) {
    ElMessage.warning("暂无可复制的回答");
    return;
  }

  try {
    const copied = await writeTextToClipboard(content);
    if (!copied) {
      throw new Error("Clipboard copy failed");
    }
    ElMessage.success("已复制回答");
  } catch (error) {
    ElMessage.error("复制失败，请手动选择内容。");
  }
}

function selectAnswerMode(answerMode) {
  if (props.busy) {
    return;
  }
  emit("update:answer-mode", answerMode);
  answerModeMenuOpen.value = false;
}

function selectChatModel(chatModelId) {
  if (props.busy) {
    return;
  }
  emit("update:chat-model", chatModelId);
  chatModelMenuOpen.value = false;
}

function openKnowledgeFromMenu() {
  answerModeMenuOpen.value = false;
  emit("open-knowledge");
}

function handleTextareaKeydown(event) {
  if (props.busy) {
    return;
  }

  if (props.sendShortcut === "ctrl-enter") {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submitCurrentPrompt();
    }
    return;
  }

  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitCurrentPrompt();
  }
}

watch(
  () => messageScrollSignature.value,
  async () => {
    await nextTick();
    if (messagePaneRef.value) {
      messagePaneRef.value.scrollTop = messagePaneRef.value.scrollHeight;
    }
  },
  { immediate: true },
);
</script>

<template>
  <section class="chat-workspace">
    <header class="chat-workspace__header">
      <div class="chat-workspace__header-copy">
        <h2>{{ session.title || "新对话" }}</h2>
        <span>{{ providerLabel }}</span>
      </div>
    </header>

    <div ref="messagePaneRef" class="chat-workspace__messages">
      <div v-if="showHero" class="chat-hero">
        <div class="chat-hero__badge">智能问答</div>
        <h1>今天想让我帮你处理什么？</h1>
        <p>
          {{
            welcomeMessage ||
            "可以直接提问，也可以先导入 PDF、Word、Excel、CSV、Markdown、TXT 到当前账号的独立知识库。"
          }}
        </p>

        <div class="chat-hero__suggestions">
          <button
            v-for="item in suggestions"
            :key="item"
            type="button"
            class="chat-hero__chip"
            @click="emit('choose-suggestion', item)"
          >
            {{ item }}
          </button>
        </div>
      </div>

      <div class="chat-workspace__conversation">
        <div
          v-for="message in renderedMessages"
          :key="message.id"
          class="message-row"
          :class="{ 'message-row--user': message.role === 'user' }"
        >
          <div class="message-card" :class="{ 'message-card--user': message.role === 'user' }">
            <div class="message-card__topline">
              <div class="message-card__role">{{ message.role === "user" ? "你" : "助手" }}</div>
              <el-tooltip v-if="message.role === 'assistant'" content="复制回答" placement="top">
                <button
                  type="button"
                  class="message-copy-button"
                  aria-label="复制回答"
                  @click="copyMessageContent(message)"
                >
                  <el-icon><CopyDocument /></el-icon>
                </button>
              </el-tooltip>
            </div>
            <div
              v-if="message.role === 'assistant'"
              class="message-card__content markdown-content"
              v-html="renderMessageContent(message)"
            ></div>
            <div v-else class="message-card__content">{{ message.content }}</div>
          </div>
        </div>

        <div v-if="showTyping" class="message-row">
          <div class="message-card typing-card">
            <div class="message-card__role">助手</div>
            <div class="typing-card__dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div class="typing-card__copy">{{ typingCopy }}</div>
          </div>
        </div>
      </div>
    </div>

    <footer class="chat-workspace__composer-shell">
      <div class="chat-workspace__composer">
        <el-input
          :model-value="prompt"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 6 }"
          resize="none"
          placeholder="发送消息..."
          :disabled="busy"
          @update:model-value="emit('update:prompt', $event)"
          @keydown="handleTextareaKeydown"
        />

        <div class="chat-workspace__composer-bar">
          <div class="chat-workspace__tools">
            <button type="button" class="tool-chip" @click="emit('open-knowledge')">
              <el-icon><FolderAdd /></el-icon>
              <span>知识库</span>
            </button>
            <span class="tool-chip tool-chip--muted">{{ sendShortcutLabel }}</span>
            <span v-if="showKnowledgeTips" class="tool-chip tool-chip--muted">
              {{ providerLabel }}
            </span>
          </div>

          <div class="chat-workspace__actions">
            <el-popover
              v-model:visible="chatModelMenuOpen"
              placement="top-start"
              trigger="click"
              popper-class="chat-model-popover"
              :width="300"
              :show-arrow="false"
              :disabled="busy || !chatModelOptions.length"
            >
              <template #reference>
                <button
                  type="button"
                  class="mode-pill model-pill"
                  :class="{ 'mode-pill--open': chatModelMenuOpen }"
                  :disabled="busy || !chatModelOptions.length"
                >
                  <span class="mode-pill__prefix">模型</span>
                  <span class="mode-pill__value model-pill__value">
                    {{ currentChatModelLabel }}
                  </span>
                  <el-icon class="mode-pill__chevron"><ArrowDown /></el-icon>
                </button>
              </template>

              <div class="chat-model-menu">
                <button
                  v-for="item in chatModelOptions"
                  :key="item.id"
                  type="button"
                  class="chat-model-item"
                  :class="{ 'chat-model-item--selected': chatModelId === item.id }"
                  @click="selectChatModel(item.id)"
                >
                  <span class="chat-model-item__copy">
                    <strong>{{ item.label }}</strong>
                    <small>{{ item.provider_label }}</small>
                  </span>
                  <el-icon v-if="chatModelId === item.id"><Check /></el-icon>
                </button>
              </div>
            </el-popover>

            <el-popover
              v-model:visible="answerModeMenuOpen"
              placement="top-start"
              trigger="click"
              popper-class="answer-mode-popover"
              :width="270"
              :show-arrow="false"
              :disabled="busy"
            >
              <template #reference>
                <button
                  type="button"
                  class="mode-pill"
                  :class="{ 'mode-pill--open': answerModeMenuOpen }"
                  :disabled="busy"
                >
                  <span class="mode-pill__prefix">模式</span>
                  <span class="mode-pill__value">{{ currentAnswerModeLabel }}</span>
                  <el-icon class="mode-pill__chevron"><ArrowDown /></el-icon>
                </button>
              </template>

              <div class="answer-mode-menu">
                <!-- <div class="answer-mode-menu__eyebrow">智能</div> -->
                <button
                  v-for="item in answerModeOptions"
                  :key="item.value"
                  type="button"
                  class="answer-mode-item"
                  :class="{ 'answer-mode-item--selected': answerMode === item.value }"
                  @click="selectAnswerMode(item.value)"
                >
                  <span>{{ item.label }}</span>
                  <el-icon v-if="answerMode === item.value"><Check /></el-icon>
                </button>

                <div class="answer-mode-menu__divider"></div>
                <button type="button" class="answer-mode-footer" @click="openKnowledgeFromMenu">
                  <span>知识库管理</span>
                  <el-icon><ArrowRight /></el-icon>
                </button>
              </div>
            </el-popover>

            <el-button
              v-if="busy"
              circle
              type="danger"
              :icon="VideoPause"
              title="停止回答"
              aria-label="停止回答"
              @click="stopCurrentAnswer"
            />
            <el-button
              v-else
              circle
              type="primary"
              :icon="Promotion"
              @click="submitCurrentPrompt"
            />
          </div>
        </div>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.chat-workspace {
  position: relative;
  height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(32, 85, 186, 0.08);
  overflow: hidden;
}

.chat-workspace__header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(32, 85, 186, 0.08);
}

.chat-workspace__header-copy h2,
.chat-workspace__header-copy span {
  display: block;
}

.chat-workspace__header-copy h2 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
}

.chat-workspace__header-copy span {
  margin-top: 4px;
  color: var(--muted);
  font-size: 0.82rem;
}

.chat-workspace__messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 24px;
}

.chat-workspace__conversation,
.chat-hero {
  width: min(980px, 100%);
  margin: 0 auto;
}

.chat-hero {
  min-height: calc(100vh - 360px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 20px 8px 60px;
}

.chat-hero__badge {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(237, 244, 255, 0.96);
  color: var(--accent);
  font-size: 0.88rem;
  font-weight: 700;
}

.chat-hero h1 {
  margin: 20px 0 12px;
  font-size: clamp(2.4rem, 5vw, 4rem);
  line-height: 1.08;
  letter-spacing: -0.04em;
}

.chat-hero p {
  margin: 0;
  max-width: 760px;
  color: var(--muted);
  font-size: 1rem;
  line-height: 1.8;
}

.chat-hero__suggestions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 28px;
}

.chat-hero__chip {
  padding: 16px 18px;
  border: 1px solid rgba(32, 85, 186, 0.08);
  border-radius: 18px;
  background: rgba(250, 252, 255, 0.98);
  color: var(--ink);
  text-align: left;
  cursor: pointer;
}

.message-row {
  display: flex;
  margin-bottom: 18px;
}

.message-row--user {
  justify-content: flex-end;
}

.message-card {
  max-width: min(860px, 88%);
  padding: 18px 20px;
  border-radius: 22px;
  background: rgba(248, 250, 255, 0.96);
  border: 1px solid rgba(32, 85, 186, 0.08);
}

.message-card--user {
  background: linear-gradient(135deg, #1d56d9, #4a83ff);
  color: #fff;
  border-color: transparent;
}

.message-card__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.message-card__role {
  min-width: 0;
  font-size: 0.8rem;
  font-weight: 700;
  opacity: 0.76;
}

.message-copy-button {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 9px;
  background: rgba(46, 108, 246, 0.08);
  color: #2e6cf6;
  cursor: pointer;
  opacity: 0.72;
  transition:
    background 0.18s ease,
    color 0.18s ease,
    opacity 0.18s ease,
    transform 0.18s ease;
}

.message-copy-button:hover {
  background: rgba(46, 108, 246, 0.14);
  opacity: 1;
  transform: translateY(-1px);
}

.message-copy-button:focus-visible {
  outline: 2px solid rgba(46, 108, 246, 0.42);
  outline-offset: 2px;
}

.message-card__content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
}

.markdown-content {
  white-space: normal;
}

.markdown-content :deep(*) {
  max-width: 100%;
}

.markdown-content :deep(p) {
  margin: 0 0 12px;
  line-height: 1.8;
}

.markdown-content :deep(p:last-child),
.markdown-content :deep(ul:last-child),
.markdown-content :deep(ol:last-child),
.markdown-content :deep(pre:last-child),
.markdown-content :deep(blockquote:last-child),
.markdown-content :deep(.markdown-table-wrap:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin: 18px 0 10px;
  color: var(--ink);
  line-height: 1.35;
  font-weight: 800;
}

.markdown-content :deep(h1:first-child),
.markdown-content :deep(h2:first-child),
.markdown-content :deep(h3:first-child),
.markdown-content :deep(h4:first-child) {
  margin-top: 0;
}

.markdown-content :deep(h1) {
  font-size: 1.35rem;
}

.markdown-content :deep(h2) {
  font-size: 1.22rem;
}

.markdown-content :deep(h3) {
  font-size: 1.08rem;
}

.markdown-content :deep(h4) {
  font-size: 1rem;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 0 0 12px;
  padding-left: 1.35rem;
}

.markdown-content :deep(li) {
  margin: 5px 0;
  line-height: 1.75;
}

.markdown-content :deep(blockquote) {
  margin: 12px 0;
  padding: 10px 14px;
  border-left: 3px solid rgba(46, 108, 246, 0.36);
  border-radius: 0 12px 12px 0;
  background: rgba(46, 108, 246, 0.07);
  color: #334769;
}

.markdown-content :deep(blockquote p) {
  margin-bottom: 8px;
}

.markdown-content :deep(blockquote p:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(code) {
  padding: 2px 6px;
  border-radius: 7px;
  background: rgba(20, 40, 71, 0.08);
  color: #173057;
  font-family: "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
  font-size: 0.92em;
}

.markdown-content :deep(pre) {
  margin: 14px 0;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgba(20, 40, 71, 0.1);
  background: #14213a;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.markdown-content :deep(pre code) {
  display: block;
  overflow-x: auto;
  padding: 14px 16px 16px;
  border-radius: 0;
  background: transparent;
  color: #e9f1ff;
  line-height: 1.7;
  white-space: pre;
}

.markdown-content :deep(.markdown-code-label) {
  min-height: 10px;
  padding: 8px 14px 0;
  color: rgba(233, 241, 255, 0.62);
  font-family: "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
  font-size: 0.76rem;
  text-align: right;
}

.markdown-content :deep(.markdown-code-label:empty) {
  display: none;
}

.markdown-content :deep(a) {
  color: var(--accent);
  font-weight: 700;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.markdown-content :deep(.markdown-table-wrap) {
  width: 100%;
  margin: 14px 0;
  overflow-x: auto;
  border-radius: 14px;
  border: 1px solid rgba(20, 40, 71, 0.1);
}

.markdown-content :deep(table) {
  width: 100%;
  min-width: 420px;
  border-collapse: collapse;
  background: rgba(255, 255, 255, 0.74);
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(20, 40, 71, 0.08);
  text-align: left;
  vertical-align: top;
  line-height: 1.65;
}

.markdown-content :deep(th) {
  background: rgba(46, 108, 246, 0.08);
  color: #18345e;
  font-weight: 800;
}

.markdown-content :deep(tr:last-child td) {
  border-bottom: none;
}

.message-card--user .markdown-content :deep(*) {
  color: inherit;
}

.typing-card__dots {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.typing-card__dots span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--accent);
  animation: dotPulse 1.1s infinite ease-in-out;
}

.typing-card__dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-card__dots span:nth-child(3) {
  animation-delay: 0.3s;
}

.typing-card__copy {
  color: var(--muted);
}

.chat-workspace__composer-shell {
  flex: 0 0 auto;
  padding: 16px 20px 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.96) 24%);
}

.chat-workspace__composer {
  width: min(980px, 100%);
  margin: 0 auto;
  padding: 18px 18px 14px;
  border-radius: 26px;
  background: #ffffff;
  border: 1px solid rgba(32, 85, 186, 0.1);
  box-shadow: 0 18px 36px rgba(25, 66, 132, 0.1);
}

.chat-workspace__composer-bar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.chat-workspace__tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.chat-workspace__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex: 0 0 auto;
}

.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 12px;
  border: none;
  border-radius: 999px;
  background: rgba(244, 248, 255, 0.96);
  color: var(--ink);
  cursor: pointer;
}

.tool-chip--muted {
  color: var(--muted);
}

.mode-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 11px 0 13px;
  border: none;
  border-radius: 999px;
  background: rgba(238, 240, 243, 0.92);
  color: var(--ink);
  cursor: pointer;
  flex: 0 0 auto;
  transition:
    background 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.mode-pill:hover,
.mode-pill--open {
  background: rgba(229, 232, 237, 0.98);
  box-shadow: inset 0 0 0 1px rgba(31, 74, 160, 0.05);
}

.mode-pill:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.mode-pill__prefix {
  color: var(--muted);
  font-size: 0.9rem;
}

.mode-pill__value {
  font-size: 0.9rem;
  font-weight: 700;
}

.model-pill__value {
  max-width: min(30vw, 180px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mode-pill__chevron {
  color: var(--muted);
  transition: transform 0.18s ease;
}

.mode-pill--open .mode-pill__chevron {
  transform: rotate(180deg);
}

:global(.answer-mode-popover.el-popover) {
  padding: 8px;
  border: 1px solid rgba(24, 42, 70, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow:
    0 18px 50px rgba(27, 44, 72, 0.16),
    0 2px 12px rgba(27, 44, 72, 0.07);
  backdrop-filter: blur(18px);
}

.chat-model-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

:global(.chat-model-popover.el-popover) {
  padding: 8px;
  border: 1px solid rgba(24, 42, 70, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow:
    0 18px 50px rgba(27, 44, 72, 0.16),
    0 2px 12px rgba(27, 44, 72, 0.07);
  backdrop-filter: blur(18px);
}

.chat-model-item {
  width: 100%;
  min-height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
}

.chat-model-item:hover,
.chat-model-item--selected {
  background: rgba(237, 238, 240, 0.96);
}

.chat-model-item__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.chat-model-item__copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.95rem;
}

.chat-model-item__copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted);
  font-size: 0.78rem;
}

.chat-model-item .el-icon {
  flex: 0 0 auto;
  color: #596274;
  font-size: 1rem;
}

.answer-mode-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.answer-mode-menu__eyebrow {
  padding: 7px 10px 5px;
  color: var(--muted);
  font-size: 0.92rem;
  font-weight: 700;
}

.answer-mode-item,
.answer-mode-footer {
  width: 100%;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  font-size: 0.95rem;
  text-align: left;
}

.answer-mode-item {
  padding: 0 10px;
}

.answer-mode-footer {
  padding: 0 10px;
}

.answer-mode-item:hover,
.answer-mode-footer:hover,
.answer-mode-item--selected {
  background: rgba(237, 238, 240, 0.96);
}

.answer-mode-item .el-icon,
.answer-mode-footer .el-icon {
  color: #596274;
  font-size: 1rem;
}

.answer-mode-menu__divider {
  height: 1px;
  margin: 7px 10px;
  background: rgba(24, 42, 70, 0.1);
}

@keyframes dotPulse {
  0%,
  80%,
  100% {
    transform: scale(0.75);
    opacity: 0.35;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (max-width: 960px) {
  .chat-workspace {
    height: auto;
    min-height: 720px;
  }

  .chat-hero {
    min-height: auto;
    padding-bottom: 24px;
  }

  .chat-hero__suggestions {
    grid-template-columns: 1fr;
  }

  .chat-workspace__composer-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .chat-workspace__actions {
    justify-content: space-between;
  }

  .chat-workspace__messages {
    padding: 18px;
  }

  .message-card {
    max-width: 100%;
  }
}
</style>
