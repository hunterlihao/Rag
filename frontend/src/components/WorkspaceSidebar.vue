<script setup>
import { computed, ref } from "vue";
import {
  MessageCircle, Database, Settings, Shield, Plus, Clock, Trash2,
  PanelLeftOpen, PanelLeftClose, LogOut, Menu, X, Search, Loader2,
  Sparkles, ChevronUp,
} from "lucide-vue-next";
import { formatRelativeTime } from "@/services/workspace";
import DeleteConfirmDialog from "@/components/DeleteConfirmDialog.vue";

const props = defineProps({
  user: { type: Object, required: true },
  sessions: { type: Array, required: true },
  navItems: { type: Array, default: () => [] },
  currentRouteName: { type: String, default: "" },
  activeSessionId: { type: String, default: "" },
  searchValue: { type: String, default: "" },
  busy: { type: Boolean, default: false },
  deletingSessionId: { type: String, default: "" },
  sessionDensity: { type: String, default: "comfy" },
  collapsed: { type: Boolean, default: false },
});

const emit = defineEmits([
  "create-session", "select-session", "delete-session",
  "update:search-value", "navigate", "logout", "toggle-collapse",
]);

const deleteTarget = ref(null);
const showDeleteConfirm = ref(false);
const showLogoutConfirm = ref(false);
const mobileOpen = ref(false);
const showUserMenu = ref(false);

const userInitial = computed(() => (props.user?.name || "U").slice(0, 1).toUpperCase());
const isDense = computed(() => props.sessionDensity === "compact");

const navIconMap = {
  workspace: MessageCircle, knowledge: Database,
  settings: Settings, "admin-users": Shield,
};
function navIcon(name) { return navIconMap[name] || MessageCircle; }
function isActive(name) { return props.currentRouteName === name; }

function requestDelete(session) {
  if (!session?.id || props.busy || props.deletingSessionId) return;
  deleteTarget.value = session; showDeleteConfirm.value = true;
}
function confirmDelete() {
  if (!deleteTarget.value?.id) return;
  emit("delete-session", deleteTarget.value.id);
  showDeleteConfirm.value = false; deleteTarget.value = null;
}
function confirmLogout() { showLogoutConfirm.value = false; showUserMenu.value = false; emit("logout"); }
function openLogoutConfirm() { showUserMenu.value = false; showLogoutConfirm.value = true; }
function toggleUserMenu() { showUserMenu.value = !showUserMenu.value; }
function goSettings() { showUserMenu.value = false; emit("navigate", "settings"); }
function goHome() { mobileOpen.value = false; emit("navigate", "workspace"); }
function handleNav(name) { mobileOpen.value = false; showUserMenu.value = false; emit("navigate", name); }
function handleSelectSession(id) { mobileOpen.value = false; emit("select-session", id); }
function onSearchInput(e) { emit("update:search-value", e.target.value); }
</script>

