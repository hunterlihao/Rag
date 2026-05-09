<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { ArrowLeft, Files, Upload, Loader2, AlertCircle } from "lucide-vue-next";

import ActionBusyOverlay from "@/components/ActionBusyOverlay.vue";
import DeleteConfirmDialog from "@/components/DeleteConfirmDialog.vue";
import KnowledgeDock from "@/components/KnowledgeDock.vue";
import WorkspaceSidebar from "@/components/WorkspaceSidebar.vue";
import { getCurrentUser, logout } from "@/services/auth";
import { appConfig } from "@/services/config";
import { buildRouteLocation, buildSidebarNavItems, normalizeShellSession } from "@/services/shell";
import { getPreferences, savePreferences } from "@/services/user";
import {
  createSession, deleteSession, deleteUpload, deleteUploads,
  fetchBackendMeta, fetchSessions, fetchUploads, formatRelativeTime, uploadFileWithProgress,
  connectUploadWebSocket, addUploadWsListener, removeUploadWsListener, disconnectUploadWebSocket,
} from "@/services/workspace";

const route = useRoute();
const router = useRouter();
const user = ref(getCurrentUser());
const preferences = ref(getPreferences(user.value));
const workspace = reactive({ sessions: [], uploads: [] });
const activeSessionId = ref("");
const sessionSearch = ref("");
const uploadSearch = ref("");
const pageLoading = ref(false);
const importBusy = ref(false);
const deletingUploadId = ref("");
const deletingSessionId = ref("");
const batchDeleting = ref(false);
const startupError = ref("");
const uploadTasks = ref([]);
const selectedUploadIds = ref([]);
const deleteDialogVisible = ref(false);
const deleteDialogState = ref({ tone: "danger", title: "", summary: "", hint: "", items: [], extra: "", confirmText: "确认删除", onConfirm: null });
const successDialogVisible = ref(false);
const successDialogState = ref({ title: "", message: "", items: [] });

const sidebarBusy = computed(() => importBusy.value || batchDeleting.value || !!deletingUploadId.value || !!deletingSessionId.value);
const navItems = computed(() => buildSidebarNavItems(user.value));
const pageBusy = computed(() => importBusy.value || batchDeleting.value || !!deletingUploadId.value || !!deletingSessionId.value);

const filteredSessions = computed(() => {
  const kw = sessionSearch.value.trim().toLowerCase();
  return [...workspace.sessions]
    .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
    .filter((s) => !kw || `${s.title} ${s.preview || ""}`.toLowerCase().includes(kw));
});

const filteredUploads = computed(() => {
  const kw = uploadSearch.value.trim().toLowerCase();
  if (!kw) return [...workspace.uploads];
  return workspace.uploads.filter((u) =>
    (u.name || "").toLowerCase().includes(kw) ||
    (u.type || "").toLowerCase().includes(kw)
  );
});

const allUploadsSelected = computed(() =>
  filteredUploads.value.length > 0 && filteredUploads.value.every((u) => selectedUploadIds.value.includes(u.id))
);

const selectedUploadCount = computed(() => selectedUploadIds.value.length);

const modelSettings = reactive({
  provider: appConfig.modelProvider,
  chatModel: appConfig.chatModel,
  embeddingModel: appConfig.embeddingModel,
});

const latestUploadText = computed(() => {
  if (!workspace.uploads.length) return "还没有导入任何文件";
  const latest = [...workspace.uploads].sort((a, b) => new Date(b.uploaded_at || 0) - new Date(a.uploaded_at || 0))[0];
  return `最近导入：${formatRelativeTime(latest.uploaded_at)}`;
});

