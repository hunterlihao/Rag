<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  EditPen,
  Lock,
  Monitor,
  Setting,
  UserFilled,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import ActionBusyOverlay from "@/components/ActionBusyOverlay.vue";
import WorkspaceSidebar from "@/components/WorkspaceSidebar.vue";
import { getCurrentUser, logout } from "@/services/auth";
import { buildRouteLocation, buildSidebarNavItems, normalizeShellSession } from "@/services/shell";
import {
  buildDefaultPreferences,
  getPreferences,
  normalizePreferences,
  savePreferences,
  updateMyPassword,
  updateMyProfile,
} from "@/services/user";
import { createSession, deleteSession, fetchSessions } from "@/services/workspace";

const route = useRoute();
const router = useRouter();
const user = ref(getCurrentUser());
const preferences = ref({
  ...buildDefaultPreferences(),
  ...getPreferences(user.value),
});

const workspace = reactive({
  sessions: [],
});
const pageLoading = ref(false);
const profileLoading = ref(false);
const passwordLoading = ref(false);
const preferenceLoading = ref(false);
const deletingSessionId = ref("");
const sessionSearch = ref("");
const activeSessionId = ref("");
const deleteBusyState = computed(() => ({
  visible: !!deletingSessionId.value,
  badgeText: "删除处理中",
  title: "正在删除会话",
  description: "正在清理当前会话并同步刷新左侧历史列表，请稍候。",
}));
const navItems = computed(() => buildSidebarNavItems(user.value));
const dashboardGridStyle = computed(() => ({
  "--dashboard-sidebar-width": preferences.value.sidebarCollapsed ? "88px" : "320px",
}));

const profileForm = reactive({
  name: user.value?.name || "",
  email: user.value?.email || "",
});

const passwordForm = reactive({
  current_password: "",
  new_password: "",
  confirm_password: "",
});

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

async function refreshSessions() {
  const sessionList = await fetchSessions();
  workspace.sessions.splice(
    0,
    workspace.sessions.length,
    ...sessionList.map((session) => normalizeShellSession(session)),
  );
  activeSessionId.value = workspace.sessions[0]?.id || "";
}

function syncProfileForm() {
  profileForm.name = user.value?.name || "";
  profileForm.email = user.value?.email || "";
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

function navigateTo(name) {
  router.push(buildRouteLocation(name, activeSessionId.value));
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

async function saveProfile() {
  if (profileLoading.value) {
    return;
  }

  profileLoading.value = true;
  try {
    const result = await updateMyProfile({
      name: profileForm.name,
      email: profileForm.email,
    });
    user.value = getCurrentUser();
    syncProfileForm();
    ElMessage.success(result.message || "个人信息已更新");
  } catch (error) {
    ElMessage.error(error.message || "个人信息更新失败");
  } finally {
    profileLoading.value = false;
  }
}

async function savePassword() {
  if (passwordLoading.value) {
    return;
  }

  if (!passwordForm.current_password || !passwordForm.new_password) {
    ElMessage.warning("请先填写完整密码信息");
    return;
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning("两次输入的新密码不一致");
    return;
  }

  passwordLoading.value = true;
  try {
    await updateMyPassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    });
    ElMessage.success("密码已更新，请重新登录。");
    await logout();
    router.push("/login");
  } catch (error) {
    ElMessage.error(error.message || "密码更新失败");
  } finally {
    passwordLoading.value = false;
  }
}

async function saveUserPreferences() {
  preferenceLoading.value = true;
  try {
    preferences.value = savePreferences(preferences.value, user.value);
    ElMessage.success("个性化设置已保存");
  } finally {
    preferenceLoading.value = false;
  }
}

const homeRouteOptions = computed(() => {
  const options = [
    { label: "问答主页", value: "workspace" },
    { label: "知识库", value: "knowledge" },
    { label: "设置中心", value: "settings" },
  ];
  if (user.value?.isAdmin) {
    options.push({ label: "用户管理", value: "admin-users" });
  }
  return options;
});

const effectiveHomeRoute = computed(() => {
  const routeName = String(preferences.value.homeRoute || "workspace").trim();
  if (routeName === "admin-users" && !user.value?.isAdmin) {
    return "workspace";
  }
  return routeName || "workspace";
});

const effectiveHomeRouteLabel = computed(() => {
  return (
    homeRouteOptions.value.find((item) => item.value === effectiveHomeRoute.value)?.label ||
    "问答主页"
  );
});

onMounted(async () => {
  pageLoading.value = true;
  try {
    user.value = getCurrentUser();
    preferences.value = normalizePreferences(getPreferences(user.value), user.value);
    syncProfileForm();
    await refreshSessions();
  } catch (error) {
    ElMessage.error(error.message || "设置页面加载失败");
  } finally {
    pageLoading.value = false;
  }
});
</script>

