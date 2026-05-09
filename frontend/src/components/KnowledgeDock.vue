<script setup>
import { computed, ref, watch } from "vue";
import {
  Upload, Trash2, FileText, X, Loader2, CheckCircle, AlertCircle,
  Search, Files, Cpu, Database, Server, File, Check,
} from "lucide-vue-next";
import { formatRelativeTime, deleteUpload, deleteUploads } from "@/services/workspace";

const props = defineProps({
  busy: { type: Boolean, default: false },
  uploadTasks: { type: Array, default: () => [] },
  uploads: { type: Array, default: () => [] },
  totalUploadCount: { type: Number, default: 0 },
  modelSettings: { type: Object, default: () => ({ chatModel: "", embeddingModel: "", provider: "" }) },
  pageMode: { type: Boolean, default: false },
  deletingUploadId: { type: String, default: "" },
  batchDeleting: { type: Boolean, default: false },
  selectedUploadIds: { type: Array, default: () => [] },
  allUploadsSelected: { type: Boolean, default: false },
  selectedUploadCount: { type: Number, default: 0 },
  uploadSearch: { type: String, default: "" },
});

const emit = defineEmits([
  "import-files", "delete-file", "batch-delete",
  "toggle-select-all", "toggle-upload", "update:upload-search",
]);

const dragOver = ref(false);

const operationBusy = computed(() => props.busy || props.batchDeleting || !!props.deletingUploadId);
const canImport = computed(() => !props.busy && draftFiles.value.length > 0);
const draftFiles = ref([]);

const visibleUploadCountLabel = computed(() => {
  const total = props.totalUploadCount || props.uploads.length;
  const visible = props.uploads.length;
  if (props.uploadSearch.trim() && visible !== total) return `匹配 ${visible} / ${total}`;
  return `共 ${total} 个文件`;
});

function resolveFileLabel(file) {
  const ext = (file.name || file.filename || "").split(".").pop()?.toLowerCase();
  if (!ext) return "FILE";
  const map = { pdf: "PDF", docx: "DOC", doc: "DOC", xlsx: "XLS", xls: "XLS", csv: "CSV", txt: "TXT", md: "MD" };
  return map[ext] || ext.toUpperCase();
}

