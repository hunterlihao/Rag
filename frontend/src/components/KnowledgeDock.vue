<script setup>
import { computed, ref } from "vue";
import {
  Cpu,
  Delete,
  DocumentAdd,
  Files,
  Search,
  UploadFilled,
} from "@element-plus/icons-vue";

const props = defineProps({
  busy: {
    type: Boolean,
    default: false,
  },
  uploadTasks: {
    type: Array,
    default: () => [],
  },
  uploads: {
    type: Array,
    default: () => [],
  },
  totalUploadCount: {
    type: Number,
    default: 0,
  },
  modelSettings: {
    type: Object,
    required: true,
  },
  pageMode: {
    type: Boolean,
    default: false,
  },
  deletingUploadId: {
    type: String,
    default: "",
  },
  batchDeleting: {
    type: Boolean,
    default: false,
  },
  selectedUploadIds: {
    type: Array,
    default: () => [],
  },
  allUploadsSelected: {
    type: Boolean,
    default: false,
  },
  selectedUploadCount: {
    type: Number,
    default: 0,
  },
  uploadSearch: {
    type: String,
    default: "",
  },
});

const emit = defineEmits([
  "import-files",
  "delete-file",
  "batch-delete",
  "toggle-select-all",
  "toggle-upload",
  "update:upload-search",
]);

const draftFiles = ref([]);

const operationBusy = computed(() => props.busy || props.batchDeleting || !!props.deletingUploadId);
const canImport = computed(() => !operationBusy.value && draftFiles.value.length > 0);
const draftFileCount = computed(() => draftFiles.value.length);
const busyNotice = computed(() => {
  if (props.batchDeleting || props.deletingUploadId) {
    return "知识库内容正在删除中，上传入口已暂时锁定。";
  }
  return props.pageMode
    ? "文件正在写入当前账号知识库，上传入口已暂时锁定。"
    : "模型正在回答中，文件上传已暂时锁定。";
});
const panelTitle = computed(() => (props.pageMode ? "知识库管理" : "知识区"));
const panelSubtitle = computed(() => {
  return props.pageMode
    ? "上传文件、查看导入历史，并维护当前账号的专属向量知识库。"
    : "上传文件、查看模型信息，并直接写入当前知识库。";
});
const uploadListHeight = computed(() => (props.pageMode ? 180 : 240));
const uploadQueueHeight = computed(() => (props.pageMode ? 220 : 180));
const uploadEmptyDescription = computed(() => {
  if (props.totalUploadCount > 0 && props.uploadSearch.trim()) {
    return "没有匹配的文件";
  }
  return "还没有导入文件";
});
const uploadEmptyHint = computed(() => {
  if (props.totalUploadCount > 0 && props.uploadSearch.trim()) {
    return "可以调整关键词后重新搜索。";
  }
  return "可继续上传 PDF / Word / Excel / CSV / Markdown / TXT 文件。";
});
const visibleUploadCountLabel = computed(() => {
  if (props.uploadSearch.trim()) {
    return `匹配 ${props.uploads.length} / ${props.totalUploadCount}`;
  }
  return `共 ${props.totalUploadCount} 个文件`;
});
const selectedUploadSummary = computed(() => {
  if (props.selectedUploadCount > 0) {
    return `已选 ${props.selectedUploadCount} 个文件`;
  }
  return "支持批量删除已选文件";
});

function resolveFileLabel(file) {
  const name = String(file?.name || "");
  const parts = name.split(".");
  const extension = parts.length > 1 ? parts.pop() : "";
  if (extension) {
    return extension.toUpperCase().slice(0, 5);
  }

  const mime = String(file?.type || "");
  if (mime.includes("pdf")) return "PDF";
  if (mime.includes("word")) return "DOC";
  if (mime.includes("sheet") || mime.includes("excel")) return "XLS";
  if (mime.includes("csv")) return "CSV";
  if (mime.includes("text")) return "TXT";
  return "FILE";
}

function resolveFileTypeText(file) {
  const label = resolveFileLabel(file);
  if (["XLS", "XLSX"].includes(label)) return "Excel 表格";
  if (["CSV"].includes(label)) return "CSV 文件";
  if (["MD"].includes(label)) return "Markdown 文档";
  if (["PDF"].includes(label)) return "PDF 文档";
  if (["DOC", "DOCX"].includes(label)) return "Word 文档";
  if (["TXT"].includes(label)) return "文本文件";
  return "普通文件";
}

function handleImport() {
  if (!canImport.value) {
    return;
  }
  emit("import-files", [...draftFiles.value]);
  draftFiles.value = [];
}

