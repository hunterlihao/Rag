<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Delete,
  EditPen,
  Plus,
  RefreshRight,
  Search,
  Setting,
  UserFilled,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import ActionBusyOverlay from "@/components/ActionBusyOverlay.vue";
import DeleteConfirmDialog from "@/components/DeleteConfirmDialog.vue";
import DialogHeroHeader from "@/components/DialogHeroHeader.vue";
import WorkspaceSidebar from "@/components/WorkspaceSidebar.vue";
import { getCurrentUser, logout, replaceCurrentUser } from "@/services/auth";
import { buildRouteLocation, buildSidebarNavItems, normalizeShellSession } from "@/services/shell";
import {
  createAdminUser,
  deleteAdminUser,
  fetchAdminUsers,
  getPreferences,
  savePreferences,
  updateAdminUser,
} from "@/services/user";
import { createSession, deleteSession, fetchSessions } from "@/services/workspace";

const route = useRoute();
const router = useRouter();
const user = ref(getCurrentUser());
const preferences = ref(getPreferences(user.value));

const workspace = reactive({
  sessions: [],
});
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
const formRef = ref(null);
const deleteDialogVisible = ref(false);
const userPendingDelete = ref(null);
const formDialogMeta = computed(() => {
  const isCreate = formMode.value === "create";
  return {
    icon: isCreate ? Plus : EditPen,
    title: isCreate ? "新增用户" : "编辑用户",
    badgeText: isCreate ? "创建账号" : "更新账号",
    description: isCreate
      ? "填写基础资料、初始密码和角色信息后创建新账号。"
      : "修改账号资料、密码或管理员角色，变更会立即生效。",
  };
});
const deleteBusyState = computed(() => {
  if (deletingUserId.value) {
    return {
      visible: true,
      badgeText: "删除处理中",
      title: "正在删除用户",
      description: "用户数据、会话历史和独立知识库内容正在同步清理，请等待完成。",
    };
  }

  return {
    visible: !!deletingSessionId.value,
    badgeText: "删除处理中",
    title: "正在删除会话",
    description: "会话记录正在清理并刷新管理台左侧历史列表，请稍候。",
  };
});
const navItems = computed(() => buildSidebarNavItems(user.value));
const dashboardGridStyle = computed(() => ({
  "--dashboard-sidebar-width": preferences.value.sidebarCollapsed ? "88px" : "320px",
}));

const form = reactive({
  id: "",
  name: "",
  email: "",
  password: "",
  is_admin: false,
});

const formRules = {
  name: [{ required: true, message: "请输入昵称", trigger: "blur" }],
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "邮箱格式不正确", trigger: ["blur", "change"] },
  ],
  password: [
    {
      validator: (_rule, value, callback) => {
        if (formMode.value === "create" && !value) {
          callback(new Error("请设置初始密码"));
          return;
        }
        if (value && value.length < 6) {
          callback(new Error("密码至少需要 6 位"));
          return;
        }
        callback();
      },
      trigger: ["blur", "change"],
    },
  ],
};

const filteredSessions = computed(() => {
  const keyword = sessionSearch.value.trim().toLowerCase();
  return [...workspace.sessions]
    .sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt))
    .filter((session) => {
      if (!keyword) {
        return true;
      }
      return `${session.title} ${session.preview || ""}`.toLowerCase().includes(keyword);
    });
});

const adminCount = computed(() => userRows.value.filter((item) => item.isAdmin).length);
const normalUserCount = computed(() => userRows.value.length - adminCount.value);
const todayCreatedCount = computed(() => {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = today.getMonth();
  const dd = today.getDate();
  return userRows.value.filter((item) => {
    const createdAt = new Date(item.createdAt);
    return (
      createdAt.getFullYear() === yyyy &&
      createdAt.getMonth() === mm &&
      createdAt.getDate() === dd
    );
  }).length;
});

function normalizeUserRow(row) {
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    isAdmin: Boolean(row.is_admin ?? row.isAdmin),
    createdAt: row.created_at || row.createdAt || new Date().toISOString(),
  };
}

async function refreshSessions() {
  const sessionList = await fetchSessions();
  workspace.sessions.splice(
    0,
    workspace.sessions.length,
    ...sessionList.map((session) => normalizeShellSession(session)),
  );
  activeSessionId.value = workspace.sessions[0]?.id || "";
}

async function refreshUsers() {
  tableLoading.value = true;
  try {
    const result = await fetchAdminUsers(userKeyword.value);
    userRows.value = (result.users || []).map((item) => normalizeUserRow(item));
    currentAdminId.value = result.current_admin_id || "";
  } catch (error) {
    ElMessage.error(error.message || "加载用户列表失败");
  } finally {
    tableLoading.value = false;
  }
}