const busyOverlayState = computed(() => {
  if (importBusy.value) return { visible: true, badgeText: "导入中", title: "正在导入文件", description: "文件正在上传并写入向量库，请等待完成。" };
  if (batchDeleting.value) return { visible: true, badgeText: "删除中", title: "正在批量删除", description: "知识库文件正在移除，请等待完成。" };
  if (deletingUploadId.value) return { visible: true, badgeText: "删除中", title: "正在删除文件", description: "文件正在从向量库中移除。" };
  if (deletingSessionId.value) return { visible: true, badgeText: "删除处理中", title: "正在删除会话", description: "会话记录正在清理。" };
  return { visible: false, badgeText: "", title: "", description: "" };
});

function normalizeUpload(upload) {
  return {
    ...upload,
    name: upload.name || upload.filename || "未命名文件",
    type: upload.type || upload.content_type || "unknown",
    size: upload.size ?? upload.size_bytes ?? 0,
    uploaded_at: upload.uploaded_at || upload.created_at || upload.createdAt,
  };
}

async function refreshSessions(preferredId = "") {
  const list = await fetchSessions();
  workspace.sessions = list.map((s) => ({ ...normalizeShellSession(s), welcomeMessage: "" }));
  if (!workspace.sessions.length) return;
  const nextId = workspace.sessions.find((s) => s.id === preferredId)?.id || workspace.sessions.find((s) => s.id === activeSessionId.value)?.id || workspace.sessions[0].id;
  activeSessionId.value = nextId;
}

async function refreshUploads() {
  const list = await fetchUploads();
  workspace.uploads = list.map(normalizeUpload);
  selectedUploadIds.value = selectedUploadIds.value.filter((id) => workspace.uploads.some((u) => u.id === id));
}

function openWorkspace(sessionId) {
  if (pageBusy.value) return;
  router.push(buildRouteLocation("workspace", sessionId || activeSessionId.value));
}

async function createNewSession() {
  if (pageBusy.value) return;
  const session = await createSession();
  workspace.sessions.unshift({ ...normalizeShellSession(session), welcomeMessage: "" });
  activeSessionId.value = session.id;
  router.push(buildRouteLocation("workspace", session.id));
}

function navigateTo(name) {
  if (pageBusy.value && name !== "knowledge") return;
  router.push(buildRouteLocation(name, activeSessionId.value));
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
    workspace.sessions = workspace.sessions.filter((s) => s.id !== sessionId);
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = result.next_session_id || workspace.sessions[0]?.id || "";
    }
  } finally {
    deletingSessionId.value = "";
  }
}

function toggleSidebarCollapse() {
  preferences.value = savePreferences({ ...preferences.value, sidebarCollapsed: !preferences.value.sidebarCollapsed }, user.value);
}

function openDeleteDialog(payload) {
  deleteDialogState.value = {
    tone: payload.tone || "danger",
    title: payload.title || "删除确认",
    summary: payload.summary || "",
    hint: payload.hint || "",
    items: payload.items || [],
    extra: payload.extra || "",
    confirmText: payload.confirmText || "确认删除",
    onConfirm: payload.onConfirm || (() => {}),
  };
  deleteDialogVisible.value = true;
}