function requestDelete(file) {
  if (props.deletingUploadId || props.batchDeleting) {
    return;
  }
  emit("delete-file", file);
}

function toggleUpload(file, checked) {
  emit("toggle-upload", {
    id: file.id,
    checked,
  });
}

function resolveTaskLabel(status) {
  return {
    waiting: "排队中",
    uploading: "上传中",
    processing: "入库中",
    success: "已完成",
    warning: "已跳过",
    error: "失败",
  }[status] || "处理中";
}

function resolveProgressStatus(status) {
  if (status === "success") {
    return "success";
  }
  if (status === "error") {
    return "exception";
  }
  return "";
}
</script>

<template>
  <aside class="knowledge-dock soft-card" :class="{ 'knowledge-dock--page': pageMode }">
    <div class="knowledge-dock__header">
      <div>
        <div class="section-title">{{ panelTitle }}</div>
        <div class="section-subtitle">{{ panelSubtitle }}</div>
      </div>
      <div class="badge-chip">RAG</div>
    </div>

    <div class="knowledge-stage">
      <el-alert
        v-if="operationBusy"
        class="knowledge-stage__alert"
        type="info"
        :closable="false"
        show-icon
        :title="busyNotice"
      />

      <section class="knowledge-panel">
        <div class="knowledge-panel__head">
          <div>
            <div class="knowledge-panel__title">导入文件</div>
            <div class="knowledge-panel__subtitle">支持一次选择多个文件，并按配置并发写入当前账号知识库。</div>
          </div>
          <div class="knowledge-panel__meta">
            <span class="knowledge-pill">{{ draftFileCount ? `待导入 ${draftFileCount}` : "支持并发导入" }}</span>
          </div>
        </div>

        <div class="knowledge-upload-grid" :class="{ 'knowledge-upload-grid--single': !pageMode }">
          <div class="knowledge-upload-main">
            <el-upload
              v-model:file-list="draftFiles"
              drag
              multiple
              :auto-upload="false"
              accept=".pdf,.docx,.xlsx,.xls,.csv,.md,.txt"
              :disabled="operationBusy"
              class="knowledge-dock__upload"
            >
              <el-icon class="knowledge-dock__upload-icon"><UploadFilled /></el-icon>
              <div class="knowledge-dock__upload-title">拖入文件到这里，或者点击选择</div>
              <div class="knowledge-dock__upload-subtitle">支持 PDF / Word / Excel / CSV / Markdown / TXT</div>
            </el-upload>

            <div class="knowledge-upload-actions">
              <div class="knowledge-upload-caption">
                <strong>{{ draftFileCount ? `已选择 ${draftFileCount} 个文件` : "准备导入你的资料" }}</strong>
                <span>重复文件会直接提醒，不会重复写入向量库。</span>
              </div>
              <el-button
                type="primary"
                class="knowledge-dock__import"
                :icon="DocumentAdd"
                :disabled="!canImport"
                @click="handleImport"
              >
                导入到知识区
              </el-button>
            </div>
          </div>

          <div class="knowledge-upload-side">
            <div class="knowledge-side-card">
              <div class="knowledge-side-card__head">
                <strong>{{ uploadTasks.length ? "导入进度" : "导入说明" }}</strong>
                <span>{{ uploadTasks.length ? `任务 ${uploadTasks.length}` : "专属知识库" }}</span>
              </div>

              <template v-if="uploadTasks.length">
                <el-scrollbar :max-height="uploadQueueHeight">
                  <div class="upload-queue">
                    <div v-for="task in uploadTasks" :key="task.id" class="upload-task">
                      <div class="upload-task__head">
                        <strong>{{ task.name }}</strong>
                        <el-tag
                          size="small"
                          effect="plain"
                          :type="task.status === 'error' ? 'danger' : task.status === 'success' ? 'success' : task.status === 'warning' ? 'warning' : 'info'"
                        >
                          {{ resolveTaskLabel(task.status) }}
                        </el-tag>
                      </div>

                      <div class="upload-task__meta">
                        {{ (task.size / 1024).toFixed(1) }} KB
                        <span v-if="task.message">· {{ task.message }}</span>
                      </div>

                      <el-progress
                        :percentage="task.progress"
                        :stroke-width="10"
                        :status="resolveProgressStatus(task.status)"
                        :show-text="true"
                      />
                    </div>
                  </div>
                </el-scrollbar>
              </template>

              <div v-else class="knowledge-rule-list">
                <div class="knowledge-rule-item">
                  <strong>账户隔离</strong>
                  <span>文件只写入当前登录用户自己的 collection。</span>
                </div>
                <div class="knowledge-rule-item">
                  <strong>重复检测</strong>
                  <span>导入过的同名同内容文件会直接提示，不重复入库。</span>
                </div>
                <div class="knowledge-rule-item">
                  <strong>向量检索</strong>
                  <span>当前会结合 Embedding 和余弦相似度完成召回。</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="knowledge-panel">
        <div class="knowledge-panel__head knowledge-panel__head--library">
          <div>
            <div class="knowledge-panel__title knowledge-panel__title--inline">
              <el-icon><Files /></el-icon>
              <span>已导入文件</span>
            </div>
            <div class="knowledge-panel__subtitle">支持按文件名搜索，删除时会同步移除对应的向量内容。</div>
          </div>
          <div class="knowledge-panel__meta knowledge-panel__meta--library">
            <span class="knowledge-pill">{{ visibleUploadCountLabel }}</span>
            <span class="knowledge-pill knowledge-pill--soft">{{ selectedUploadSummary }}</span>
          </div>
        </div>

        <div class="knowledge-library-toolbar">
          <el-input
            :model-value="uploadSearch"
            clearable
            class="knowledge-library-toolbar__search"
            placeholder="按文件名称搜索"
            :prefix-icon="Search"
            @update:model-value="emit('update:upload-search', $event)"
          />

          <div v-if="pageMode && (uploads.length || totalUploadCount)" class="knowledge-dock__bulk-actions">
            <el-checkbox
              :model-value="allUploadsSelected"
              :disabled="busy || batchDeleting || !!deletingUploadId"
              @update:model-value="emit('toggle-select-all', $event)"
            >
              全选
            </el-checkbox>
            <el-button
              plain
              size="small"
              :icon="Delete"
              :loading="batchDeleting"
              :disabled="busy || batchDeleting || !!deletingUploadId || selectedUploadCount === 0"
              @click="emit('batch-delete')"
            >
              批量删除
            </el-button>
          </div>
        </div>

        <template v-if="pageMode">
          <div v-if="uploads.length" class="upload-list upload-list--page">
            <div v-for="file in uploads" :key="file.id" class="upload-item upload-item--page-card">
              <el-checkbox
                class="upload-item__checkbox"
                :model-value="selectedUploadIds.includes(file.id)"
                :disabled="busy || batchDeleting || (!!deletingUploadId && deletingUploadId !== file.id)"
                @update:model-value="toggleUpload(file, $event)"
              />
              <div class="upload-item__body upload-item__body--stacked">
                <strong class="upload-item__name">{{ file.name }}</strong>
                <div class="upload-item__type">{{ resolveFileTypeText(file) }}</div>
                <div class="upload-item__size">{{ (file.size / 1024).toFixed(1) }} KB</div>
              </div>
              <div class="upload-item__actions upload-item__actions--floating">
                <el-button
                  circle
                  plain
                  :icon="Delete"
                  class="upload-item__delete"
                  :loading="deletingUploadId === file.id"
                  :disabled="busy || batchDeleting || (!!deletingUploadId && deletingUploadId !== file.id)"
                  @click="requestDelete(file)"
                />
              </div>
            </div>
          </div>

          <div v-else class="upload-empty-card upload-empty-card--page">
            <div class="upload-empty-card__icon">
              <el-icon><Files /></el-icon>
            </div>
            <div class="upload-empty-card__copy">
              <strong>{{ uploadEmptyDescription }}</strong>
              <span>{{ uploadEmptyHint }}</span>
            </div>
          </div>
        </template>

        <template v-else>
          <el-scrollbar v-if="uploads.length" :max-height="uploadListHeight">
            <div class="upload-list">
              <div v-for="file in uploads" :key="file.id" class="upload-item">
                <div class="upload-item__body">
                  <strong>{{ file.name }}</strong>
                  <div class="upload-item__meta">
                    {{ (file.size / 1024).toFixed(1) }} KB · {{ file.status || "success" }}
                  </div>
                </div>
                <div class="upload-item__actions">
                  <el-tag effect="plain" round>{{ file.type || "unknown" }}</el-tag>
                </div>
              </div>
            </div>
          </el-scrollbar>

          <div v-else class="upload-empty-card">
            <div class="upload-empty-card__icon">
              <el-icon><Files /></el-icon>
            </div>
            <div class="upload-empty-card__copy">
              <strong>{{ uploadEmptyDescription }}</strong>
              <span>{{ uploadEmptyHint }}</span>
            </div>
          </div>
        </template>
      </section>

      <section class="knowledge-panel">
        <div class="knowledge-panel__head">
          <div>
            <div class="knowledge-panel__title knowledge-panel__title--inline">
              <el-icon><Cpu /></el-icon>
              <span>模型与后端</span>
            </div>
            <div class="knowledge-panel__subtitle">当前问答模型、向量模型和服务来源。</div>
          </div>
        </div>

        <div class="model-card-grid">
          <article class="model-card">
            <label>问答模型</label>
            <strong>{{ modelSettings.chatModel }}</strong>
            <span>当前负责生成回答的主模型</span>
          </article>
          <article class="model-card">
            <label>Embedding 模型</label>
            <strong>{{ modelSettings.embeddingModel }}</strong>
            <span>当前负责向量化与检索的模型</span>
          </article>
          <article class="model-card">
            <label>模型来源</label>
            <strong>{{ modelSettings.provider }}</strong>
            <span>当前启用的问答服务来源</span>
          </article>
        </div>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.knowledge-dock {
  height: calc(100vh - 48px);
  padding: 22px 20px 20px;
  border-radius: 28px;
  display: flex;
  flex-direction: column;
}

