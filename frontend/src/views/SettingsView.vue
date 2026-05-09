<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeft, User, Mail, Lock, Loader2, AlertCircle, CheckCircle, Settings, Home, Keyboard, LayoutGrid, Eye } from "lucide-vue-next";

import ActionBusyOverlay from "@/components/ActionBusyOverlay.vue";
import WorkspaceSidebar from "@/components/WorkspaceSidebar.vue";
import { getCurrentUser, logout, replaceCurrentUser } from "@/services/auth";
import { buildRouteLocation, buildSidebarNavItems, normalizeShellSession } from "@/services/shell";
import { buildDefaultPreferences, getPreferences, normalizePreferences, savePreferences, updateMyPassword, updateMyProfile } from "@/services/user";
import { createSession, deleteSession, fetchSessions } from "@/services/workspace";

const route = useRoute();
const router = useRouter();
const user = ref(getCurrentUser());
const preferences = ref(getPreferences(user.value));
const workspace = reactive({ sessions: [] });
const pageLoading = ref(false);
const profileLoading = ref(false);
const passwordLoading = ref(false);
const preferenceLoading = ref(false);
const deletingSessionId = ref("");
const sessionSearch = ref("");
const activeSessionId = ref("");
const profileError = ref("");
const profileSuccess = ref("");
const passwordError = ref("");
const passwordSuccess = ref("");

const sidebarBusy = computed(() => !!deletingSessionId.value);
const navItems = computed(() => buildSidebarNavItems(user.value));

const filteredSessions = computed(() => {
  const kw = sessionSearch.value.trim().toLowerCase();
  return [...workspace.sessions]
    .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
    .filter((s) => !kw || `${s.title} ${s.preview || ""}`.toLowerCase().includes(kw));
});

const busyOverlayState = computed(() => ({
  visible: !!deletingSessionId.value,
  badgeText: "删除处理中",
  title: "正在删除会话",
  description: "会话记录正在清理。",
}));

const profileForm = reactive({ name: "", email: "" });
const passwordForm = reactive({ current_password: "", new_password: "", confirm_password: "" });

const homeRouteOptions = computed(() => {
  const opts = [
    { value: "workspace", label: "问答主页" },
    { value: "knowledge", label: "知识库管理" },
    { value: "settings", label: "设置中心" },
  ];
  if (user.value?.isAdmin) opts.push({ value: "admin-users", label: "用户管理" });
  return opts;
});

const effectiveHomeRoute = computed(() => {
  const ids = homeRouteOptions.value.map((o) => o.value);
  return ids.includes(preferences.value.homeRoute) ? preferences.value.homeRoute : "workspace";
});

const effectiveHomeRouteLabel = computed(() => {
  return homeRouteOptions.value.find((o) => o.value === effectiveHomeRoute.value)?.label || "问答主页";
});

function syncProfileForm() {
  profileForm.name = user.value?.name || "";
  profileForm.email = user.value?.email || "";
}

async function refreshSessions() {
  const list = await fetchSessions();
  workspace.sessions = list.map((s) => ({ ...normalizeShellSession(s), welcomeMessage: "" }));
  if (workspace.sessions.length) activeSessionId.value = workspace.sessions[0].id;
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

async function saveProfile() {
  profileError.value = ""; profileSuccess.value = "";
  if (!profileForm.name.trim() || !profileForm.email.trim()) { profileError.value = "请填写完整的个人信息"; return; }
  profileLoading.value = true;
  try {
    const result = await updateMyProfile({ name: profileForm.name, email: profileForm.email });
    if (result.user) user.value = replaceCurrentUser(result.user);
    profileSuccess.value = result.message || "个人信息已更新";
    setTimeout(() => { profileSuccess.value = ""; }, 3000);
  } catch (err) {
    profileError.value = err.message || "保存失败";
  } finally {
    profileLoading.value = false;
  }
}

async function savePassword() {
  passwordError.value = ""; passwordSuccess.value = "";
  if (!passwordForm.current_password || !passwordForm.new_password) { passwordError.value = "请填写完整的密码信息"; return; }
  if (passwordForm.new_password.length < 6) { passwordError.value = "新密码至少需要6位"; return; }
  if (passwordForm.new_password !== passwordForm.confirm_password) { passwordError.value = "两次输入的密码不一致"; return; }
  passwordLoading.value = true;
  try {
    const result = await updateMyPassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    });
    passwordSuccess.value = result.message || "密码已更新，请重新登录。";
    passwordForm.current_password = ""; passwordForm.new_password = ""; passwordForm.confirm_password = "";
  } catch (err) {
    passwordError.value = err.message || "修改失败";
  } finally {
    passwordLoading.value = false;
  }
}