async function importFiles(fileList) {
  const files = Array.from(fileList);
  if (!files.length) return;
  importBusy.value = true;

  const tasks = files.map((f, i) => ({
    id: `task-${Date.now()}-${i}`,
    name: f.name,
    filename: f.name,
    size: f.size,
    progress: 0,
    status: "uploading",
  }));
  uploadTasks.value = [...uploadTasks.value, ...tasks];

  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  try {
    const result = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        const totalPct = Math.round((e.loaded / e.total) * 90);
        uploadTasks.value.forEach((t) => {
          if (t.status === "uploading") {
            // 按文件大小比例分配进度，避免所有文件进度完全一致
            const ratio = totalSize > 0 ? t.size / totalSize : 1 / files.length;
            const filePct = Math.round(totalPct * Math.min(ratio * files.length, 1));
            t.progress = Math.max(t.progress, Math.min(filePct, 90));
          }
        });
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          try { reject(new Error(JSON.parse(xhr.responseText).detail || "上传失败")); }
          catch { reject(new Error("上传失败")); }
        }
      };
      xhr.onerror = () => reject(new Error("网络错误"));
      const session = JSON.parse(sessionStorage.getItem("rag.frontend.session") || "null");
      xhr.open("POST", `${appConfig.apiBaseUrl}/uploads`);
      if (session?.token) xhr.setRequestHeader("Authorization", `Bearer ${session.token}`);
      xhr.send(formData);
    });

    if (result.tasks) {
      result.tasks.forEach((task) => {
        const localTask = uploadTasks.value.find((t) => t.name === task.filename && t.status === "uploading");
        if (localTask) {
          localTask.id = task.task_id;
          localTask.status = task.status;
          localTask.message = task.message;
          if (task.status === "processing") {
            localTask.progress = Math.max(localTask.progress, 90);
            pendingTaskIds.value.add(task.task_id);
          } else if (task.status === "success" || task.status === "error" || task.status === "warning" || task.status === "duplicate") {
            localTask.progress = 100;
          }
        }
      });
    }

    if (uploadTasks.value.every((t) => t.status !== "uploading" && t.status !== "processing")) {
      await refreshUploads();
    }
  } catch (err) {
    console.error("Upload failed:", err);
    uploadTasks.value.forEach((t) => {
      if (t.status === "uploading") { t.status = "error"; t.message = err.message; }
    });
  } finally {
    importBusy.value = false;
  }
}

function deleteKnowledgeFile(file) {
  openDeleteDialog({
    title: "删除知识库文件",
    summary: `确认删除「${file.name}」吗？`,
    hint: "文件将从向量库中移除，对应对话引用将无法检索。",
    items: [{ id: file.id, name: file.name }],
    extra: "删除后不可恢复。",
    onConfirm: async () => {
      deleteDialogVisible.value = false;
      deletingUploadId.value = file.id;
      try {
        await deleteUpload(file.id);
        await refreshUploads();
      } finally {
        deletingUploadId.value = "";
      }
    },
  });
}

function batchDeleteKnowledgeFiles() {
  const ids = [...selectedUploadIds.value];
  if (!ids.length) return;
  const items = ids.map((id) => {
    const u = workspace.uploads.find((up) => up.id === id);
    return { id, name: u?.name || id };
  }).slice(0, 4);
  openDeleteDialog({
    title: "批量删除文件",
    summary: `确认删除 ${ids.length} 个知识库文件吗？`,
    items,
    extra: ids.length > 4 ? `...等共 ${ids.length} 个文件` : "",
    onConfirm: async () => {
      deleteDialogVisible.value = false;
      batchDeleting.value = true;
      try {
        await deleteUploads(ids);
        selectedUploadIds.value = [];
        await refreshUploads();
      } finally {
        batchDeleting.value = false;
      }
    },
  });
}

function updateUploadSelection({ id, checked }) {
  if (checked) {
    if (!selectedUploadIds.value.includes(id)) selectedUploadIds.value = [...selectedUploadIds.value, id];
  } else {
    selectedUploadIds.value = selectedUploadIds.value.filter((x) => x !== id);
  }
}

function toggleSelectAllUploads(checked) {
  selectedUploadIds.value = checked ? filteredUploads.value.map((u) => u.id) : [];
}

watch(activeSessionId, (id) => {
  if (route.name !== "knowledge") return;
  const q = typeof route.query.session === "string" ? route.query.session : "";
  if ((id || "") === q) return;
  router.replace({ name: "knowledge", query: id ? { session: id } : {} });
});

watch(deleteDialogVisible, (v) => { if (!v) deleteDialogState.value.onConfirm = null; });
watch(successDialogVisible, (v) => {
  if (!v) {
    successDialogState.value.title = "";
    successDialogState.value.message = "";
    successDialogState.value.items = [];
  }
});

// 处理 WebSocket 消息
const pendingTaskIds = ref(new Set());
let pendingSuccessCount = 0;
const pendingSuccessFiles = ref([]);

