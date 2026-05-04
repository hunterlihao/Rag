<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";

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
const workspace = reactive({
  sessions: [],
});
const activeSessionId = ref("");
const sessionSearch = ref("");
const prompt = ref("");
const isAnswering = ref(false);
const isStoppingAnswer = ref(false);
const activeAnswerController = ref(null);
const activeAnswerRequestId = ref("");
const activeAnswerPrompt = ref("");
const activeAnswerExpectedMessageCount = ref(0);
const pageLoading = ref(false);
const deletingSessionId = ref("");
const welcomeMessage = ref("你好，我已经准备好结合知识库回答问题了。");
const startupError = ref("");
const sidebarBusy = computed(() => isAnswering.value || !!deletingSessionId.value);
const deleteBusyState = computed(() => ({
  visible: !!deletingSessionId.value,
  badgeText: "删除处理中",
  title: "正在删除会话",
  description: "会话记录正在清理并刷新工作区，请等待当前操作完成。",
}));
const navItems = computed(() => buildSidebarNavItems(user.value));
const dashboardGridStyle = computed(() => ({
  "--dashboard-sidebar-width": preferences.value.sidebarCollapsed ? "88px" : "320px",
}));

const filteredSessions = computed(() => {
  const keyword = sessionSearch.value.trim().toLowerCase();
  return [...workspace.sessions]
    .sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt))
    .filter((session) => {
      if (!keyword) {
        return true;
      }
      const haystack = `${session.title} ${session.preview || ""}`.toLowerCase();
      return haystack.includes(keyword);
    });
});

const activeSession = computed(() => {
  return (
    workspace.sessions.find((session) => session.id === activeSessionId.value) || {
      id: "",
      title: "新对话",
      preview: "还没有消息",
      messageCount: 0,
      updatedAt: new Date().toISOString(),
      messages: [],
      welcomeMessage: welcomeMessage.value,
    }
  );
});

const modelSettings = reactive({
  provider: appConfig.modelProvider,
  chatModel: appConfig.chatModel,
  embeddingModel: appConfig.embeddingModel,
  defaultChatModelId: "",
  chatModels: [],
});

const selectedChatModel = computed(() => {
  return (
    modelSettings.chatModels.find((item) => item.id === preferences.value.chatModelId) ||
    modelSettings.chatModels[0] ||
    null
  );
});
const currentProviderLabel = computed(() => {
  return selectedChatModel.value?.provider_label || modelSettings.provider;
});

function mergeSession(sessionPayload) {
  const session = {
    ...normalizeShellSession(sessionPayload),
    welcomeMessage: buildWelcomeMessage(sessionPayload),
  };
  const existingIndex = workspace.sessions.findIndex((item) => item.id === session.id);
  if (existingIndex >= 0) {
    workspace.sessions.splice(existingIndex, 1, session);
  } else {
    workspace.sessions.unshift(session);
  }
  workspace.sessions.sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt));
  return session;
}

async function loadSession(sessionId) {
  const detail = await fetchSessionDetail(sessionId);
  const merged = mergeSession(detail);
  activeSessionId.value = merged.id;
  welcomeMessage.value = merged.welcomeMessage;
}

function wait(milliseconds) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

async function syncStoppedSession(sessionId, expectedPrompt, expectedMessageCount) {
  const retryDelays = [120, 280, 520, 900];

  for (const delay of retryDelays) {
    await wait(delay);
    const detail = await fetchSessionDetail(sessionId);
    const messages = Array.isArray(detail?.messages) ? detail.messages : [];
    const hasExpectedPrompt = messages.some((message, index) => {
      return (
        message?.role === "user" &&
        String(message.content || "").trim() === expectedPrompt &&
        index >= Math.max(0, messages.length - 3)
      );
    });

    if (messages.length >= expectedMessageCount && hasExpectedPrompt) {
      const merged = mergeSession(detail);
      activeSessionId.value = merged.id;
      welcomeMessage.value = merged.welcomeMessage;
      return;
    }
  }

  await loadSession(sessionId);
}

