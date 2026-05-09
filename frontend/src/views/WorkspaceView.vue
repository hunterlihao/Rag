<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import ActionBusyOverlay from "@/components/ActionBusyOverlay.vue";
import ChatWorkspace from "@/components/ChatWorkspace.vue";
import WorkspaceSidebar from "@/components/WorkspaceSidebar.vue";
import { getCurrentUser, logout } from "@/services/auth";
import { appConfig } from "@/services/config";
import { buildRouteLocation, buildSidebarNavItems, normalizeShellSession } from "@/services/shell";
import { getPreferences, savePreferences } from "@/services/user";
import {
  buildWelcomeMessage,
  createSession,
  deleteSession,
  fetchBackendMeta,
  fetchSessionDetail,
  fetchSessions,
  sendPromptStream,
  stopPromptStream,
  suggestedPrompts,
} from "@/services/workspace";

const route = useRoute();
const router = useRouter();
const user = ref(getCurrentUser());
const preferences = ref(getPreferences(user.value));
const sessions = ref([]);
const activeSessionId = ref("");
const sessionSearch = ref("");
const prompt = ref("");
const isAnswering = ref(false);
const isStoppingAnswer = ref(false);
const activeAnswerController = ref(null);
const activeAnswerRequestId = ref("");
const activeAnswerPrompt = ref("");
const activeAnswerExpectedMessageCount = ref(0);
const deletingSessionId = ref("");
const welcomeMessage = ref("你好，我已经准备好结合知识库回答问题了。");
const startupError = ref("");
const pageLoading = ref(false);

const sidebarBusy = computed(() => isAnswering.value || !!deletingSessionId.value);
const deleteBusyState = computed(() => ({
  visible: !!deletingSessionId.value,
  badgeText: "删除处理中",
  title: "正在删除会话",
  description: "会话记录正在清理并刷新工作区，请等待当前操作完成。",
}));
const navItems = computed(() => buildSidebarNavItems(user.value));

const filteredSessions = computed(() => {
  const keyword = sessionSearch.value.trim().toLowerCase();
  return sessions.value
    .filter((s) => {
      if (!keyword) return true;
      return `${s.title} ${s.preview || ""}`.toLowerCase().includes(keyword);
    })
    .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
});

const activeSession = computed(() => {
  const found = sessions.value.find((s) => s.id === activeSessionId.value);
  return found || {
    id: "", title: "新对话", preview: "还没有消息",
    messageCount: 0, updatedAt: new Date().toISOString(),
    messages: [], welcomeMessage: welcomeMessage.value,
  };
});

const modelSettings = reactive({
  provider: appConfig.modelProvider,
  chatModel: appConfig.chatModel,
  embeddingModel: appConfig.embeddingModel,
  defaultChatModelId: "",
  chatModels: [],
});

const selectedChatModel = computed(() => {
  return modelSettings.chatModels.find((m) => m.id === preferences.value.chatModelId) || modelSettings.chatModels[0] || null;
});

const currentProviderLabel = computed(() => {
  return selectedChatModel.value?.provider_label || modelSettings.provider;
});

function mergeSession(sessionPayload) {
  const session = { ...normalizeShellSession(sessionPayload), welcomeMessage: buildWelcomeMessage(sessionPayload) };
  const idx = sessions.value.findIndex((s) => s.id === session.id);
  if (idx >= 0) sessions.value.splice(idx, 1, session);
  else sessions.value.unshift(session);
  sessions.value.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
  return session;
}

async function loadSession(sessionId) {
  const detail = await fetchSessionDetail(sessionId);
  const merged = mergeSession(detail);
  activeSessionId.value = merged.id;
  welcomeMessage.value = merged.welcomeMessage;
}

function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function syncStoppedSession(sessionId, expectedPrompt, expectedMessageCount) {
  for (const delay of [120, 280, 520, 900]) {
    await wait(delay);
    const detail = await fetchSessionDetail(sessionId);
    const msgs = Array.isArray(detail?.messages) ? detail.messages : [];
    const hasPrompt = msgs.some((m, i) => m?.role === "user" && String(m.content || "").trim() === expectedPrompt && i >= Math.max(0, msgs.length - 3));
    if (msgs.length >= expectedMessageCount && hasPrompt) {
      const merged = mergeSession(detail);
      activeSessionId.value = merged.id;
      welcomeMessage.value = merged.welcomeMessage;
      return;
    }
  }
  await loadSession(sessionId);
}

