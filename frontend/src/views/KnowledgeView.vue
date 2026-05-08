<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
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

  const concurrency = Math.min(appConfig.uploadConcurrency || 2, files.length);
  const queue = [...files];
  const results = [];

  async function worker() {
    while (queue.length) {
      const file = queue.shift();
      if (!file) break;
      const task = tasks.find((t) => t.name === file.name && t.status === "uploading");
      if (!task) continue;
      try {
        await uploadFileWithProgress(file, {
          onProgress(ratio) {
            task.progress = Math.round(ratio * 100);
          },
        });
        task.status = "success";
        task.progress = 100;
        results.push({ name: file.name, status: "success" });
      } catch (err) {
        task.status = "error";
        results.push({ name: file.name, status: "error", message: err.message });
      }
    }
  }

  await Promise.all(Array.from({ length: concurrency }, () => worker()));
  await refreshUploads();

  const duplicates = results.filter((r) => r.status === "error" && r.message?.includes("已经处理过"));
  const errors = results.filter((r) => r.status === "error" && !r.message?.includes("已经处理过"));
  if (duplicates.length) {
    openDeleteDialog({
      title: "重复文件提示",
      tone: "primary",
      summary: `${duplicates.length} 个文件已经处理过了，已自动跳过。`,
      hint: duplicates.map((d) => d.name).join("、"),
      confirmText: "知道了",
      onConfirm: () => { deleteDialogVisible.value = false; },
    });
  } else if (errors.length) {
    openDeleteDialog({
      title: "导入失败",
      summary: `${errors.length} 个文件导入失败`,
      hint: errors.map((e) => `${e.name}: ${e.message}`).join("；"),
      confirmText: "知道了",
      onConfirm: () => { deleteDialogVisible.value = false; },
    });
  }

  setTimeout(() => {
    uploadTasks.value = uploadTasks.value.filter((t) => t.status !== "error");
    if (uploadTasks.value.every((t) => t.status === "success")) {
      uploadTasks.value = [];
    }
  }, 3000);
  importBusy.value = false;
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
  } catch {
    if (!getCurrentUser()) router.push("/login");
  } finally {
    pageLoading.value = false;
  }
});
</script>

<template>
  <div class="flex h-screen bg-[#FAFAFA]">
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
            <h1 class="text-xl font-bold text-[#0a0a0a] tracking-tight mb-1">知识库文档管理</h1>
            <p class="text-sm text-zinc-500">独立导入文件并维护当前账号向量库。支持 PDF、Word、Excel、CSV、Markdown、TXT 格式。</p>
          </div>

          <!-- Info tiles -->
          <div class="grid grid-cols-3 gap-3">
            <div class="bg-white border border-[#ebebeb] rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center">
                <Files class="w-4 h-4 text-zinc-500" />
              </div>
              <div>
                <p class="text-lg font-bold text-[#0a0a0a] numeric">{{ workspace.uploads.length }}</p>
                <p class="text-xs text-zinc-400">文件总数</p>
              </div>
            </div>
            <div class="bg-white border border-[#ebebeb] rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center">
                <Upload class="w-4 h-4 text-zinc-500" />
              </div>
              <div>
                <p class="text-xs text-zinc-600 truncate max-w-[140px]">{{ latestUploadText }}</p>
                <p class="text-xs text-zinc-400">最近活动</p>
              </div>
            </div>
            <div class="bg-white border border-[#ebebeb] rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center">
                <ArrowLeft class="w-4 h-4 text-zinc-500" />
              </div>
              <div>
                <p class="text-sm font-medium text-zinc-700">返回当前问答</p>
                <button @click="openWorkspace()" class="text-xs text-blue-600 hover:underline mt-0.5">返回问答</button>
              </div>
            </div>
          </div>

          <!-- KnowledgeDock -->
          <div class="bg-white border border-[#ebebeb] rounded-xl overflow-hidden min-h-[400px] flex flex-col">
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
  </div>
</template>