function navigateTo(name) {
  router.push(buildRouteLocation(name, activeSessionId.value));
}

async function createNewSession() {
  const session = await createSession();
  router.push(buildRouteLocation("workspace", session.id));
}

async function selectSession(sessionId) {
  router.push(buildRouteLocation("workspace", sessionId));
}

async function handleDeleteSession(sessionId) {
  if (!sessionId || deletingSessionId.value) {
    return;
  }

  deletingSessionId.value = sessionId;
  try {
    await deleteSession(sessionId);
    await refreshSessions();
    ElMessage.success("会话已删除");
  } catch (error) {
    ElMessage.error(error.message || "删除会话失败");
  } finally {
    deletingSessionId.value = "";
  }
}

async function handleLogout() {
  await logout();
  router.push("/login");
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

function resetForm() {
  form.id = "";
  form.name = "";
  form.email = "";
  form.password = "";
  form.is_admin = false;
}

function openCreateDialog() {
  formMode.value = "create";
  resetForm();
  dialogVisible.value = true;
}

function openEditDialog(row) {
  formMode.value = "edit";
  form.id = row.id;
  form.name = row.name;
  form.email = row.email;
  form.password = "";
  form.is_admin = row.isAdmin;
  dialogVisible.value = true;
}

async function submitUserForm() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid || saving.value) {
    return;
  }

  saving.value = true;
  try {
    if (formMode.value === "create") {
      await createAdminUser({
        name: form.name,
        email: form.email,
        password: form.password,
        is_admin: form.is_admin,
      });
      ElMessage.success("用户创建成功");
    } else {
      const result = await updateAdminUser(form.id, {
        name: form.name,
        email: form.email,
        password: form.password,
        is_admin: form.is_admin,
      });

      if (result.user?.id === user.value?.id) {
        user.value = replaceCurrentUser(result.user, result.access_token);
        if (!user.value?.isAdmin) {
          ElMessage.success("当前账号已移出管理员角色，正在返回问答主页。");
          dialogVisible.value = false;
          router.push({ name: "workspace" });
          return;
        }
      }

      ElMessage.success("用户更新成功");
    }

    dialogVisible.value = false;
    await refreshUsers();
  } catch (error) {
    ElMessage.error(error.message || "保存用户失败");
  } finally {
    saving.value = false;
  }
}

async function removeUser(row) {
  if (!row?.id || deletingUserId.value) {
    return;
  }
  userPendingDelete.value = row;
  deleteDialogVisible.value = true;
}

async function confirmDeleteUser() {
  if (!userPendingDelete.value?.id) {
    return;
  }
  const row = userPendingDelete.value;
  deleteDialogVisible.value = false;
  userPendingDelete.value = null;
  deletingUserId.value = row.id;
  try {
    await deleteAdminUser(row.id);
    ElMessage.success("用户已删除");
    await refreshUsers();
  } catch (error) {
    ElMessage.error(error.message || "删除用户失败");
  } finally {
    deletingUserId.value = "";
  }
}

onMounted(async () => {
  pageLoading.value = true;
  try {
    user.value = getCurrentUser();
    preferences.value = getPreferences(user.value);
    await Promise.all([refreshSessions(), refreshUsers()]);
  } catch (error) {
    ElMessage.error(error.message || "用户管理页面加载失败");
  } finally {
    pageLoading.value = false;
  }
});
</script>