async function refreshSessions(preferredSessionId = "") {
  const list = await fetchSessions();
  sessions.value = list.map((s) => ({ ...normalizeShellSession(s), welcomeMessage: buildWelcomeMessage(s) }));
  if (!sessions.value.length) { await createNewSession(); return; }
  const nextId = sessions.value.find((s) => s.id === preferredSessionId)?.id || sessions.value.find((s) => s.id === activeSessionId.value)?.id || sessions.value[0].id;
  await loadSession(nextId);
}

async function createNewSession({ ignoreBusy = false } = {}) {
  if (!ignoreBusy && sidebarBusy.value) return;
  const session = await createSession();
  const merged = mergeSession(session);
  activeSessionId.value = merged.id;
  welcomeMessage.value = merged.welcomeMessage;
  prompt.value = "";
  // Navigate to workspace to ensure fresh chat view
  router.push(buildRouteLocation("workspace", merged.id));
}

async function selectSession(sessionId) {
  if (sidebarBusy.value) return;
  await loadSession(sessionId);
}

async function submitPrompt(rawPrompt) {
  const content = (rawPrompt || "").trim();
  if (!content || isAnswering.value) return;
  if (!activeSession.value.id) await createNewSession();

  const opt = activeSession.value;
  const serverCount = opt.messages.length;
  opt.messages = [...opt.messages, { id: `local-user-${Date.now()}`, role: "user", content }];
  opt.messageCount = opt.messages.length;
  const aid = `local-assistant-${Date.now()}`;
  let started = false;
  const reqId = `${activeSession.value.id}-${Date.now()}`;
  const ctrl = new AbortController();
  activeAnswerRequestId.value = reqId;
  activeAnswerController.value = ctrl;
  activeAnswerPrompt.value = content;
  activeAnswerExpectedMessageCount.value = serverCount + 2;
  isStoppingAnswer.value = false;
  prompt.value = "";
  isAnswering.value = true;

  let collectedSources = [];

  try {
    const updated = await sendPromptStream(activeSession.value.id, content, {
      answerMode: preferences.value.answerMode,
      chatModelId: preferences.value.chatModelId || modelSettings.defaultChatModelId,
      answerRequestId: reqId,
      signal: ctrl.signal,
      onDelta(delta) {
        if (!started) { opt.messages = [...opt.messages, { id: aid, role: "assistant", content: "" }]; started = true; }
        const msg = opt.messages.find((m) => m.id === aid);
        if (msg) { msg.content += delta; opt.messageCount = opt.messages.length; }
      },
      onSources(sources) {
        collectedSources = sources;
        const msg = opt.messages.find((m) => m.id === aid);
        if (msg) { msg.sources = sources; }
      },
    });
    mergeSession(updated);
    if (collectedSources.length) {
      const mergedSession = sessions.value.find((s) => s.id === activeSessionId.value);
      const lastAssistant = mergedSession?.messages?.slice().reverse().find((m) => m.role === "assistant");
      if (lastAssistant) { lastAssistant.sources = collectedSources; }
    }
  } catch (err) {
    if (err.name === "AbortError") {
      if (isStoppingAnswer.value) {
        await syncStoppedSession(activeSession.value.id, activeAnswerPrompt.value, activeAnswerExpectedMessageCount.value);
      } else {
        await loadSession(activeSession.value.id);
      }
      return;
    }
    await loadSession(activeSession.value.id);
  } finally {
    if (activeAnswerRequestId.value === reqId) {
      activeAnswerRequestId.value = "";
      activeAnswerController.value = null;
      activeAnswerPrompt.value = "";
      activeAnswerExpectedMessageCount.value = 0;
      isAnswering.value = false;
      isStoppingAnswer.value = false;
    }
  }
}

async function stopCurrentAnswer() {
  if (!isAnswering.value || isStoppingAnswer.value || !activeSession.value?.id) return;
  isStoppingAnswer.value = true;
  try {
    await stopPromptStream(activeSession.value.id, activeAnswerRequestId.value);
    activeAnswerController.value?.abort();
  } catch {
    activeAnswerController.value?.abort();
  }
}

function updateAnswerMode(mode) { preferences.value = savePreferences({ ...preferences.value, answerMode: mode }, user.value); }
function updateChatModel(id) { preferences.value = savePreferences({ ...preferences.value, chatModelId: id }, user.value); }

function syncChatModelPreference() {
  const ids = modelSettings.chatModels.map((m) => m.id);
  const fallback = modelSettings.defaultChatModelId || ids[0] || "";
  if (!fallback || ids.includes(preferences.value.chatModelId)) return;
  preferences.value = savePreferences({ ...preferences.value, chatModelId: fallback }, user.value);
}

