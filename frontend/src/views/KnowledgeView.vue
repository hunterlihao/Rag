<script setup>
import { computed, h, onMounted, reactive, ref, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { ArrowLeft, CollectionTag, Files } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import ActionBusyOverlay from "@/components/ActionBusyOverlay.vue";
import DeleteConfirmDialog from "@/components/DeleteConfirmDialog.vue";
import KnowledgeDock from "@/components/KnowledgeDock.vue";
import WorkspaceSidebar from "@/components/WorkspaceSidebar.vue";
import { getCurrentUser, logout } from "@/services/auth";
import { appConfig } from "@/services/config";
import { buildRouteLocation, buildSidebarNavItems, normalizeShellSession } from "@/services/shell";
import { getPreferences, savePreferences } from "@/services/user";
import {
  createSession,
  deleteSession,
  deleteUpload,
  deleteUploads,
  fetchBackendMeta,
  fetchSessions,
  fetchUploads,
  formatRelativeTime,
  uploadFileWithProgress,
} from "@/services/workspace";

const route = useRoute();
const router = useRouter();
const user = ref(getCurrentUser());
const preferences = ref(getPreferences(user.value));

const workspace = reactive({
  sessions: [],
  uploads: [],
});

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
const deleteDialogState = ref(createDeleteDialogState());
const navItems = computed(() => buildSidebarNavItems(user.value));
const dashboardGridStyle = computed(() => ({
  "--dashboard-sidebar-width": preferences.value.sidebarCollapsed ? "88px" : "320px",
}));

const modelSettings = reactive({
  provider: appConfig.modelProvider,
  chatModel: appConfig.chatModel,
  embeddingModel: appConfig.embeddingModel,
});

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

const latestUploadText = computed(() => {
  if (!workspace.uploads.length) {
    return "还没有导入任何文件";
  }

  return `最近导入：${formatRelativeTime(workspace.uploads[0].uploadedAt)}`;
});

const filteredUploads = computed(() => {
  const keyword = uploadSearch.value.trim().toLowerCase();
  if (!keyword) {
    return workspace.uploads;
  }

  return workspace.uploads.filter((upload) => String(upload.name || "").toLowerCase().includes(keyword));
});
const importOverlayText = computed(() => {
  if (!uploadTasks.value.length) {
    return "知识库导入中，请稍候...";
  }
  return `正在导入 ${uploadTasks.value.length} 个文件，请等待处理完成...`;
});
const busyOverlayState = computed(() => {
  if (importBusy.value) {
    return {
      visible: true,
      badgeText: "导入处理中",
      title: "正在导入知识库",
      description: importOverlayText.value,
    };
  }

  if (batchDeleting.value) {
    return {
      visible: true,
      badgeText: "删除处理中",
      title: "正在批量删除文件",
      description: "选中的知识库文件和对应向量内容正在同步清理，请等待完成。",
    };
  }

  if (deletingUploadId.value) {
    return {
      visible: true,
      badgeText: "删除处理中",
      title: "正在删除知识库文件",
      description: "文件记录和对应向量内容正在同步移除，请等待当前操作完成。",
    };
  }

  return {
    visible: !!deletingSessionId.value,
    badgeText: "删除处理中",
    title: "正在删除会话",
    description: "会话记录正在清理并刷新知识库页面关联状态，请稍候。",
  };
});

function normalizeUpload(upload) {
  return {
    id: upload.id,
    name: upload.name,
    type: upload.type,
    size: upload.size,
    status: upload.status,
    message: upload.message,
    duplicate: Boolean(upload.duplicate),
    uploadedAt: upload.uploaded_at || upload.uploadedAt || new Date().toISOString(),
    uploaderName: upload.uploader_name || upload.uploaderName || user.value?.name || "",
  };
}

const allUploadsSelected = computed(() => {
  return (
    filteredUploads.value.length > 0 &&
    filteredUploads.value.every((upload) => selectedUploadIds.value.includes(upload.id))
  );
});

const selectedUploadCount = computed(() => selectedUploadIds.value.length);
const pageBusy = computed(
  () =>
    importBusy.value ||
    batchDeleting.value ||
    !!deletingUploadId.value ||
    !!deletingSessionId.value,
);

function createDeleteDialogState() {
  return {
    title: "",
    summary: "",
    hint: "",
    items: [],
    extra: "",
    confirmText: "确认删除",
    action: null,
  };
}

function openDeleteDialog(payload) {
  deleteDialogState.value = {
    ...createDeleteDialogState(),
    ...payload,
  };
  deleteDialogVisible.value = true;
}

async function refreshSessions(preferredSessionId = "") {
  const sessionList = await fetchSessions();
  workspace.sessions.splice(
    0,
    workspace.sessions.length,
    ...sessionList.map((session) => normalizeShellSession(session)),
  );

  const nextSessionId =
    workspace.sessions.find((item) => item.id === preferredSessionId)?.id ||
    workspace.sessions.find((item) => item.id === activeSessionId.value)?.id ||
    workspace.sessions[0]?.id ||
    "";
  activeSessionId.value = nextSessionId;
}

async function refreshUploads() {
  const uploads = await fetchUploads();
  workspace.uploads.splice(0, workspace.uploads.length, ...uploads.map((item) => normalizeUpload(item)));
  const availableIds = new Set(workspace.uploads.map((item) => item.id));
  selectedUploadIds.value = selectedUploadIds.value.filter((uploadId) => availableIds.has(uploadId));
}

function openWorkspace(sessionId = activeSessionId.value) {
  if (pageBusy.value) {
    ElMessage.warning("知识库操作进行中，请等待当前处理完成后再返回问答。");
    return;
  }
  router.push(buildRouteLocation("workspace", sessionId));
}

async function createNewSession() {
  if (pageBusy.value) {
    ElMessage.warning("知识库操作进行中，请先等待当前处理完成。");
    return;
  }
  const session = await createSession();
  openWorkspace(session.id);
}

async function handleLogout() {
  await logout();
  router.push("/login");
}

async function handleDeleteSession(sessionId) {
  if (!sessionId || pageBusy.value) {
    return;
  }

  deletingSessionId.value = sessionId;
  try {
    const result = await deleteSession(sessionId);
    const deletedActiveSession = activeSessionId.value === sessionId;
    const remainingSessions = workspace.sessions.filter((session) => session.id !== sessionId);
    workspace.sessions.splice(0, workspace.sessions.length, ...remainingSessions);

    if (deletedActiveSession) {
      activeSessionId.value = result.next_session_id || remainingSessions[0]?.id || "";
    }

    ElMessage.success(result.message || "会话已删除");
  } catch (error) {
    ElMessage.error(error.message || "删除会话失败，请稍后重试。");
  } finally {
    deletingSessionId.value = "";
  }
}

function openSession(sessionId) {
  if (pageBusy.value) {
    ElMessage.warning("知识库操作进行中，请等待当前处理完成后再切换页面。");
    return;
  }
  activeSessionId.value = sessionId;
  openWorkspace(sessionId);
}

function navigateTo(name) {
  if (pageBusy.value && name !== "knowledge") {
    ElMessage.warning("知识库操作进行中，请等待当前处理完成后再切换页面。");
    return;
  }
  router.push(buildRouteLocation(name, activeSessionId.value));
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

async function showDuplicateAlert(duplicateFiles) {
  await ElMessageBox.alert(
    h("div", { class: "duplicate-dialog" }, [
      h("p", "这些文件之前已经导入过当前账号的知识库，本次不会重复写入向量库："),
      h(
        "ul",
        duplicateFiles.map((item) =>
          h("li", { key: item.id || item.name }, item.name),
        ),
      ),
    ]),
    "以下文件已导入",
    {
      confirmButtonText: "知道了",
    },
  );
}

async function importFiles(fileList) {
  if (!fileList.length || importBusy.value) {
    return;
  }

  uploadTasks.value = fileList.map((file, index) => {
    const rawFile = file.raw || file;
    return {
      id: `upload-task-${Date.now()}-${index}`,
      name: rawFile.name,
      size: rawFile.size || 0,
      progress: 0,
      status: "waiting",
      message: "等待上传",
      rawFile,
    };
  });

  importBusy.value = true;
  try {
    const uploadResults = [];

    let cursor = 0;
    async function runWorker() {
      while (cursor < uploadTasks.value.length) {
        const currentIndex = cursor;
        cursor += 1;
        const task = uploadTasks.value[currentIndex];
        task.status = "uploading";
        task.message = "正在上传到后端";

        try {
          const result = await uploadFileWithProgress(task.rawFile, {
            onProgress(ratio) {
              task.progress = Math.max(task.progress, Math.min(92, Math.round(ratio * 90)));
            },
          });

          task.status = "processing";
          task.progress = Math.max(task.progress, 95);
          task.message = "文件上传完成，正在写入知识库";

          const singleResult = result.results?.[0] || {
            name: task.name,
            status: "success",
            message: "上传成功",
            duplicate: false,
          };
          uploadResults.push(singleResult);

          task.status = singleResult.status || "success";
          task.progress = 100;
          task.message = singleResult.message || "处理完成";
        } catch (error) {
          task.status = "error";
          task.progress = 100;
          task.message = error.message || "上传失败";
          uploadResults.push({
            name: task.name,
            status: "error",
            message: task.message,
            duplicate: false,
          });
        }
      }
    }

    const workers = Array.from(
      { length: Math.min(appConfig.uploadConcurrency, uploadTasks.value.length) },
      () => runWorker(),
    );
    await Promise.all(workers);
    await refreshUploads();

    const successFiles = uploadResults.filter((item) => item.status === "success");
    const duplicateFiles = uploadResults.filter((item) => item.duplicate);
    const errorFiles = uploadResults.filter((item) => item.status === "error");

    if (successFiles.length) {
      ElMessage.success(`已导入 ${successFiles.length} 个文件到当前账号知识库`);
    }
    if (errorFiles.length) {
      ElMessage.error(`有 ${errorFiles.length} 个文件导入失败，请查看后端日志。`);
    }
    if (duplicateFiles.length) {
      await showDuplicateAlert(duplicateFiles);
    }
  } catch (error) {
    ElMessage.error(error.message || "文件导入失败，请稍后重试。");
  } finally {
    importBusy.value = false;
  }
}

async function deleteKnowledgeFile(file) {
  if (!file?.id || deletingUploadId.value || batchDeleting.value) {
    return;
  }

  openDeleteDialog({
    title: "删除知识库文件",
    confirmText: "确认删除",
    summary: `确认删除「${file.name}」吗？`,
    hint: "该文件写入当前账号知识库的向量内容会一起移除，后续问答将不再检索到相关片段。",
    items: [file],
    extra: "删除完成后，如果需要恢复，只能重新上传并重新向量化。",
    action: {
      type: "single-upload",
      file,
    },
  });
}

function updateUploadSelection({ id, checked }) {
  if (!id) {
    return;
  }

  if (checked) {
    if (!selectedUploadIds.value.includes(id)) {
      selectedUploadIds.value = [...selectedUploadIds.value, id];
    }
    return;
  }

  selectedUploadIds.value = selectedUploadIds.value.filter((uploadId) => uploadId !== id);
}

function toggleSelectAllUploads(checked) {
  const filteredIds = filteredUploads.value.map((item) => item.id);
  if (checked) {
    selectedUploadIds.value = Array.from(new Set([...selectedUploadIds.value, ...filteredIds]));
    return;
  }

  selectedUploadIds.value = selectedUploadIds.value.filter((uploadId) => !filteredIds.includes(uploadId));
}

async function batchDeleteKnowledgeFiles() {
  if (!selectedUploadIds.value.length || importBusy.value || deletingUploadId.value || batchDeleting.value) {
    return;
  }

  const selectedFiles = workspace.uploads.filter((item) => selectedUploadIds.value.includes(item.id));
  const previewFiles = selectedFiles.slice(0, 4);
  openDeleteDialog({
    title: "批量删除知识库文件",
    confirmText: "批量删除",
    summary: `确认删除已选中的 ${selectedUploadIds.value.length} 个文件吗？`,
    hint: "这些文件对应的向量内容会一起清理，后续问答将不再命中相关片段。",
    items: previewFiles,
    extra:
      selectedFiles.length > previewFiles.length
        ? `另有 ${selectedFiles.length - previewFiles.length} 个文件将一并删除。`
        : "删除完成后，这些文件关联的向量内容都会一起移除。",
    action: {
      type: "batch-upload",
      ids: [...selectedUploadIds.value],
    },
  });
}

async function confirmDeleteDialog() {
  const action = deleteDialogState.value.action;
  if (!action?.type) {
    return;
  }

  deleteDialogVisible.value = false;

  if (action.type === "single-upload" && action.file?.id) {
    deletingUploadId.value = action.file.id;
    try {
      const result = await deleteUpload(action.file.id);
      selectedUploadIds.value = selectedUploadIds.value.filter((uploadId) => uploadId !== action.file.id);
      workspace.uploads.splice(
        0,
        workspace.uploads.length,
        ...(result.uploads || []).map((item) => normalizeUpload(item)),
      );
      ElMessage.success(result.message || "知识库文件已删除");
    } catch (error) {
      ElMessage.error(error.message || "删除知识库文件失败，请稍后重试。");
    } finally {
      deletingUploadId.value = "";
    }
    return;
  }

  if (action.type === "batch-upload" && action.ids?.length) {
    batchDeleting.value = true;
    try {
      const result = await deleteUploads(action.ids);
      selectedUploadIds.value = [];
      workspace.uploads.splice(
        0,
        workspace.uploads.length,
        ...(result.uploads || []).map((item) => normalizeUpload(item)),
      );

      if (result.failed?.length) {
        ElMessage.warning(result.message || "部分文件删除失败。");
        return;
      }
      ElMessage.success(result.message || "知识库文件已批量删除");
    } catch (error) {
      ElMessage.error(error.message || "批量删除知识库文件失败，请稍后重试。");
    } finally {
      batchDeleting.value = false;
    }
  }
}

watch(activeSessionId, (sessionId) => {
  if (route.name !== "knowledge") {
    return;
  }

  const currentSession = typeof route.query.session === "string" ? route.query.session : "";
  if ((sessionId || "") === currentSession) {
    return;
  }

  router.replace({
    name: "knowledge",
    query: sessionId ? { session: sessionId } : {},
  });
});

watch(deleteDialogVisible, (value) => {
  if (!value) {
    deleteDialogState.value = createDeleteDialogState();
  }
});

onBeforeRouteLeave(() => {
  if (!pageBusy.value) {
    return true;
  }

  ElMessage.warning("知识库操作进行中，请等待当前处理完成后再离开知识库页面。");
  return false;
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
    if (startupError.value) {
      ElMessage.warning(startupError.value);
    }

    const preferredSessionId =
      typeof route.query.session === "string" ? route.query.session : "";
    await Promise.all([refreshSessions(preferredSessionId), refreshUploads()]);
  } catch (error) {
    ElMessage.error(error.message || "知识库页面加载失败。");
    if (!getCurrentUser()) {
      router.push("/login");
    }
  } finally {
    pageLoading.value = false;
  }
});
</script>

<template>
  <div v-loading="pageLoading" class="page-shell knowledge-page">
    <ActionBusyOverlay
      :visible="busyOverlayState.visible"
      :badge-text="busyOverlayState.badgeText"
      :title="busyOverlayState.title"
      :description="busyOverlayState.description"
    />

    <div class="dashboard-grid" :style="dashboardGridStyle">
      <WorkspaceSidebar
        :user="user"
        :sessions="filteredSessions"
        :nav-items="navItems"
        :current-route-name="String(route.name || '')"
        :active-session-id="activeSessionId"
        :search-value="sessionSearch"
        :busy="pageBusy"
        :deleting-session-id="deletingSessionId"
        :session-density="preferences.sessionDensity"
        :collapsed="preferences.sidebarCollapsed"
        @create-session="createNewSession"
        @select-session="openSession"
        @delete-session="handleDeleteSession"
        @navigate="navigateTo"
        @toggle-collapse="toggleSidebarCollapse"
        @update:search-value="sessionSearch = $event"
        @logout="handleLogout"
      />

      <section class="dashboard-stage">
        <header class="dashboard-hero glass-panel knowledge-hero">
          <div class="dashboard-copy knowledge-hero__copy">
            <div class="dashboard-eyebrow">独立知识库</div>
            <h1>为当前账号维护一套专属向量资料。</h1>
            <p>
              文件只会写入当前用户自己的 collection 和去重登记表。上传重复文件时会直接提醒，不会重复写入。
            </p>
          </div>

          <div class="dashboard-stats knowledge-hero__stats">
            <div class="info-tile">
              <div class="info-tile__icon">
                <el-icon><CollectionTag /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ workspace.uploads.length }}</strong>
                <span>当前账号下的独立文件总数</span>
              </div>
            </div>

            <div class="info-tile">
              <div class="info-tile__icon">
                <el-icon><Files /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ activeSessionId ? "已关联当前会话" : "暂未关联会话" }}</strong>
                <span>{{ latestUploadText }}</span>
              </div>
            </div>

            <div class="info-tile knowledge-info-tile knowledge-info-tile--action">
              <div class="info-tile__icon">
                <el-icon><ArrowLeft /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ activeSessionId ? "返回当前问答" : "返回工作台" }}</strong>
                <span>{{ activeSessionId ? "继续回到当前会话提问" : "返回问答主页开始提问" }}</span>
              </div>
              <el-button plain round :icon="ArrowLeft" :disabled="importBusy" @click="openWorkspace">
                返回问答
              </el-button>
            </div>
          </div>
        </header>

        <KnowledgeDock
          :busy="importBusy"
          :batch-deleting="batchDeleting"
          :deleting-upload-id="deletingUploadId"
          :selected-upload-ids="selectedUploadIds"
          :all-uploads-selected="allUploadsSelected"
          :selected-upload-count="selectedUploadCount"
          :total-upload-count="workspace.uploads.length"
          :upload-search="uploadSearch"
          :upload-tasks="uploadTasks"
          :uploads="filteredUploads"
          :model-settings="modelSettings"
          :page-mode="true"
          @import-files="importFiles"
          @batch-delete="batchDeleteKnowledgeFiles"
          @delete-file="deleteKnowledgeFile"
          @toggle-select-all="toggleSelectAllUploads"
          @toggle-upload="updateUploadSelection"
          @update:upload-search="uploadSearch = $event"
        />
      </section>
    </div>

    <DeleteConfirmDialog
      v-model="deleteDialogVisible"
      :title="deleteDialogState.title"
      :summary="deleteDialogState.summary"
      :hint="deleteDialogState.hint"
      :items="deleteDialogState.items"
      :extra="deleteDialogState.extra"
      :confirm-text="deleteDialogState.confirmText"
      :loading="!!deletingUploadId || batchDeleting"
      @confirm="confirmDeleteDialog"
    />
  </div>
</template>

<style scoped>
.knowledge-page {
  overflow: hidden;
}

.knowledge-hero {
  display: block;
}

.knowledge-hero__copy {
  max-width: 860px;
}

.knowledge-hero__stats {
  margin-top: 18px;
}

.knowledge-info-tile {
  justify-content: space-between;
  align-items: center;
}

.knowledge-info-tile .info-tile__copy {
  min-width: 0;
  flex: 1;
}

.knowledge-info-tile--action :deep(.el-button) {
  flex: none;
  height: 34px;
  padding-inline: 14px;
  border-color: rgba(46, 108, 246, 0.16);
  color: var(--accent);
}

@media (max-width: 1080px) {
  .knowledge-page {
    overflow: auto;
  }

  .knowledge-info-tile {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