.knowledge-dock--page {
  width: 100%;
  height: auto;
  min-height: 0;
  padding: 22px;
}

.knowledge-dock__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.knowledge-stage {
  display: grid;
  gap: 16px;
  margin-top: 16px;
}

.knowledge-panel {
  display: grid;
  gap: 14px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(31, 74, 160, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(246, 250, 255, 0.94));
  box-shadow: 0 12px 30px rgba(31, 64, 128, 0.04);
}

.knowledge-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.knowledge-panel__head--library {
  align-items: center;
}

.knowledge-panel__title {
  font-size: 1rem;
  font-weight: 800;
  color: var(--ink);
}

.knowledge-panel__title--inline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.knowledge-panel__subtitle {
  margin-top: 6px;
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1.6;
}

.knowledge-panel__meta,
.knowledge-dock__bulk-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.knowledge-panel__meta--library {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.knowledge-pill {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(46, 108, 246, 0.12);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 700;
}

.knowledge-pill--soft {
  background: rgba(31, 74, 160, 0.06);
  color: var(--muted);
}

.knowledge-upload-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.85fr);
  gap: 14px;
}

.knowledge-upload-grid--single {
  grid-template-columns: 1fr;
}

.knowledge-upload-main,
.knowledge-upload-side,
.knowledge-side-card {
  display: grid;
  gap: 12px;
}

