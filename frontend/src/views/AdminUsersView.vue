<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ArrowLeft, User, Mail, Lock, Shield, Trash2, Plus, X, Loader2, Search, RefreshCw, Users, UserCheck, AlertCircle } from "lucide-vue-next";

import ActionBusyOverlay from "@/components/ActionBusyOverlay.vue";
import DeleteConfirmDialog from "@/components/DeleteConfirmDialog.vue";
import WorkspaceSidebar from "@/components/WorkspaceSidebar.vue";
import { getCurrentUser, logout, replaceCurrentUser } from "@/services/auth";
import { buildRouteLocation, buildSidebarNavItems, normalizeShellSession } from "@/services/shell";
import { createAdminUser, deleteAdminUser, fetchAdminUsers, getPreferences, savePreferences, updateAdminUser } from "@/services/user";
import { createSession, deleteSession, fetchSessions } from "@/services/workspace";

const router = useRouter();
const user = ref(getCurrentUser());
const preferences = ref(getPreferences(user.value));
const workspace = reactive({ sessions: [] });
const userRows = ref([]);
const pageLoading = ref(false);
const tableLoading = ref(false);
const saving = ref(false);
const deletingSessionId = ref("");
const deletingUserId = ref("");
const sessionSearch = ref("");
const userKeyword = ref("");
const activeSessionId = ref("");
const currentAdminId = ref("");
const dialogVisible = ref(false);
const formMode = ref("create");
const formError = ref("");
const deleteDialogVisible = ref(false);
const userPendingDelete = ref(null);

const sidebarBusy = computed(() => !!deletingSessionId.value || !!deletingUserId.value);
const navItems = computed(() => buildSidebarNavItems(user.value));

const filteredSessions = computed(() => {
  const kw = sessionSearch.value.trim().toLowerCase();
  return [...workspace.sessions]
    .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
    .filter((s) => !kw || `${s.title} ${s.preview || ""}`.toLowerCase().includes(kw));
});

const adminCount = computed(() => userRows.value.filter((u) => u.is_admin).length);
const normalUserCount = computed(() => userRows.value.filter((u) => !u.is_admin).length);
const todayCreatedCount = computed(() => {
  const today = new Date().toDateString();
  return userRows.value.filter((u) => {
    const d = u.created_at ? new Date(u.created_at).toDateString() : null;
    return d === today;
  }).length;
});

const form = reactive({ id: "", name: "", email: "", password: "", is_admin: false });

const formRules = computed(() => ({
  name: { required: true, message: "请输入用户名" },
  email: { required: true, message: "请输入邮箱", pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/ },
  password: formMode.value === "create" ? { required: true, message: "密码至少6位", min: 6 } : null,
}));

const busyOverlayState = computed(() => {
  if (deletingUserId.value) return { visible: true, badgeText: "删除中", title: "正在删除用户", description: "用户数据正在清理。" };
  if (deletingSessionId.value) return { visible: true, badgeText: "删除处理中", title: "正在删除会话", description: "会话记录正在清理。" };
  return { visible: false };
});

function normalizeUserRow(row) {
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    is_admin: Boolean(row.is_admin ?? row.isAdmin),
    created_at: row.created_at || row.createdAt,
  };
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function refreshSessions() {
  const list = await fetchSessions();
  workspace.sessions = list.map((s) => ({ ...normalizeShellSession(s), welcomeMessage: "" }));
  if (workspace.sessions.length) activeSessionId.value = workspace.sessions[0].id;
}

async function refreshUsers() {
  tableLoading.value = true;
  try {
    const result = await fetchAdminUsers(userKeyword.value);
    userRows.value = (result.users || []).map(normalizeUserRow);
    currentAdminId.value = result.current_admin_id || "";
  } finally {
    tableLoading.value = false;
  }
}