function handleUploadWsMessage(data) {
  if (data.type === "upload_progress") {
    const task = uploadTasks.value.find((t) => t.id === data.task_id);
    if (task) {
      // 后端 progress 是处理阶段进度(0-100)，映射到 90-100 区间
      const backendProgress = typeof data.progress === "number" ? data.progress : 50;
      const mappedProgress = 90 + Math.round(backendProgress * 0.1);
      task.progress = Math.max(task.progress, mappedProgress);
      task.status = "processing";
    }
  } else if (data.type === "upload_complete") {
    const task = uploadTasks.value.find((t) => t.id === data.task_id);
    if (task) {
      task.status = data.status;
      task.message = data.message;
      task.progress = data.status === "success" ? 100 : task.progress;
    }

    if (data.status === "success" && data.upload) {
      refreshUploads();
      pendingSuccessCount++;
      // 记录成功的文件名（优先从 uploadTasks 获取，后备从 data.upload 获取）
      const task = uploadTasks.value.find((t) => t.id === data.task_id);
      const fileName = task?.name || data.upload?.name || data.upload?.filename || "";
      if (fileName) {
        pendingSuccessFiles.value.push(fileName);
      }
    }

    pendingTaskIds.value.delete(data.task_id);

    if (pendingTaskIds.value.size === 0 && pendingSuccessCount > 0) {
      const count = pendingSuccessCount;
      const fileNames = [...pendingSuccessFiles.value];
      pendingSuccessCount = 0;
      pendingSuccessFiles.value = [];
      
      // 构建成功消息
      let message = "";
      const items = fileNames.map((name) => ({ name }));
      if (count === 1) {
        message = fileNames.length ? `「${fileNames[0]}」已成功导入知识库` : "文件已成功导入知识库";
      } else {
        message = `${count} 个文件已成功导入知识库`;
      }
      
      successDialogState.value = {
        title: "导入成功",
        message,
        items,
      };
      successDialogVisible.value = true;
    }

    setTimeout(() => {
      uploadTasks.value = uploadTasks.value.filter((t) => 
        t.status !== "success" && 
        t.status !== "error" && 
        t.status !== "warning" && 
        t.status !== "duplicate"  // 重复文件也在5秒后清理
      );
    }, 5000);
  }
}

onBeforeRouteLeave((to, from, next) => {
  if (pageBusy.value) {
    if (!confirm("知识库操作正在进行，确定要离开当前页面吗？")) return next(false);
  }
  next();
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
    startupError.value = meta.startup_error || "";
    const preferredId = typeof route.query.session === "string" ? route.query.session : "";
    await refreshSessions(preferredId);
    await refreshUploads();

    // 连接 WebSocket 接收上传进度
    connectUploadWebSocket();
    addUploadWsListener(handleUploadWsMessage);
  } catch {
    if (!getCurrentUser()) router.push("/login");
  } finally {
    pageLoading.value = false;
  }
});

// 组件卸载时断开 WebSocket
onUnmounted(() => {
  removeUploadWsListener(handleUploadWsMessage);
  disconnectUploadWebSocket();
});
</script>