async function handleLogout() {
  await logout();
  router.push("/login");
}

async function handleDeleteSession(sessionId) {
  if (!sessionId || sidebarBusy.value) return;
  deletingSessionId.value = sessionId;
  try {
    const result = await deleteSession(sessionId);
    const wasActive = activeSessionId.value === sessionId;
    sessions.value = sessions.value.filter((s) => s.id !== sessionId);
    if (wasActive) {
      activeSessionId.value = "";
      const nextId = result.next_session_id || sessions.value[0]?.id || "";
      if (nextId) await loadSession(nextId);
      else await createNewSession({ ignoreBusy: true });
    }
  } finally {
    deletingSessionId.value = "";
  }
}

function navigateTo(name) { router.push(buildRouteLocation(name, activeSessionId.value)); }
function toggleSidebarCollapse() {
  preferences.value = savePreferences({ ...preferences.value, sidebarCollapsed: !preferences.value.sidebarCollapsed }, user.value);
}

watch(activeSessionId, (id) => {
  if (route.name !== "workspace") return;
  const q = typeof route.query.session === "string" ? route.query.session : "";
  if ((id || "") === q) return;
  router.replace({ name: "workspace", query: id ? { session: id } : {} });
});

onMounted(async () => {
  pageLoading.value = true;
  try {
    user.value = getCurrentUser();
    preferences.value = getPreferences(user.value);
    const meta = await fetchBackendMeta();
    modelSettings.provider = meta.model_provider || appConfig.modelProvider;
    modelSettings.chatModel = meta.chat_model || appConfig.chatModel;
    modelSettings.embeddingModel = meta.embedding_model || appConfig.embeddingModel;
    modelSettings.defaultChatModelId = meta.default_chat_model_id || "";
    modelSettings.chatModels = Array.isArray(meta.chat_models) ? meta.chat_models : [];
    syncChatModelPreference();
    startupError.value = meta.startup_error || "";
    const preferredId = typeof route.query.session === "string" ? route.query.session : "";
    await refreshSessions(preferredId);
  } catch {
    if (!getCurrentUser()) router.push("/login");
  } finally {
    pageLoading.value = false;
  }
});
</script>

<template>
  <div class="flex h-screen bg-zinc-50">
    <ActionBusyOverlay
      :visible="deleteBusyState.visible"
      :badge-text="deleteBusyState.badgeText"
      :title="deleteBusyState.title"
      :description="deleteBusyState.description"
    />
    <WorkspaceSidebar
      :user="user"
      :sessions="filteredSessions"
      :nav-items="navItems"
      :current-route-name="String(route.name || '')"
      :active-session-id="activeSessionId"
      :search-value="sessionSearch"
      :busy="sidebarBusy"
      :deleting-session-id="deletingSessionId"
      :session-density="preferences.sessionDensity"
      :collapsed="preferences.sidebarCollapsed"
      @create-session="createNewSession"
      @select-session="selectSession"
      @delete-session="handleDeleteSession"
      @navigate="navigateTo"
      @toggle-collapse="toggleSidebarCollapse"
      @update:search-value="sessionSearch = $event"
      @logout="handleLogout"
    />

    <div class="flex-1 flex flex-col min-w-0">
      <!-- Top header bar -->
      <header class="h-12 bg-white border-b border-zinc-100 flex items-center justify-between px-6 shrink-0">
        <span class="text-sm font-medium text-zinc-700">问答主页</span>
      </header>

      <main class="flex-1 min-h-0">
        <div v-if="pageLoading" class="flex items-center justify-center h-full">
          <div class="flex gap-1.5">
            <span class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" />
            <span class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>
        </div>
        <ChatWorkspace
          v-else
          :session="activeSession"
          :busy="isAnswering"
          :prompt="prompt"
          :provider-label="currentProviderLabel"
          :suggestions="suggestedPrompts"
          :welcome-message="activeSession.welcomeMessage"
          :send-shortcut="preferences.sendShortcut"
          :show-knowledge-tips="preferences.showKnowledgeTips"
          :answer-mode="preferences.answerMode"
          :chat-model-id="preferences.chatModelId"
          :chat-model-options="modelSettings.chatModels"
          @update:prompt="prompt = $event"
          @update:answer-mode="updateAnswerMode"
          @update:chat-model="updateChatModel"
          @submit="submitPrompt"
          @stop="stopCurrentAnswer"
          @choose-suggestion="submitPrompt"
          @open-knowledge="() => navigateTo('knowledge')"
        />
      </main>
    </div>
  </div>
</template>