<template>
  <div v-loading="pageLoading" class="page-shell settings-page">
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
        :busy="profileLoading || passwordLoading || preferenceLoading"
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
            <div class="dashboard-eyebrow">设置中心</div>
            <h1>统一维护账号信息、安全能力和工作习惯。</h1>
            <p>
              这里可以修改个人资料、更新登录密码，并保存默认首页、发送快捷键、会话密度等前端偏好。
            </p>
          </div>

          <div class="dashboard-stats">
            <div class="info-tile">
              <div class="info-tile__icon">
                <el-icon><UserFilled /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ user?.name || "-" }}</strong>
                <span>{{ user?.isAdmin ? "管理员账号" : "普通账号" }}</span>
              </div>
            </div>
            <div class="info-tile">
              <div class="info-tile__icon">
                <el-icon><Monitor /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ effectiveHomeRouteLabel }}</strong>
                <span>当前默认首页</span>
              </div>
            </div>
            <div class="info-tile">
              <div class="info-tile__icon">
                <el-icon><Setting /></el-icon>
              </div>
              <div class="info-tile__copy">
                <strong>{{ preferences.sendShortcut === "enter" ? "Enter" : "Ctrl+Enter" }}</strong>
                <span>当前发送快捷键</span>
              </div>
            </div>
          </div>
        </header>

        <div class="panel-grid-2">
          <section class="soft-card content-card panel-stack">
            <div>
              <div class="section-title">个人资料</div>
              <div class="section-subtitle">同步更新你的昵称和邮箱。</div>
            </div>
            <el-form label-position="top" class="panel-stack">
              <el-form-item label="昵称">
                <el-input v-model="profileForm.name" placeholder="请输入昵称" />
              </el-form-item>
              <el-form-item label="邮箱">
                <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
              </el-form-item>
            </el-form>
            <el-button type="primary" :icon="EditPen" :loading="profileLoading" @click="saveProfile">
              保存资料
            </el-button>
          </section>

          <section class="soft-card content-card panel-stack">
            <div>
              <div class="section-title">安全设置</div>
              <div class="section-subtitle">更新密码后会立即要求重新登录。</div>
            </div>
            <el-form label-position="top" class="panel-stack">
              <el-form-item label="当前密码">
                <el-input v-model="passwordForm.current_password" type="password" show-password />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input v-model="passwordForm.new_password" type="password" show-password />
              </el-form-item>
              <el-form-item label="确认新密码">
                <el-input v-model="passwordForm.confirm_password" type="password" show-password />
              </el-form-item>
            </el-form>
            <el-button type="primary" :icon="Lock" :loading="passwordLoading" @click="savePassword">
              更新密码
            </el-button>
          </section>
        </div>

        <section class="soft-card content-card panel-stack">
          <div>
            <div class="section-title">偏好设置</div>
            <div class="section-subtitle">这些配置会保存在浏览器本地，并立即作用到前端页面。</div>
          </div>

          <div class="panel-grid-2">
            <el-form label-position="top" class="panel-stack">
              <el-form-item label="默认首页">
                <el-select v-model="preferences.homeRoute">
                  <el-option
                    v-for="item in homeRouteOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="发送快捷键">
                <el-radio-group v-model="preferences.sendShortcut">
                  <el-radio-button label="enter">Enter 发送</el-radio-button>
                  <el-radio-button label="ctrl-enter">Ctrl+Enter 发送</el-radio-button>
                </el-radio-group>
              </el-form-item>
            </el-form>

            <el-form label-position="top" class="panel-stack">
              <el-form-item label="会话列表密度">
                <el-radio-group v-model="preferences.sessionDensity">
                  <el-radio-button label="comfy">舒展</el-radio-button>
                  <el-radio-button label="compact">紧凑</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="知识库提示语">
                <el-switch
                  v-model="preferences.showKnowledgeTips"
                  inline-prompt
                  active-text="显示"
                  inactive-text="隐藏"
                />
              </el-form-item>
            </el-form>
          </div>

          <div class="settings-preview">
            <div class="settings-preview__item">
              <span>默认进入</span>
              <strong>{{ effectiveHomeRouteLabel }}</strong>
            </div>
            <div class="settings-preview__item">
              <span>发送方式</span>
              <strong>{{ preferences.sendShortcut === "enter" ? "Enter" : "Ctrl+Enter" }}</strong>
            </div>
            <div class="settings-preview__item">
              <span>会话密度</span>
              <strong>{{ preferences.sessionDensity === "compact" ? "紧凑" : "舒展" }}</strong>
            </div>
          </div>

          <el-button type="primary" :loading="preferenceLoading" @click="saveUserPreferences">
            保存偏好设置
          </el-button>
        </section>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  overflow: hidden;
}

.settings-preview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.settings-preview__item {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(247, 250, 255, 0.92);
}

.settings-preview__item span,
.settings-preview__item strong {
  display: block;
}

.settings-preview__item span {
  color: var(--muted);
  font-size: 0.82rem;
}

.settings-preview__item strong {
  margin-top: 6px;
  font-size: 0.95rem;
}

@media (max-width: 1080px) {
  .settings-page {
    overflow: auto;
  }

  .settings-preview {
    grid-template-columns: 1fr;
  }
}
</style>