<template>
  <div class="flex h-screen bg-zinc-50">
    <ActionBusyOverlay v-bind="busyOverlayState" />

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
      @select-session="(id) => openWorkspace(id)"
      @delete-session="handleDeleteSession"
      @navigate="navigateTo"
      @toggle-collapse="toggleSidebarCollapse"
      @update:search-value="sessionSearch = $event"
      @logout="handleLogout"
    />

    <div class="flex-1 flex flex-col min-w-0">
      <header class="h-12 bg-white border-b border-zinc-100 flex items-center justify-between px-6 shrink-0">
        <div class="flex items-center gap-2">
          <button @click="openWorkspace()" class="flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-700 transition-colors">
            <ArrowLeft class="w-4 h-4" /> 返回问答
          </button>
          <span class="text-zinc-300">/</span>
          <span class="text-sm font-medium text-zinc-700">知识库管理</span>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto">
        <div v-if="pageLoading" class="flex items-center justify-center h-full">
          <Loader2 class="w-6 h-6 text-zinc-300 animate-spin" />
        </div>

        <div v-else class="max-w-6xl mx-auto px-6 py-6 space-y-6">
          <!-- Hero -->
          <div>
            <span class="inline-flex items-center px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-500 text-xs font-medium mb-3">独立知识库</span>
            <h1 class="text-xl font-bold text-zinc-900 tracking-tight mb-1">知识库文档管理</h1>
            <p class="text-sm text-zinc-500">独立导入文件并维护当前账号向量库。支持 PDF、Word、Excel、CSV、Markdown、TXT 格式。</p>
          </div>

          <!-- Info tiles -->
          <div class="grid grid-cols-3 gap-3">
            <div class="bg-white border border-zinc-200 rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center">
                <Files class="w-4 h-4 text-zinc-500" />
              </div>
              <div>
                <p class="text-lg font-bold text-zinc-900 numeric">{{ workspace.uploads.length }}</p>
                <p class="text-xs text-zinc-400">文件总数</p>
              </div>
            </div>
            <div class="bg-white border border-zinc-200 rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center">
                <Upload class="w-4 h-4 text-zinc-500" />
              </div>
              <div>
                <p class="text-xs text-zinc-600 truncate max-w-[140px]">{{ latestUploadText }}</p>
                <p class="text-xs text-zinc-400">最近活动</p>
              </div>
            </div>
            <div class="bg-white border border-zinc-200 rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center">
                <ArrowLeft class="w-4 h-4 text-zinc-500" />
              </div>
              <div>
                <p class="text-sm font-medium text-zinc-700">返回当前问答</p>
                <button @click="openWorkspace()" class="text-xs text-zinc-900 hover:underline mt-0.5">返回问答</button>
              </div>
            </div>
          </div>

          <!-- KnowledgeDock -->
          <div class="bg-white border border-zinc-200 rounded-xl overflow-hidden min-h-[400px] flex flex-col">
            <KnowledgeDock
              :busy="importBusy"
              :upload-tasks="uploadTasks"
              :uploads="filteredUploads"
              :total-upload-count="workspace.uploads.length"
              :model-settings="modelSettings"
              :page-mode="true"
              :deleting-upload-id="deletingUploadId"
              :batch-deleting="batchDeleting"
              :selected-upload-ids="selectedUploadIds"
              :all-uploads-selected="allUploadsSelected"
              :selected-upload-count="selectedUploadCount"
              :upload-search="uploadSearch"
              @import-files="importFiles"
              @delete-file="deleteKnowledgeFile"
              @batch-delete="batchDeleteKnowledgeFiles"
              @toggle-select-all="toggleSelectAllUploads"
              @toggle-upload="updateUploadSelection"
              @update:upload-search="uploadSearch = $event"
            />
          </div>
        </div>
      </div>
    </div>

    <DeleteConfirmDialog
      v-model="deleteDialogVisible"
      :tone="deleteDialogState.tone"
      :title="deleteDialogState.title"
      :summary="deleteDialogState.summary"
      :hint="deleteDialogState.hint"
      :items="deleteDialogState.items"
      :extra="deleteDialogState.extra"
      :confirm-text="deleteDialogState.confirmText"
      @confirm="deleteDialogState.onConfirm?.()"
    />

    <!-- 上传成功提示对话框 -->
    <DeleteConfirmDialog
      v-model="successDialogVisible"
      tone="success"
      :title="successDialogState.title"
      :summary="successDialogState.message"
      :items="successDialogState.items"
      badge-text="文件导入成功"
      confirm-text="知道了"
      @confirm="successDialogVisible = false"
    />
  </div>
</template>