function navigateTo(name) { router.push(buildRouteLocation(name, activeSessionId.value)); }
async function createNewSession() { const s = await createSession(); router.push(buildRouteLocation("workspace", s.id)); }
function selectSession(id) { router.push(buildRouteLocation("workspace", id)); }
async function handleDeleteSession(id) {
  if (!id || sidebarBusy.value) return;
  deletingSessionId.value = id;
  try { await deleteSession(id); workspace.sessions = workspace.sessions.filter((s) => s.id !== id); } finally { deletingSessionId.value = ""; }
}
async function handleLogout() { await logout(); router.push("/login"); }
function toggleSidebarCollapse() { preferences.value = savePreferences({ ...preferences.value, sidebarCollapsed: !preferences.value.sidebarCollapsed }, user.value); }

function openCreateDialog() {
  formMode.value = "create"; formError.value = "";
  form.id = ""; form.name = ""; form.email = ""; form.password = ""; form.is_admin = false;
  dialogVisible.value = true;
}
function openEditDialog(row) {
  formMode.value = "edit"; formError.value = "";
  form.id = row.id; form.name = row.name; form.email = row.email; form.password = ""; form.is_admin = row.is_admin;
  dialogVisible.value = true;
}

async function submitUserForm() {
  formError.value = "";
  if (!form.name.trim()) { formError.value = "请输入用户名"; return; }
  if (!form.email.trim()) { formError.value = "请输入邮箱"; return; }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) { formError.value = "邮箱格式不正确"; return; }
  if (formMode.value === "create" && !form.password.trim()) { formError.value = "请输入密码（至少6位）"; return; }
  if (form.password.trim() && form.password.trim().length < 6) { formError.value = "密码至少需要6位"; return; }
  saving.value = true;
  try {
    if (formMode.value === "create") {
      await createAdminUser({ name: form.name, email: form.email, password: form.password, is_admin: form.is_admin });
    } else {
      const payload = { name: form.name, email: form.email, is_admin: form.is_admin };
      if (form.password.trim()) payload.password = form.password;
      const result = await updateAdminUser(form.id, payload);
      if (result.user && result.user.id === user.value?.id) user.value = replaceCurrentUser(result.user, result.access_token);
    }
    dialogVisible.value = false;
    await refreshUsers();
  } catch (err) {
    formError.value = err.message || "保存失败";
  } finally {
    saving.value = false;
  }
}

function removeUser(row) {
  userPendingDelete.value = row;
  deleteDialogVisible.value = true;
}

async function confirmDeleteUser() {
  if (!userPendingDelete.value) return;
  const u = userPendingDelete.value;
  deleteDialogVisible.value = false;
  deletingUserId.value = u.id;
  try { await deleteAdminUser(u.id); await refreshUsers(); } finally { deletingUserId.value = ""; }
}

watch(activeSessionId, (id) => {
  if (router.currentRoute?.value?.name !== "admin-users") return;
  router.replace({ name: "admin-users", query: id ? { session: id } : {} });
});

onMounted(async () => {
  pageLoading.value = true;
  try {
    user.value = getCurrentUser();
    preferences.value = getPreferences(user.value);
    await refreshSessions();
    await refreshUsers();
  } catch {
    if (!getCurrentUser()) router.push("/login");
  } finally {
    pageLoading.value = false;
  }
});
</script>