function saveUserPreferences() {
  preferenceLoading.value = true;
  preferences.value = savePreferences({ ...preferences.value }, user.value);
  setTimeout(() => { preferenceLoading.value = false; }, 300);
}

onMounted(async () => {
  pageLoading.value = true;
  try {
    user.value = getCurrentUser();
    preferences.value = getPreferences(user.value);
    syncProfileForm();
    await refreshSessions();
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
      :current-route-name="'settings'"
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
        <span class="text-sm font-medium text-zinc-700">设置中心</span>
      </header>

      <div class="flex-1 overflow-y-auto">
        <div v-if="pageLoading" class="flex items-center justify-center h-full">
          <div class="flex gap-1.5">
            <span class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" />
            <span class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>
        </div>

        <div v-else class="max-w-3xl mx-auto px-6 py-6 space-y-6">
          <!-- Hero -->
          <div>
            <span class="inline-flex items-center px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-500 text-xs font-medium mb-3">设置中心</span>
            <h1 class="text-xl font-bold text-zinc-900 tracking-tight mb-1">个人设置与偏好</h1>
            <p class="text-sm text-zinc-500">修改资料、密码和个性化工作台偏好。</p>
          </div>

          <!-- Info tiles -->
          <div class="grid grid-cols-3 gap-3">
            <div class="bg-white border border-zinc-200 rounded-xl p-4">
              <div class="flex items-center gap-2 mb-1">
                <User class="w-3.5 h-3.5 text-zinc-400" />
                <span class="text-[11px] text-zinc-400">用户</span>
              </div>
              <p class="text-sm font-semibold text-zinc-900">{{ user?.name || '—' }}</p>
              <p class="text-[11px] text-zinc-400">{{ user?.isAdmin ? '管理员' : '普通用户' }}</p>
            </div>
            <div class="bg-white border border-zinc-200 rounded-xl p-4">
              <div class="flex items-center gap-2 mb-1">
                <Home class="w-3.5 h-3.5 text-zinc-400" />
                <span class="text-[11px] text-zinc-400">首页路由</span>
              </div>
              <p class="text-sm font-semibold text-zinc-900">{{ effectiveHomeRouteLabel }}</p>
            </div>
            <div class="bg-white border border-zinc-200 rounded-xl p-4">
              <div class="flex items-center gap-2 mb-1">
                <Keyboard class="w-3.5 h-3.5 text-zinc-400" />
                <span class="text-[11px] text-zinc-400">发送方式</span>
              </div>
              <p class="text-sm font-semibold text-zinc-900">{{ preferences.sendShortcut === 'ctrl-enter' ? 'Ctrl+Enter 发送' : 'Enter 发送' }}</p>
            </div>
          </div>

          <!-- Profile + Password -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Profile -->
            <div class="bg-white border border-zinc-200 rounded-xl p-6">
              <h2 class="text-sm font-semibold text-zinc-900 mb-4">个人资料</h2>
              <div class="space-y-3">
                <div>
                  <label class="block text-xs font-medium text-zinc-600 mb-1">用户名</label>
                  <div class="relative">
                    <User class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                    <input v-model="profileForm.name" class="w-full h-9 pl-9 pr-3 bg-zinc-50 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all" placeholder="用户名" />
                  </div>
                </div>
                <div>
                  <label class="block text-xs font-medium text-zinc-600 mb-1">邮箱</label>
                  <div class="relative">
                    <Mail class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                    <input v-model="profileForm.email" type="email" class="w-full h-9 pl-9 pr-3 bg-zinc-50 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all" placeholder="email@example.com" />
                  </div>
                </div>
                <div v-if="profileError" class="flex items-center gap-2 bg-red-50 text-red-600 px-3 py-2 rounded-lg text-xs"><AlertCircle class="w-3.5 h-3.5" /> {{ profileError }}</div>
                <div v-if="profileSuccess" class="flex items-center gap-2 bg-emerald-50 text-emerald-700 px-3 py-2 rounded-lg text-xs"><CheckCircle class="w-3.5 h-3.5" /> {{ profileSuccess }}</div>
                <button @click="saveProfile" :disabled="profileLoading" class="px-4 py-2 bg-zinc-900 text-white text-xs font-medium rounded-lg hover:bg-zinc-800 transition-colors flex items-center gap-2 disabled:opacity-70">
                  <template v-if="profileLoading">
                    <div class="flex gap-1">
                      <span class="w-1 h-1 bg-white rounded-full animate-bounce" />
                      <span class="w-1 h-1 bg-white rounded-full animate-bounce" style="animation-delay: 150ms" />
                      <span class="w-1 h-1 bg-white rounded-full animate-bounce" style="animation-delay: 300ms" />
                    </div>
                  </template>
                  保存资料
                </button>
              </div>
            </div>

            <!-- Password -->
            <div class="bg-white border border-zinc-200 rounded-xl p-6">
              <h2 class="text-sm font-semibold text-zinc-900 mb-4">安全设置</h2>
              <div class="space-y-3">
                <div>
                  <label class="block text-xs font-medium text-zinc-600 mb-1">当前密码</label>
                  <div class="relative">
                    <Lock class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                    <input v-model="passwordForm.current_password" type="password" class="w-full h-9 pl-9 pr-3 bg-zinc-50 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all" placeholder="当前密码" />
                  </div>
                </div>
                <div>
                  <label class="block text-xs font-medium text-zinc-600 mb-1">新密码</label>
                  <div class="relative">
                    <Lock class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                    <input v-model="passwordForm.new_password" type="password" class="w-full h-9 pl-9 pr-3 bg-zinc-50 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all" placeholder="新密码（至少6位）" />
                  </div>
                </div>
                <div>
                  <label class="block text-xs font-medium text-zinc-600 mb-1">确认新密码</label>
                  <div class="relative">
                    <Lock class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                    <input v-model="passwordForm.confirm_password" type="password" class="w-full h-9 pl-9 pr-3 bg-zinc-50 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all" placeholder="再次输入新密码" />
                  </div>
                </div>
                <div v-if="passwordError" class="flex items-center gap-2 bg-red-50 text-red-600 px-3 py-2 rounded-lg text-xs"><AlertCircle class="w-3.5 h-3.5" /> {{ passwordError }}</div>
                <div v-if="passwordSuccess" class="flex items-center gap-2 bg-emerald-50 text-emerald-700 px-3 py-2 rounded-lg text-xs"><CheckCircle class="w-3.5 h-3.5" /> {{ passwordSuccess }}</div>
                <button @click="savePassword" :disabled="passwordLoading" class="px-4 py-2 bg-zinc-900 text-white text-xs font-medium rounded-lg hover:bg-zinc-800 transition-colors flex items-center gap-2 disabled:opacity-70">
                  <template v-if="passwordLoading">
                    <div class="flex gap-1">
                      <span class="w-1 h-1 bg-white rounded-full animate-bounce" />
                      <span class="w-1 h-1 bg-white rounded-full animate-bounce" style="animation-delay: 150ms" />
                      <span class="w-1 h-1 bg-white rounded-full animate-bounce" style="animation-delay: 300ms" />
                    </div>
                  </template>
                  更新密码
                </button>
              </div>
            </div>
          </div>

          <!-- Preferences -->
          <div class="bg-white border border-zinc-200 rounded-xl p-6">
            <h2 class="text-sm font-semibold text-zinc-900 mb-4">工作台偏好</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <!-- Home route -->
              <div>
                <label class="block text-xs font-medium text-zinc-600 mb-2">默认首页</label>
                <select
                  :value="effectiveHomeRoute"
                  @change="preferences.homeRoute = ($event.target).value"
                  class="w-full h-9 px-3 bg-zinc-50 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 transition-all"
                >
                  <option v-for="opt in homeRouteOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>

              <!-- Send shortcut -->
              <div>
                <label class="block text-xs font-medium text-zinc-600 mb-2">发送快捷键</label>
                <div class="flex gap-3">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input v-model="preferences.sendShortcut" type="radio" value="enter" class="w-4 h-4 text-zinc-900" />
                    <span class="text-sm text-zinc-700">Enter 发送</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input v-model="preferences.sendShortcut" type="radio" value="ctrl-enter" class="w-4 h-4 text-zinc-900" />
                    <span class="text-sm text-zinc-700">Ctrl+Enter 发送</span>
                  </label>
                </div>
              </div>

              <!-- Session density -->
              <div>
                <label class="block text-xs font-medium text-zinc-600 mb-2">会话列表密度</label>
                <div class="flex gap-3">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input v-model="preferences.sessionDensity" type="radio" value="comfy" class="w-4 h-4 text-zinc-900" />
                    <span class="text-sm text-zinc-700">舒展</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input v-model="preferences.sessionDensity" type="radio" value="compact" class="w-4 h-4 text-zinc-900" />
                    <span class="text-sm text-zinc-700">紧凑</span>
                  </label>
                </div>
              </div>

              <!-- Knowledge tips toggle -->
              <div>
                <label class="block text-xs font-medium text-zinc-600 mb-2">知识库提示语</label>
                <div class="flex gap-3">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input v-model="preferences.showKnowledgeTips" type="radio" :value="true" class="w-4 h-4 text-zinc-900" />
                    <span class="text-sm text-zinc-700">显示</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input v-model="preferences.showKnowledgeTips" type="radio" :value="false" class="w-4 h-4 text-zinc-900" />
                    <span class="text-sm text-zinc-700">隐藏</span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Preview -->
            <div class="mt-4 pt-4 border-t border-zinc-100">
              <span class="text-xs text-zinc-400">当前设置预览</span>
              <div class="flex flex-wrap gap-2 mt-2">
                <span class="px-2.5 py-1 bg-zinc-100 rounded-full text-xs text-zinc-600">首页：{{ effectiveHomeRouteLabel }}</span>
                <span class="px-2.5 py-1 bg-zinc-100 rounded-full text-xs text-zinc-600">发送：{{ preferences.sendShortcut === 'ctrl-enter' ? 'Ctrl+Enter' : 'Enter' }}</span>
                <span class="px-2.5 py-1 bg-zinc-100 rounded-full text-xs text-zinc-600">密度：{{ preferences.sessionDensity === 'compact' ? '紧凑' : '舒展' }}</span>
                <span class="px-2.5 py-1 bg-zinc-100 rounded-full text-xs text-zinc-600">提示：{{ preferences.showKnowledgeTips ? '开' : '关' }}</span>
              </div>
            </div>

            <button @click="saveUserPreferences" :disabled="preferenceLoading" class="mt-4 px-4 py-2 bg-zinc-900 text-white text-xs font-medium rounded-lg hover:bg-zinc-800 transition-colors flex items-center gap-2 disabled:opacity-70">
              <template v-if="preferenceLoading">
                <div class="flex gap-1">
                  <span class="w-1 h-1 bg-white rounded-full animate-bounce" />
                  <span class="w-1 h-1 bg-white rounded-full animate-bounce" style="animation-delay: 150ms" />
                  <span class="w-1 h-1 bg-white rounded-full animate-bounce" style="animation-delay: 300ms" />
                </div>
              </template>
              保存偏好设置
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