.knowledge-dock__upload {
  margin: 0;
}

.knowledge-dock__upload :deep(.el-upload) {
  display: block;
}

.knowledge-dock__upload :deep(.el-upload-dragger) {
  min-height: 220px;
  border-radius: 22px;
  border: 1px dashed rgba(46, 108, 246, 0.18);
  background:
    radial-gradient(circle at top, rgba(105, 154, 255, 0.16), transparent 42%),
    linear-gradient(180deg, rgba(249, 252, 255, 0.98), rgba(241, 247, 255, 0.92));
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.knowledge-dock__upload :deep(.el-upload-dragger:hover) {
  transform: translateY(-1px);
  border-color: rgba(46, 108, 246, 0.32);
  box-shadow: 0 12px 30px rgba(46, 108, 246, 0.08);
}

.knowledge-dock__upload-icon {
  font-size: 38px;
  color: var(--accent);
}

.knowledge-dock__upload-title {
  margin-top: 12px;
  font-size: 1rem;
  font-weight: 700;
  color: var(--ink);
}

.knowledge-dock__upload-subtitle {
  margin-top: 8px;
  color: var(--muted);
  font-size: 0.86rem;
}

.knowledge-upload-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.knowledge-upload-caption {
  display: grid;
  gap: 4px;
}

.knowledge-upload-caption strong {
  font-size: 0.94rem;
  color: var(--ink);
}

.knowledge-upload-caption span {
  color: var(--muted);
  font-size: 0.82rem;
}

.knowledge-dock__import {
  height: 42px;
  min-width: 148px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #1d4dcc, #326cf2);
}

.knowledge-side-card {
  height: 100%;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(31, 74, 160, 0.08);
  background: rgba(244, 248, 255, 0.92);
}

.knowledge-side-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-side-card__head strong {
  font-size: 0.94rem;
  color: var(--ink);
}

.knowledge-side-card__head span {
  color: var(--muted);
  font-size: 0.8rem;
}

.knowledge-rule-list {
  display: grid;
  gap: 12px;
}

.knowledge-rule-item {
  display: grid;
  gap: 4px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(31, 74, 160, 0.08);
}

.knowledge-rule-item:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.knowledge-rule-item strong {
  font-size: 0.88rem;
  color: var(--ink);
}

.knowledge-rule-item span {
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.6;
}

.knowledge-library-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-library-toolbar__search {
  flex: 1;
}

.upload-list {
  display: grid;
  gap: 10px;
}

.upload-list--page {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.upload-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  min-height: 92px;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 8px 20px rgba(31, 64, 128, 0.04);
}

.upload-item--page-card {
  position: relative;
  min-height: 152px;
  height: 152px;
  padding: 16px;
  border-color: rgba(31, 74, 160, 0.06);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 255, 0.94));
  box-shadow: 0 10px 24px rgba(31, 64, 128, 0.035);
}