<template>
  <div class="flex h-screen bg-zinc-50">
    <ActionBusyOverlay v-bind="busyOverlayState" />

    <WorkspaceSidebar
      :user="user"
      :sessions="filteredSessions"
      :nav-items="navItems"
      :current-route-name="'admin-users'"
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
      <header class="h-12 bg-white border-b border-zinc-100 flex items-center px-6 shrink-0">
        <button @click="router.push('/workspace')" class="flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-700 transition-colors">
          <ArrowLeft class="w-4 h-4" /> 返回
        </button>
        <span class="mx-3 text-zinc-300">/</span>
        <span class="text-sm font-medium text-zinc-700">用户管理</span>
      </header>

      <div class="flex-1 overflow-y-auto">
        <div v-if="pageLoading" class="flex items-center justify-center h-full">
          <Loader2 class="w-6 h-6 text-zinc-300 animate-spin" />
        </div>

        <div v-else class="max-w-6xl mx-auto px-6 py-6 space-y-6">
          <!-- Hero -->
          <div>
            <span class="inline-flex items-center px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-500 text-xs font-medium mb-3">管理员控制台</span>
            <h1 class="text-xl font-bold text-zinc-900 tracking-tight mb-1">系统用户管理</h1>
            <p class="text-sm text-zinc-500">管理员可维护系统用户与权限，当前管理员工号：{{ currentAdminId || '—' }}</p>
          </div>

          <!-- Info tiles -->
          <div class="grid grid-cols-3 gap-3">
            <div class="bg-white border border-zinc-200 rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-zinc-100 flex items-center justify-center">
                <Users class="w-4 h-4 text-zinc-500" />
              </div>
              <div>
                <p class="text-lg font-bold text-zinc-900 numeric">{{ userRows.length }}</p>
                <p class="text-xs text-zinc-400">总用户数</p>
              </div>
            </div>
            <div class="bg-white border border-zinc-200 rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                <Shield class="w-4 h-4 text-amber-600" />
              </div>
              <div>
                <p class="text-lg font-bold text-zinc-900 numeric">{{ adminCount }}</p>
                <p class="text-xs text-zinc-400">管理员 / {{ normalUserCount }} 普通</p>
              </div>
            </div>
            <div class="bg-white border border-zinc-200 rounded-xl p-4 flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center">
                <UserCheck class="w-4 h-4 text-emerald-600" />
              </div>
              <div>
                <p class="text-lg font-bold text-zinc-900 numeric">{{ todayCreatedCount }}</p>
                <p class="text-xs text-zinc-400">今日新增</p>
              </div>
            </div>
          </div>

          <!-- Toolbar -->
          <div class="flex items-center gap-2">
            <div class="relative flex-1 max-w-xs">
              <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input v-model="userKeyword" @keyup.enter="refreshUsers" placeholder="搜索昵称或邮箱..." class="w-full h-9 pl-9 pr-3 bg-white border border-zinc-200 rounded-xl text-sm focus:outline-none focus:border-zinc-300 transition-colors" />
            </div>
            <button @click="refreshUsers" :disabled="tableLoading" class="px-3 py-1.5 text-xs text-zinc-600 bg-white border border-zinc-200 hover:bg-zinc-50 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50">
              <RefreshCw :class="['w-3.5 h-3.5', tableLoading && 'animate-spin']" /> 刷新
            </button>
            <button @click="openCreateDialog" class="px-3 py-1.5 text-xs text-white bg-zinc-900 hover:bg-zinc-800 rounded-lg transition-colors flex items-center gap-1.5">
              <Plus class="w-3.5 h-3.5" /> 新增用户
            </button>
          </div>

          <!-- Table -->
          <div class="bg-white border border-zinc-200 rounded-xl overflow-hidden">
            <table class="w-full">
              <thead>
                <tr class="border-b border-zinc-200 bg-zinc-50">
                  <th class="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">用户</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">邮箱</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">角色</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase hidden sm:table-cell">创建时间</th>
                  <th class="text-right px-4 py-3 text-xs font-medium text-zinc-500 uppercase">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="tableLoading">
                  <td colspan="5" class="text-center py-12">
                    <Loader2 class="w-5 h-5 text-zinc-300 animate-spin mx-auto" />
                  </td>
                </tr>
                <tr v-else-if="!userRows.length">
                  <td colspan="5" class="text-center py-12 text-sm text-zinc-400">暂无用户数据</td>
                </tr>
                <tr v-for="(row, idx) in userRows" :key="row.id" :class="['border-b border-zinc-50 last:border-0 hover:bg-zinc-50 transition-colors', idx % 2 === 0 ? 'bg-white' : 'bg-zinc-50/30']">
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2.5">
                      <div class="w-8 h-8 rounded-full bg-zinc-200 flex items-center justify-center text-xs font-medium text-zinc-600">{{ row.name?.charAt(0)?.toUpperCase() || '?' }}</div>
                      <div>
                        <p class="text-sm font-medium text-zinc-900">{{ row.name }}</p>
                        <p class="text-[10px] text-zinc-400">{{ row.id }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="px-4 py-3 text-sm text-zinc-600">{{ row.email }}</td>
                  <td class="px-4 py-3">
                    <span :class="['inline-flex px-2 py-0.5 rounded-full text-xs font-medium', row.is_admin ? 'bg-amber-50 text-amber-700' : 'bg-zinc-100 text-zinc-600']">
                      {{ row.is_admin ? '管理员' : '普通用户' }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm text-zinc-500 hidden sm:table-cell">{{ formatDate(row.created_at) }}</td>
                  <td class="px-4 py-3 text-right">
                    <button @click="openEditDialog(row)" class="px-2.5 py-1 text-xs text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100 rounded-lg transition-colors">编辑</button>
                    <button @click="removeUser(row)" :disabled="row.id === user?.id" class="px-2.5 py-1 text-xs text-red-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Edit modal -->
    <div v-if="dialogVisible" class="fixed inset-0 z-[100] flex items-center justify-center">
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="dialogVisible = false" />
      <div class="relative bg-white rounded-2xl shadow-2xl p-6 max-w-md w-full mx-4" style="animation: fade-in 0.2s ease-out, slide-up 0.2s ease-out;">
        <button @click="dialogVisible = false" :disabled="saving" class="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"><X class="w-5 h-5" /></button>
        <h3 class="text-lg font-semibold text-zinc-900 mb-4">{{ formMode === 'create' ? '创建用户' : '编辑用户' }}</h3>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-zinc-700 mb-1">用户名</label>
            <div class="relative">
              <User class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input v-model="form.name" class="w-full h-10 pl-10 pr-3 bg-zinc-50 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all" placeholder="用户名" />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-700 mb-1">邮箱</label>
            <div class="relative">
              <Mail class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input v-model="form.email" type="email" class="w-full h-10 pl-10 pr-3 bg-zinc-50 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all" placeholder="email@example.com" />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-700 mb-1">{{ formMode === 'create' ? '密码' : '新密码（留空则不修改）' }}</label>
            <div class="relative">
              <Lock class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input v-model="form.password" type="password" class="w-full h-10 pl-10 pr-3 bg-zinc-50 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all" :placeholder="formMode === 'create' ? '至少6位' : '留空则不修改'" />
            </div>
          </div>
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="form.is_admin" type="checkbox" class="w-4 h-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900" />
            <span class="text-sm text-zinc-700">管理员权限</span>
          </label>
          <div v-if="formError" class="flex items-center gap-2 bg-red-50 text-red-600 px-3 py-2 rounded-lg text-xs">
            <AlertCircle class="w-3.5 h-3.5" /> {{ formError }}
          </div>
          <div class="flex gap-3 pt-2">
            <button @click="dialogVisible = false" :disabled="saving" class="flex-1 h-10 border border-zinc-200 text-zinc-700 rounded-xl text-sm font-medium hover:bg-zinc-50 transition-colors">取消</button>
            <button @click="submitUserForm" :disabled="saving" class="flex-1 h-10 bg-zinc-900 text-white rounded-xl text-sm font-medium hover:bg-zinc-800 transition-colors flex items-center justify-center gap-2 disabled:opacity-70">
              <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirm -->
    <DeleteConfirmDialog
      v-model="deleteDialogVisible"
      title="删除用户"
      :summary="userPendingDelete ? `确认删除用户「${userPendingDelete.name}」吗？` : ''"
      hint="删除后，该用户的会话和知识库数据可能丢失。"
      :items="userPendingDelete ? [{ id: userPendingDelete.id, name: userPendingDelete.name }] : []"
      extra="此操作不可恢复。"
      @confirm="confirmDeleteUser"
    />
  </div>
</template>