<template>
  <!-- ===== Mobile menu button ===== -->
  <button @click="mobileOpen = true" class="md:hidden fixed top-4 left-4 z-40 w-11 h-11 flex items-center justify-center bg-white border border-zinc-200 rounded-xl shadow-sm">
    <Menu class="w-5 h-5 text-zinc-700" />
  </button>

  <!-- ===== Mobile overlay ===== -->
  <div v-if="mobileOpen" class="md:hidden fixed inset-0 z-40 bg-black/40" @click="mobileOpen = false" />

  <!-- ===== Mobile sidebar drawer ===== -->
  <aside :class="['md:hidden fixed top-0 left-0 z-50 h-full transition-transform duration-300 bg-white border-r border-zinc-100 flex flex-col w-64', mobileOpen ? 'translate-x-0' : '-translate-x-full']">
    <button @click="mobileOpen = false" class="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-zinc-500 hover:text-zinc-900 z-10"><X class="w-5 h-5" /></button>
    <div class="px-4 py-6 flex items-center justify-between">
      <button @click="goHome" class="flex items-center gap-3 hover:opacity-80 transition-opacity">
        <div class="w-9 h-9 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25">
          <Sparkles class="w-5 h-5 text-white" />
        </div>
        <span class="text-sm font-semibold text-zinc-900 tracking-tight">RAG Studio</span>
      </button>
      <button @click="emit('toggle-collapse')" class="p-1.5 hover:bg-zinc-100 rounded-lg transition-colors">
        <PanelLeftClose class="w-4 h-4 text-zinc-400" />
      </button>
    </div>
    <div class="px-4 mb-3">
      <button @click="emit('create-session'); mobileOpen = false" :disabled="busy" class="w-full flex items-center justify-between px-3 py-2.5 text-sm font-medium text-zinc-700 bg-zinc-50 hover:bg-zinc-100 rounded-xl transition-colors disabled:opacity-50">
        <span class="flex items-center gap-2"><Plus class="w-4 h-4" /> 新对话</span>
        <span class="text-xs text-zinc-400 bg-zinc-200/60 px-1.5 py-0.5 rounded">Ctrl K</span>
      </button>
    </div>
    <nav class="px-3 space-y-0.5">
      <button v-for="item in navItems" :key="item.name" @click="handleNav(item.name)" :class="['w-full flex items-center gap-3 px-3 py-2.5 text-sm rounded-xl transition-colors', isActive(item.name) ? 'bg-zinc-100 text-zinc-900 font-medium' : 'text-zinc-600 hover:bg-zinc-50']">
        <component :is="navIcon(item.name)" class="w-4 h-4 flex-shrink-0" />
        <span>{{ item.label }}</span>
      </button>
    </nav>
    <div class="flex-1 overflow-hidden flex flex-col px-3 mt-4">
      <div class="flex items-center justify-between px-1 mb-2">
        <span class="text-xs font-medium text-zinc-400 uppercase tracking-wider">历史对话</span>
        <span class="text-xs text-zinc-400 bg-zinc-100 px-1.5 py-0.5 rounded-full numeric">{{ sessions.length }}</span>
      </div>
      <div class="relative mb-2">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-400" />
        <input :value="searchValue" @input="onSearchInput" placeholder="搜索..." :disabled="busy" class="w-full h-8 pl-8 pr-3 bg-zinc-50 border border-zinc-100 rounded-lg text-xs focus:outline-none focus:border-zinc-200 transition-colors" />
      </div>
      <div class="flex-1 overflow-y-auto space-y-0.5">
        <div v-for="s in sessions" :key="s.id" :class="['group flex items-center gap-1 rounded-xl transition-colors cursor-pointer', s.id === activeSessionId ? 'bg-zinc-100' : 'hover:bg-zinc-50', isDense ? 'px-2 py-1.5' : 'px-3 py-2']">
          <button @click="handleSelectSession(s.id)" :disabled="busy" class="flex-1 text-left min-w-0">
            <div class="text-sm font-medium text-zinc-700 truncate">{{ s.title }}</div>
            <div :class="['flex items-center gap-2 text-xs text-zinc-400', isDense ? 'mt-0.5' : 'mt-1']">
              <span class="numeric">{{ s.messageCount || 0 }} 条</span>
              <Clock class="w-3 h-3" />
              <span>{{ formatRelativeTime(s.updatedAt) }}</span>
            </div>
          </button>
          <button @click.stop="requestDelete(s)" :disabled="busy" class="p-1 text-zinc-300 hover:text-red-500 hover:bg-red-50 rounded transition-all shrink-0">
            <Loader2 v-if="deletingSessionId === s.id" class="w-3.5 h-3.5 animate-spin" />
            <Trash2 v-else class="w-3.5 h-3.5" />
          </button>
        </div>
        <div v-if="!sessions.length" class="text-center text-xs text-zinc-400 py-8">暂无历史对话</div>
      </div>
    </div>
    <!-- User area with popup -->
    <div class="border-t border-zinc-100 p-3 relative">
      <button @click="toggleUserMenu" class="w-full flex items-center gap-3 px-2 py-2 hover:bg-zinc-50 rounded-xl transition-colors">
        <div class="w-8 h-8 rounded-full bg-zinc-200 flex items-center justify-center text-xs font-semibold text-zinc-600 shrink-0">
          {{ userInitial }}
        </div>
        <div class="flex-1 text-left min-w-0">
          <div class="text-xs font-medium text-zinc-700 truncate">{{ user.name }}</div>
          <div class="text-[10px] text-zinc-400 truncate">{{ user.email }}</div>
        </div>
        <ChevronUp :class="['w-4 h-4 text-zinc-400 transition-transform', showUserMenu && 'rotate-180']" />
      </button>

      <!-- User popup menu -->
      <div v-if="showUserMenu" class="absolute bottom-full left-3 right-3 mb-2 bg-white rounded-xl shadow-lg border border-zinc-200 overflow-hidden z-50">
        <div class="px-3 py-2.5 border-b border-zinc-100">
          <div class="text-xs font-medium text-zinc-700">{{ user.name }}</div>
          <div class="text-[10px] text-zinc-400">{{ user.isAdmin ? '管理员' : '普通用户' }}</div>
        </div>
        <button @click="goSettings" class="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-zinc-600 hover:bg-zinc-50 transition-colors">
          <Settings class="w-4 h-4 text-zinc-400" /> 设置中心
        </button>
        <button @click="openLogoutConfirm" class="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors">
          <LogOut class="w-4 h-4" /> 退出登录
        </button>
      </div>
    </div>
  </aside>

  <!-- ===== Desktop sidebar ===== -->
  <aside class="hidden md:flex flex-col h-full bg-white border-r border-zinc-100 w-64 shrink-0 transition-[margin-left] duration-300" :class="{ '-ml-64': collapsed }">
    <div class="px-4 py-6 flex items-center justify-between">
      <button @click="goHome" class="flex items-center gap-3 hover:opacity-80 transition-opacity">
        <div class="w-9 h-9 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25">
          <Sparkles class="w-5 h-5 text-white" />
        </div>
        <span class="text-sm font-semibold text-zinc-900 tracking-tight">RAG Studio</span>
      </button>
      <button @click="emit('toggle-collapse')" class="p-1.5 hover:bg-zinc-100 rounded-lg transition-colors" title="隐藏侧边栏">
        <PanelLeftClose class="w-4 h-4 text-zinc-400" />
      </button>
    </div>

    <div class="px-4 mb-3">
      <button @click="emit('create-session')" :disabled="busy" class="w-full flex items-center justify-between px-3 py-2.5 text-sm font-medium text-zinc-700 bg-zinc-50 hover:bg-zinc-100 rounded-xl transition-colors disabled:opacity-50">
        <span class="flex items-center gap-2"><Plus class="w-4 h-4" /> 新对话</span>
        <span class="text-xs text-zinc-400 bg-zinc-200/60 px-1.5 py-0.5 rounded">Ctrl K</span>
      </button>
    </div>

    <nav class="px-3 space-y-0.5">
      <button v-for="item in navItems" :key="item.name" @click="handleNav(item.name)" :class="['w-full flex items-center gap-3 px-3 py-2.5 text-sm rounded-xl transition-colors', isActive(item.name) ? 'bg-zinc-100 text-zinc-900 font-medium' : 'text-zinc-600 hover:bg-zinc-50']">
        <component :is="navIcon(item.name)" class="w-4 h-4 flex-shrink-0" />
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="flex-1 overflow-hidden flex flex-col px-3 mt-4">
      <div class="flex items-center justify-between px-1 mb-2">
        <span class="text-xs font-medium text-zinc-400 uppercase tracking-wider">历史对话</span>
        <span class="text-xs text-zinc-400 bg-zinc-100 px-1.5 py-0.5 rounded-full numeric">{{ sessions.length }}</span>
      </div>
      <div class="relative mb-2">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-400" />
        <input :value="searchValue" @input="onSearchInput" placeholder="搜索历史对话" :disabled="busy" class="w-full h-8 pl-8 pr-3 bg-zinc-50 border border-zinc-100 rounded-lg text-xs focus:outline-none focus:border-zinc-200 transition-colors" />
      </div>
      <div class="flex-1 overflow-y-auto space-y-0.5">
        <div v-for="s in sessions" :key="s.id" :class="['group flex items-center gap-1 rounded-xl transition-colors cursor-pointer', s.id === activeSessionId ? 'bg-zinc-100' : 'hover:bg-zinc-50', isDense ? 'px-2 py-1.5' : 'px-3 py-2']">
          <button @click="handleSelectSession(s.id)" :disabled="busy" class="flex-1 text-left min-w-0">
            <div class="text-sm font-medium text-zinc-700 truncate">{{ s.title }}</div>
            <div :class="['flex items-center gap-2 text-xs text-zinc-400', isDense ? 'mt-0.5' : 'mt-1']">
              <span class="numeric">{{ s.messageCount || 0 }} 条</span>
              <Clock class="w-3 h-3" />
              <span>{{ formatRelativeTime(s.updatedAt) }}</span>
            </div>
          </button>
          <button @click.stop="requestDelete(s)" :disabled="busy" class="p-1 text-zinc-300 hover:text-red-500 hover:bg-red-50 rounded transition-all shrink-0">
            <Loader2 v-if="deletingSessionId === s.id" class="w-3.5 h-3.5 animate-spin" />
            <Trash2 v-else class="w-3.5 h-3.5" />
          </button>
        </div>
        <div v-if="!sessions.length" class="text-center text-xs text-zinc-400 py-8">暂无历史对话</div>
      </div>
    </div>

    <!-- User area with popup -->
    <div class="border-t border-zinc-100 p-3 relative">
      <button @click="toggleUserMenu" class="w-full flex items-center gap-3 px-2 py-2 hover:bg-zinc-50 rounded-xl transition-colors">
        <div class="w-8 h-8 rounded-full bg-zinc-200 flex items-center justify-center text-xs font-semibold text-zinc-600 shrink-0">
          {{ userInitial }}
        </div>
        <div class="flex-1 text-left min-w-0">
          <div class="text-xs font-medium text-zinc-700 truncate">{{ user.name }}</div>
          <div class="text-[10px] text-zinc-400 truncate">{{ user.email }}</div>
        </div>
        <ChevronUp :class="['w-4 h-4 text-zinc-400 transition-transform', showUserMenu && 'rotate-180']" />
      </button>

      <!-- User popup menu -->
      <div v-if="showUserMenu" class="absolute bottom-full left-3 right-3 mb-2 bg-white rounded-xl shadow-lg border border-zinc-200 overflow-hidden z-50">
        <div class="px-3 py-2.5 border-b border-zinc-100">
          <div class="text-xs font-medium text-zinc-700">{{ user.name }}</div>
          <div class="text-[10px] text-zinc-400">{{ user.isAdmin ? '管理员' : '普通用户' }}</div>
        </div>
        <button @click="goSettings" class="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-zinc-600 hover:bg-zinc-50 transition-colors">
          <Settings class="w-4 h-4 text-zinc-400" /> 设置中心
        </button>
        <button @click="openLogoutConfirm" class="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors">
          <LogOut class="w-4 h-4" /> 退出登录
        </button>
      </div>
    </div>
  </aside>

  <!-- ===== Floating button when sidebar hidden (centered vertically) ===== -->
  <button
    v-if="collapsed"
    @click="emit('toggle-collapse')"
    class="hidden md:flex fixed left-3 top-1/2 -translate-y-1/2 z-30 w-9 h-9 items-center justify-center bg-white border border-zinc-200 rounded-lg shadow-sm hover:bg-zinc-50 transition-colors"
    title="显示侧边栏"
  >
    <PanelLeftOpen class="w-4 h-4 text-zinc-500" />
  </button>

  <!-- ===== Modals ===== -->
  <DeleteConfirmDialog v-model="showDeleteConfirm" title="删除会话" confirm-text="确认删除" :summary="deleteTarget ? `确认删除会话「${deleteTarget.title}」吗？` : ''" hint="删除后，该会话下的消息记录会一起移除。" :items="deleteTarget ? [{ id: deleteTarget.id, name: deleteTarget.title }] : []" extra="删除完成后无法从页面恢复。" @confirm="confirmDelete" />
  <DeleteConfirmDialog v-model="showLogoutConfirm" tone="primary" title="退出登录" badge-text="需要重新登录" confirm-text="确认退出" summary="确定要退出当前账号吗？" hint="退出后，将返回登录页。需要重新登录才能继续访问当前工作区。" extra="这不会删除任何会话和知识库数据。" @confirm="confirmLogout" />
</template>