function resolveFileTypeText(file) {
  const ext = (file.name || file.filename || "").split(".").pop()?.toLowerCase();
  const map = { pdf: "PDF 文档", docx: "Word 文档", xlsx: "Excel 表格", xls: "Excel 表格", csv: "CSV 表格", txt: "文本文件", md: "Markdown 文档" };
  return map[ext] || `${(ext || "unknown").toUpperCase()} 文件`;
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function resolveTaskLabel(status) {
  const map = { uploading: "上传中", processing: "处理中", success: "已完成", error: "失败", duplicate: "已存在" };
  return map[status] || status;
}

function resolveProgressStatus(status) {
  if (status === "success") return "success";
  if (status === "error") return "exception";
  return "";
}

function onDragEnter(e) { e.preventDefault(); dragOver.value = true; }
function onDragLeave(e) { e.preventDefault(); dragOver.value = false; }
function onDragOver(e) { e.preventDefault(); }

function onDrop(e) {
  e.preventDefault();
  dragOver.value = false;
  const files = Array.from(e.dataTransfer.files || []);
  if (files.length) draftFiles.value = [...draftFiles.value, ...files];
}

function onFileSelect(e) {
  const files = Array.from(e.target.files || []);
  if (files.length) draftFiles.value = [...draftFiles.value, ...files];
  e.target.value = "";
}

function removeDraft(index) { draftFiles.value.splice(index, 1); }

function handleImport() {
  if (!canImport.value) return;
  emit("import-files", [...draftFiles.value]);
  draftFiles.value = [];
}

function handleDelete(file) {
  if (operationBusy.value) return;
  emit("delete-file", file);
}

function handleBatchDelete() {
  if (operationBusy.value || props.selectedUploadCount === 0) return;
  emit("batch-delete");
}

function toggleSelectAll(e) { emit("toggle-select-all", e.target.checked); }
function toggleUpload(file, checked) { emit("toggle-upload", { id: file.id, checked }); }

watch(() => props.uploadSearch, (v) => emit("update:upload-search", v));
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Busy notice -->
    <div v-if="operationBusy" class="mx-4 mt-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 flex items-center gap-2 shrink-0">
      <div class="flex gap-1">
        <span class="w-1 h-1 bg-amber-600 rounded-full animate-bounce" />
        <span class="w-1 h-1 bg-amber-600 rounded-full animate-bounce" style="animation-delay: 150ms" />
        <span class="w-1 h-1 bg-amber-600 rounded-full animate-bounce" style="animation-delay: 300ms" />
      </div>
      知识库操作正在进行，请等待完成后再操作。
    </div>

    <!-- ===== Import section ===== -->
    <div class="px-4 pt-3 shrink-0">
      <div class="flex items-center justify-between mb-2">
        <div>
          <span class="text-xs font-semibold text-zinc-700">导入文件</span>
          <span class="text-xs text-zinc-400 ml-2">{{ draftFiles.length ? `待导入 ${draftFiles.length}` : '拖拽或点击上传' }}</span>
        </div>
        <button
          v-if="draftFiles.length"
          @click="handleImport"
          :disabled="!canImport"
          class="px-3 py-1.5 bg-zinc-900 text-white text-xs font-medium rounded-lg hover:bg-zinc-700 transition-colors disabled:opacity-50 flex items-center gap-1"
        >
          <Upload class="w-3 h-3" /> 导入到知识库
        </button>
      </div>

      <!-- Drop zone -->
      <div
        @dragenter="onDragEnter" @dragleave="onDragLeave" @dragover="onDragOver" @drop="onDrop"
        :class="['border-2 border-dashed rounded-xl p-4 text-center transition-colors cursor-pointer', dragOver ? 'border-zinc-900 bg-zinc-50' : 'border-zinc-200 hover:border-zinc-300 bg-zinc-50/50']"
        @click="$refs.fileInput.click()"
      >
        <Upload class="w-6 h-6 text-zinc-400 mx-auto mb-2" />
        <p class="text-xs text-zinc-500">拖拽文件到此处，或点击选择</p>
        <p class="text-[10px] text-zinc-400 mt-1">支持 PDF、Word、Excel、CSV、Markdown、TXT</p>
        <input ref="fileInput" type="file" multiple accept=".txt,.md,.pdf,.docx,.xlsx,.xls,.csv" @change="onFileSelect" class="hidden" />
      </div>

      <!-- Draft files -->
      <div v-if="draftFiles.length" class="mt-2 space-y-1 max-h-32 overflow-y-auto">
        <div v-for="(f, i) in draftFiles" :key="i" class="flex items-center gap-2 px-2 py-1.5 bg-zinc-50 rounded-lg text-xs">
          <FileText class="w-3.5 h-3.5 text-zinc-400 shrink-0" />
          <span class="flex-1 truncate text-zinc-600">{{ f.name }}</span>
          <span class="text-zinc-400 shrink-0">{{ formatSize(f.size) }}</span>
          <button @click.stop="removeDraft(i)" class="p-0.5 text-zinc-400 hover:text-red-500 rounded"><X class="w-3 h-3" /></button>
        </div>
      </div>

      <!-- Upload tasks progress -->
      <div v-if="uploadTasks.length" class="mt-2 space-y-1.5 max-h-40 overflow-y-auto">
        <div v-for="(task, i) in uploadTasks" :key="i" class="px-2 py-1.5 bg-white border border-zinc-100 rounded-lg">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs text-zinc-600 truncate flex-1">{{ task.name || task.filename }}</span>
            <span :class="['text-[10px] font-medium ml-2', task.status === 'success' ? 'text-emerald-600' : task.status === 'error' ? 'text-red-500' : task.status === 'duplicate' ? 'text-amber-600' : 'text-zinc-500']">{{ resolveTaskLabel(task.status) }}</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all duration-300', task.status === 'success' ? 'bg-emerald-500' : task.status === 'error' ? 'bg-red-400' : task.status === 'duplicate' ? 'bg-amber-500' : 'bg-zinc-900']"
                :style="{ width: `${task.progress || 0}%` }"
              />
            </div>
            <span class="text-[10px] text-zinc-400 w-8 text-right">{{ task.progress || 0 }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== Uploaded files section ===== -->
    <div class="flex-1 flex flex-col min-h-0 px-4 mt-4">
      <div class="flex items-center justify-between mb-2 shrink-0">
        <div class="flex items-center gap-2">
          <Files class="w-4 h-4 text-zinc-500" />
          <span class="text-xs font-semibold text-zinc-700">已导入文件</span>
        </div>
        <span class="text-[10px] text-zinc-400 bg-zinc-100 px-1.5 py-0.5 rounded-full">{{ visibleUploadCountLabel }}</span>
      </div>

      <!-- Search & batch actions -->
      <div class="flex items-center gap-2 mb-2 shrink-0">
        <div class="relative flex-1">
          <Search class="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-zinc-400" />
          <input
            :value="uploadSearch"
            @input="emit('update:upload-search', $event.target.value)"
            placeholder="搜索文件..."
            class="w-full h-7 pl-7 pr-2 bg-zinc-50 border border-zinc-100 rounded-lg text-xs focus:outline-none focus:border-zinc-200 transition-colors"
          />
        </div>
        <button v-if="pageMode" @click="emit('toggle-select-all', !allUploadsSelected)" class="text-xs text-zinc-500 hover:text-zinc-700 shrink-0">
          {{ allUploadsSelected ? '取消全选' : '全选' }}
        </button>
        <button
          v-if="pageMode && selectedUploadCount > 0"
          @click="handleBatchDelete"
          :disabled="operationBusy"
          class="px-2 py-1 text-xs text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
        >
          <Trash2 class="w-3 h-3" /> 删除 ({{ selectedUploadCount }})
        </button>
      </div>

      <!-- File list -->
      <div class="flex-1 overflow-y-auto" :class="pageMode ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2' : 'space-y-1'">
        <div v-if="!uploads.length" class="col-span-full flex flex-col items-center justify-center py-8 text-center">
          <FileText class="w-8 h-8 text-zinc-300 mb-2" />
          <p class="text-xs text-zinc-400">{{ uploadSearch.trim() ? '没有匹配的文件' : '还没有导入文件' }}</p>
          <p class="text-[10px] text-zinc-300 mt-0.5">{{ uploadSearch.trim() ? '尝试其他搜索词' : '上传文档来构建你的知识库' }}</p>
        </div>

        <div
          v-for="upload in uploads" :key="upload.id"
          :class="['group relative border rounded-xl transition-all', pageMode ? 'p-3 cursor-pointer' : 'flex items-center gap-2 px-3 py-2', selectedUploadIds.includes(upload.id) ? 'border-zinc-400 bg-zinc-100' : 'bg-white border-zinc-100 hover:border-zinc-300']"
          @click="pageMode && toggleUpload(upload, !selectedUploadIds.includes(upload.id))"
        >

          <!-- File icon -->
          <div :class="['rounded-lg flex items-center justify-center shrink-0', pageMode ? 'w-10 h-10 mb-2' : 'w-8 h-8', upload.status === 'success' ? 'bg-emerald-50' : upload.status === 'error' ? 'bg-red-50' : 'bg-zinc-100']">
            <FileText :class="[upload.status === 'success' ? 'text-emerald-600' : upload.status === 'error' ? 'text-red-500' : 'text-zinc-500', pageMode ? 'w-5 h-5' : 'w-4 h-4']" />
          </div>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <p :class="['font-medium text-zinc-800 truncate', pageMode ? 'text-sm mb-1' : 'text-xs']">{{ upload.name }}</p>
            <div :class="['flex items-center gap-1.5 text-zinc-400', pageMode ? 'text-[10px] flex-wrap' : 'text-[10px]']">
              <span :class="['px-1 py-0.5 rounded text-[10px] font-medium', upload.status === 'success' ? 'bg-emerald-50 text-emerald-600' : 'bg-zinc-100 text-zinc-500']">{{ resolveFileLabel(upload) }}</span>
              <span>{{ formatSize(upload.size) }}</span>
              <span v-if="upload.uploaded_at">· {{ formatRelativeTime(upload.uploaded_at) }}</span>
            </div>
            <p v-if="upload.message && pageMode" class="text-[10px] text-zinc-400 mt-1 truncate">{{ upload.message }}</p>
          </div>

          <!-- Delete button (pageMode: top-right, non-pageMode: right side) -->
          <button
            @click.stop="handleDelete(upload)"
            :disabled="operationBusy"
            class="p-1.5 text-zinc-400 hover:text-red-500 hover:bg-red-100 rounded-lg transition shrink-0"
            :class="pageMode ? 'absolute top-1.5 right-1.5' : ''"
          >
            <template v-if="deletingUploadId === upload.id">
              <div class="flex gap-0.5">
                <span class="w-1 h-1 bg-red-500 rounded-full animate-bounce" />
                <span class="w-1 h-1 bg-red-500 rounded-full animate-bounce" style="animation-delay: 150ms" />
                <span class="w-1 h-1 bg-red-500 rounded-full animate-bounce" style="animation-delay: 300ms" />
              </div>
            </template>
            <Trash2 v-else class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>

    <!-- ===== Model info section ===== -->
    <div class="px-4 py-3 border-t border-zinc-100 shrink-0">
      <div class="grid grid-cols-3 gap-2">
        <div class="bg-zinc-50 rounded-lg px-2.5 py-2">
          <div class="flex items-center gap-1.5 mb-0.5">
            <Cpu class="w-3 h-3 text-zinc-400" />
            <span class="text-[10px] text-zinc-400">问答模型</span>
          </div>
          <p class="text-xs font-medium text-zinc-700 truncate">{{ modelSettings.chatModel || '—' }}</p>
        </div>
        <div class="bg-zinc-50 rounded-lg px-2.5 py-2">
          <div class="flex items-center gap-1.5 mb-0.5">
            <Database class="w-3 h-3 text-zinc-400" />
            <span class="text-[10px] text-zinc-400">嵌入模型</span>
          </div>
          <p class="text-xs font-medium text-zinc-700 truncate">{{ modelSettings.embeddingModel || '—' }}</p>
        </div>
        <div class="bg-zinc-50 rounded-lg px-2.5 py-2">
          <div class="flex items-center gap-1.5 mb-0.5">
            <Server class="w-3 h-3 text-zinc-400" />
            <span class="text-[10px] text-zinc-400">模型来源</span>
          </div>
          <p class="text-xs font-medium text-zinc-700 truncate">{{ modelSettings.provider || '—' }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