.upload-item__checkbox {
  flex: none;
  margin-top: 3px;
}

.upload-item--page-card .upload-item__checkbox {
  position: absolute;
  top: 14px;
  left: 14px;
  margin-top: 0;
  z-index: 1;
}

.upload-item__body {
  min-width: 0;
  flex: 1;
}

.upload-item__body strong {
  display: block;
  word-break: break-word;
  line-height: 1.55;
}

.upload-item__body--stacked {
  display: grid;
  grid-template-rows: auto auto auto;
  align-content: start;
  gap: 10px;
  width: 100%;
  height: 100%;
  padding: 6px 44px 0 34px;
}

.upload-item__name {
  font-size: 0.96rem;
  font-weight: 800;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.45;
}

.upload-item__meta {
  color: var(--muted);
  font-size: 0.82rem;
  margin-top: 6px;
}

.upload-item__type,
.upload-item__size {
  color: var(--muted);
  font-size: 0.84rem;
  line-height: 1.5;
}

.upload-item__type {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(34, 197, 94, 0.18);
  background: rgba(34, 197, 94, 0.12);
  color: #167c3a;
  font-size: 0.8rem;
  font-weight: 600;
}

.upload-item__actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.upload-item__actions--floating {
  position: absolute;
  top: 12px;
  right: 12px;
}

.upload-item__delete {
  border-color: rgba(46, 108, 246, 0.12);
  color: var(--accent);
  background: rgba(255, 255, 255, 0.86);
}

.upload-empty-card {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 104px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px dashed rgba(46, 108, 246, 0.18);
  background: linear-gradient(180deg, rgba(247, 250, 255, 0.94), rgba(242, 247, 255, 0.88));
}

.upload-empty-card--page {
  min-height: 128px;
}

.upload-empty-card__icon {
  width: 38px;
  height: 38px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: rgba(46, 108, 246, 0.1);
  color: var(--accent);
  font-size: 18px;
}

.upload-empty-card__copy {
  display: grid;
  gap: 4px;
}

.upload-empty-card__copy strong {
  font-size: 0.94rem;
  color: var(--ink);
}

.upload-empty-card__copy span {
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.55;
}

.upload-queue {
  display: grid;
  gap: 10px;
}

.upload-task {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.9);
}

.upload-task__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.upload-task__head strong {
  min-width: 0;
  word-break: break-word;
}

.upload-task__meta {
  margin: 8px 0 12px;
  color: var(--muted);
  font-size: 0.83rem;
  line-height: 1.6;
}

.model-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.model-card {
  display: grid;
  gap: 6px;
  min-height: 112px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(31, 74, 160, 0.08);
  background:
    linear-gradient(180deg, rgba(244, 248, 255, 0.98), rgba(237, 243, 255, 0.92));
  box-shadow: 0 8px 18px rgba(31, 64, 128, 0.05);
}

.model-card label {
  color: var(--muted);
  font-size: 0.8rem;
}

.model-card strong {
  font-size: 0.96rem;
  line-height: 1.45;
  color: var(--ink);
  word-break: break-word;
}

.model-card span {
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.55;
}

@media (max-width: 960px) {
  .knowledge-dock {
    height: auto;
  }

  .knowledge-dock--page {
    min-height: auto;
  }

  .knowledge-panel__head,
  .knowledge-panel__head--library,
  .knowledge-library-toolbar,
  .knowledge-upload-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .knowledge-upload-grid,
  .upload-list--page,
  .model-card-grid {
    grid-template-columns: 1fr;
  }

  .knowledge-dock__bulk-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