<template>
  <div v-loading="pageLoading" class="page-shell admin-page">
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
        :busy="tableLoading || saving || !!deletingUserId"
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

      <section class="dashboard-stage">
        <header class="dashboard-hero glass-panel">
          <div class="dashboard-copy">
            <div class="dashboard-eyebrow">管理员控制台</div>
            <h1>在一个界面里完成用户基础管理。</h1>
            <p>
              管理员账号可以直接查询、新增、编辑和删除用户。删除用户时，会同步清理对应会话历史与独立知识库内容。
            </p>
          </div>

          <div class="dashboard-stats">
            <div class="info-tile">
              <div class="info-tile__icon">
                <el-icon><UserFilled /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ userRows.length }}</strong>
                <span>系统总用户数</span>
              </div>
            </div>
            <div class="info-tile">
              <div class="info-tile__icon">
                <el-icon><Setting /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ adminCount }}</strong>
                <span>管理员账号数</span>
              </div>
            </div>
            <div class="info-tile">
              <div class="info-tile__icon">
                <el-icon><Plus /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ todayCreatedCount }}</strong>
                <span>今日新增用户</span>
              </div>
            </div>
          </div>
        </header>

        <section class="soft-card content-card panel-stack">
          <div class="panel-toolbar">
            <el-input
              v-model="userKeyword"
              clearable
              class="admin-toolbar__search"
              placeholder="按昵称或邮箱搜索用户"
              :prefix-icon="Search"
              @keyup.enter="refreshUsers"
            />
            <div class="panel-toolbar__actions">
              <el-button plain :icon="RefreshRight" @click="refreshUsers">刷新</el-button>
              <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增用户</el-button>
            </div>
          </div>

          <div class="admin-summary">
            <span>普通用户 {{ normalUserCount }} 个</span>
            <span>当前管理员 ID：{{ currentAdminId || "-" }}</span>
          </div>

          <el-table v-loading="tableLoading" :data="userRows" stripe class="admin-table">
            <el-table-column label="昵称" min-width="160">
              <template #default="{ row }">
                <div class="user-cell">
                  <el-avatar :size="34" class="user-cell__avatar">
                    {{ row.name?.slice(0, 1)?.toUpperCase() || "U" }}
                  </el-avatar>
                  <div>
                    <strong>{{ row.name }}</strong>
                    <div class="muted-copy">{{ row.id }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="email" label="邮箱" min-width="220" />
            <el-table-column label="角色" width="120">
              <template #default="{ row }">
                <el-tag round effect="plain">{{ row.isAdmin ? "管理员" : "普通用户" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" min-width="180">
              <template #default="{ row }">
                {{ new Date(row.createdAt).toLocaleString("zh-CN") }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <div class="user-actions">
                  <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
                  <el-button
                    link
                    :icon="Delete"
                    :loading="deletingUserId === row.id"
                    @click="removeUser(row)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </section>
    </div>

    <el-dialog
      v-model="dialogVisible"
      class="surface-form-dialog"
      width="520px"
      destroy-on-close
    >
      <template #header>
        <DialogHeroHeader
          :icon="formDialogMeta.icon"
          :title="formDialogMeta.title"
          :badge-text="formDialogMeta.badgeText"
          :description="formDialogMeta.description"
        />
      </template>

      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" class="panel-stack">
        <el-form-item label="昵称" prop="name">
          <el-input v-model="form.name" placeholder="请输入昵称" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item :label="formMode === 'create' ? '初始密码' : '重置密码'" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="formMode === 'create' ? '至少 6 位' : '留空则不修改密码'"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-switch
            v-model="form.is_admin"
            inline-prompt
            active-text="管理员"
            inactive-text="普通"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="submitUserForm">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <DeleteConfirmDialog
      v-model="deleteDialogVisible"
      title="删除用户"
      confirm-text="确认删除"
      :loading="!!deletingUserId"
      :summary="userPendingDelete ? `确认删除用户「${userPendingDelete.name}」吗？` : ''"
      hint="该用户的会话记录和独立知识库内容会一起清理。"
      :items="userPendingDelete ? [{ id: userPendingDelete.id, name: `${userPendingDelete.name} · ${userPendingDelete.email}` }] : []"
      extra="如果只是停用账号，建议先评估是否需要保留历史数据。"
      @confirm="confirmDeleteUser"
    />
  </div>
</template>

<style scoped>
.admin-page {
  overflow: hidden;
}

.admin-toolbar__search {
  max-width: 360px;
}

.admin-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: var(--muted);
  font-size: 0.92rem;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-cell strong {
  display: block;
}

.user-cell__avatar {
  background: linear-gradient(135deg, #1d54d8, #6ca3ff);
  color: #fff;
  font-weight: 800;
}

.user-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

:deep(.surface-form-dialog) {
  width: min(520px, calc(100vw - 32px));
  border-radius: 26px;
  border: 1px solid rgba(31, 74, 160, 0.08);
  box-shadow: 0 30px 72px rgba(31, 64, 128, 0.16);
  overflow: hidden;
}

:deep(.surface-form-dialog .el-dialog__header) {
  margin: 0;
  padding: 22px 22px 0;
}

:deep(.surface-form-dialog .el-dialog__body) {
  padding: 14px 22px 8px;
}

:deep(.surface-form-dialog .el-dialog__footer) {
  padding: 8px 22px 22px;
}

@media (max-width: 1080px) {
  .admin-page {
    overflow: auto;
  }

  .panel-toolbar,
  .admin-summary {
    flex-direction: column;
    align-items: stretch;
  }

  .admin-toolbar__search {
    max-width: none;
  }
}
</style>