async function refreshSessions(preferredSessionId = "") {
  const sessionList = await fetchSessions();
  workspace.sessions.splice(
    0,
    workspace.sessions.length,
    ...sessionList.map((session) => {
      const normalized = normalizeShellSession(session);
      return {
        ...normalized,
        welcomeMessage: buildWelcomeMessage(session),
      };
    }),
  );

  if (!workspace.sessions.length) {
    await createNewSession();
    return;
  }

  const nextSessionId =
    workspace.sessions.find((item) => item.id === preferredSessionId)?.id ||
    workspace.sessions.find((item) => item.id === activeSessionId.value)?.id ||
    workspace.sessions[0].id;
  await loadSession(nextSessionId);
}

async function createNewSession({ ignoreBusy = false } = {}) {
  if (!ignoreBusy && sidebarBusy.value) {
    return;
  }
  const session = await createSession();
  const merged = mergeSession(session);
  activeSessionId.value = merged.id;
  welcomeMessage.value = merged.welcomeMessage;
  prompt.value = "";
}

async function selectSession(sessionId) {
  if (sidebarBusy.value) {
    return;
  }
  await loadSession(sessionId);
}

async function submitPrompt(rawPrompt) {
  const content = (rawPrompt || "").trim();
  if (!content || isAnswering.value || !activeSession.value) {
    return;
  }

  if (!activeSession.value.id) {
    await createNewSession();
  }

  const optimisticSession = activeSession.value;
  const serverMessageCountBeforeSubmit = optimisticSession.messages.length;
  optimisticSession.messages = [
    ...optimisticSession.messages,
    {
      id: `local-user-${Date.now()}`,
      role: "user",
      content,
    },
  ];
  optimisticSession.messageCount = optimisticSession.messages.length;
  const assistantMessageId = `local-assistant-${Date.now()}`;
  let assistantStarted = false;
  const answerRequestId = `${activeSession.value.id}-${Date.now()}`;
  const answerController = new AbortController();
  activeAnswerRequestId.value = answerRequestId;
  activeAnswerController.value = answerController;
  activeAnswerPrompt.value = content;
  activeAnswerExpectedMessageCount.value = serverMessageCountBeforeSubmit + 2;
  isStoppingAnswer.value = false;
  prompt.value = "";
  isAnswering.value = true;

  try {
    const updatedSession = await sendPromptStream(activeSession.value.id, content, {
      answerMode: preferences.value.answerMode,
      chatModelId: preferences.value.chatModelId || modelSettings.defaultChatModelId,
      answerRequestId,
      signal: answerController.signal,
      onDelta(delta) {
        if (!assistantStarted) {
          optimisticSession.messages = [
            ...optimisticSession.messages,
            {
              id: assistantMessageId,
              role: "assistant",
              content: "",
            },
          ];
          assistantStarted = true;
        }

        const assistantMessage = optimisticSession.messages.find(
          (message) => message.id === assistantMessageId,
        );
        if (assistantMessage) {
          assistantMessage.content += delta;
          optimisticSession.messageCount = optimisticSession.messages.length;
        }
      },
    });
    mergeSession(updatedSession);
  } catch (error) {
    if (error.name === "AbortError") {
      if (isStoppingAnswer.value) {
        await syncStoppedSession(
          activeSession.value.id,
          activeAnswerPrompt.value,
          activeAnswerExpectedMessageCount.value,
        );
      } else {
        await loadSession(activeSession.value.id);
      }
      return;
    }
    await loadSession(activeSession.value.id);
    ElMessage.error(error.message || "回答失败了，请稍后重试。");
  } finally {
    if (activeAnswerRequestId.value === answerRequestId) {
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
  if (!isAnswering.value || isStoppingAnswer.value || !activeSession.value?.id) {
    return;
  }

  const answerRequestId = activeAnswerRequestId.value;
  isStoppingAnswer.value = true;
  try {
    const result = await stopPromptStream(activeSession.value.id, answerRequestId);
    activeAnswerController.value?.abort();
    if (result.stopped) {
      ElMessage.success("已停止回答");
    }
  } catch (error) {
    ElMessage.warning(error.message || "停止请求没有发送成功，已尝试中断本地连接。");
    activeAnswerController.value?.abort();
  }
}

function updateAnswerMode(answerMode) {
  preferences.value = savePreferences(
    {
      ...preferences.value,
      answerMode,
    },
    user.value,
  );
}

function updateChatModel(chatModelId) {
  preferences.value = savePreferences(
    {
      ...preferences.value,
      chatModelId,
    },
    user.value,
  );
}

function syncChatModelPreference() {
  const modelIds = modelSettings.chatModels.map((item) => item.id);
  const fallbackModelId = modelSettings.defaultChatModelId || modelIds[0] || "";
  const preferredModelId = preferences.value.chatModelId;
  if (!fallbackModelId || modelIds.includes(preferredModelId)) {
    return;
  }

  preferences.value = savePreferences(
    {
      ...preferences.value,
      chatModelId: fallbackModelId,
    },
    user.value,
  );
}

async function handleLogout() {
  await logout();
  router.push("/login");
}

async function handleDeleteSession(sessionId) {
  if (!sessionId || sidebarBusy.value) {
    return;
  }

  deletingSessionId.value = sessionId;
  try {
    const result = await deleteSession(sessionId);
    const deletedActiveSession = activeSessionId.value === sessionId;
    const remainingSessions = workspace.sessions.filter((session) => session.id !== sessionId);
    workspace.sessions.splice(0, workspace.sessions.length, ...remainingSessions);

    if (deletedActiveSession) {
      activeSessionId.value = "";
      const nextSessionId = result.next_session_id || remainingSessions[0]?.id || "";
      if (nextSessionId) {
        await loadSession(nextSessionId);
      } else {
        await createNewSession({ ignoreBusy: true });
      }
    }

    ElMessage.success(result.message || "会话已删除");
  } catch (error) {
    ElMessage.error(error.message || "删除会话失败，请稍后重试。");
  } finally {
    deletingSessionId.value = "";
  }
}

function navigateTo(name) {
  router.push(buildRouteLocation(name, activeSessionId.value));
}

function openKnowledgePage() {
  navigateTo("knowledge");
}

function toggleSidebarCollapse() {
  preferences.value = savePreferences(
    {
      ...preferences.value,
      sidebarCollapsed: !preferences.value.sidebarCollapsed,
    },
    user.value,
  );
}

watch(activeSessionId, (sessionId) => {
  if (route.name !== "workspace") {
    return;
  }

  const currentSession = typeof route.query.session === "string" ? route.query.session : "";
  if ((sessionId || "") === currentSession) {
    return;
  }

  router.replace({
    name: "workspace",
    query: sessionId ? { session: sessionId } : {},
  });
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
    if (startupError.value) {
      ElMessage.warning(startupError.value);
    }

    const preferredSessionId =
      typeof route.query.session === "string" ? route.query.session : "";
    await refreshSessions(preferredSessionId);
  } catch (error) {
    ElMessage.error(error.message || "加载工作台失败");
    if (!getCurrentUser()) {
      router.push("/login");
    }
  } finally {
    pageLoading.value = false;
  }
});
</script>

<template>
  <div v-loading="pageLoading" class="page-shell workspace-page">
    <ActionBusyOverlay
      :visible="deleteBusyState.visible"
      :badge-text="deleteBusyState.badgeText"
      :title="deleteBusyState.title"
      :description="deleteBusyState.description"
    />

    <div class="dashboard-grid" :style="dashboardGridStyle">
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

      <ChatWorkspace
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
        @open-knowledge="openKnowledgePage"
      />
    </div>
  </div>
</template>

<style scoped>
.workspace-page {
  overflow: hidden;
}

@media (max-width: 1080px) {
  .workspace-page {
    overflow: auto;
  }
}
</style>
