<script setup>
import { computed, ref } from "vue";
import {
  ChatDotRound,
  Clock,
  Delete,
  EditPen,
  Expand,
  Fold,
  Plus,
  Search,
  SwitchButton,
} from "@element-plus/icons-vue";

import DeleteConfirmDialog from "@/components/DeleteConfirmDialog.vue";
import { formatRelativeTime } from "@/services/workspace";

const props = defineProps({
  user: {
    type: Object,
    required: true,
  },
  sessions: {
    type: Array,
    required: true,
  },
  navItems: {
    type: Array,
    default: () => [],
  },
  currentRouteName: {
    type: String,
    default: "",
  },
  activeSessionId: {
    type: String,
    default: "",
  },
  searchValue: {
    type: String,
    default: "",
  },
  busy: {
    type: Boolean,
    default: false,
  },
  deletingSessionId: {
    type: String,
    default: "",
  },
  sessionDensity: {
    type: String,
    default: "comfy",
  },
  collapsed: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits([
  "create-session",
  "select-session",
  "delete-session",
  "update:search-value",
  "navigate",
  "logout",
  "toggle-collapse",
]);

const userInitial = computed(() => props.user.name?.slice(0, 1)?.toUpperCase() || "U");
const deleteDialogVisible = ref(false);
const sessionPendingDelete = ref(null);
const logoutDialogVisible = ref(false);

function requestLogout() {
  if (props.busy) {
    return;
  }
  logoutDialogVisible.value = true;
}

async function requestDeleteSession(session) {
  if (!session?.id || props.busy || props.deletingSessionId) {
    return;
  }
  sessionPendingDelete.value = session;
  deleteDialogVisible.value = true;
}

function confirmDeleteSession() {
  if (!sessionPendingDelete.value?.id) {
    return;
  }
  const sessionId = sessionPendingDelete.value.id;
  deleteDialogVisible.value = false;
  sessionPendingDelete.value = null;
  emit("delete-session", sessionId);
}

function confirmLogout() {
  logoutDialogVisible.value = false;
  emit("logout");
}
</script>

<template>
  <aside
    class="workspace-sidebar"
    :class="{
      'workspace-sidebar--compact': sessionDensity === 'compact',
      'workspace-sidebar--collapsed': collapsed,
    }"
  >
    <div class="workspace-sidebar__topbar">
      <div class="workspace-sidebar__brand">
        <el-avatar :size="38" class="workspace-sidebar__avatar">{{ userInitial }}</el-avatar>
        <div class="workspace-sidebar__brand-copy">
          <strong>{{ user.name }}</strong>
          <span>RAG Studio</span>
        </div>
      </div>

      <div class="workspace-sidebar__top-actions">
        <button
          type="button"
          class="workspace-sidebar__icon-button"
          :disabled="busy"
          :title="collapsed ? '展开侧边栏' : '折叠侧边栏'"
          @click="emit('toggle-collapse')"
        >
          <el-icon><component :is="collapsed ? Expand : Fold" /></el-icon>
        </button>
        <button
          type="button"
          class="workspace-sidebar__icon-button"
          :disabled="busy"
          title="新对话"
          @click="emit('create-session')"
        >
          <el-icon><EditPen /></el-icon>
        </button>
      </div>
    </div>

    <button
      type="button"
      class="workspace-sidebar__create"
      :disabled="busy"
      title="新对话"
      @click="emit('create-session')"
    >
      <span class="workspace-sidebar__create-main">
        <el-icon><Plus /></el-icon>
        <span>新对话</span>
      </span>
      <span class="workspace-sidebar__shortcut">Ctrl K</span>
    </button>

    <div class="workspace-sidebar__nav">
      <button
        v-for="item in navItems"
        :key="item.name"
        type="button"
        class="workspace-nav-item"
        :class="{ 'workspace-nav-item--active': item.name === currentRouteName }"
        :disabled="busy"
        :title="item.label"
        @click="emit('navigate', item.name)"
      >
        <span class="workspace-nav-item__icon">
          <el-icon><component :is="item.icon" /></el-icon>
        </span>
        <span class="workspace-nav-item__label">{{ item.label }}</span>
      </button>
    </div>

    <div v-if="!collapsed" class="workspace-sidebar__history-head">
      <span>历史对话</span>
      <span class="workspace-sidebar__history-count">{{ sessions.length }}</span>
    </div>

    <el-input
      v-if="!collapsed"
      class="workspace-sidebar__search"
      :model-value="searchValue"
      :prefix-icon="Search"
      placeholder="搜索历史对话"
      :disabled="busy"
      @update:model-value="emit('update:search-value', $event)"
    />

    <el-scrollbar v-if="!collapsed" class="workspace-sidebar__list">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ 'session-item--active': session.id === activeSessionId }"
      >
        <button
          type="button"
          class="session-item__main"
          :disabled="busy"
          @click="emit('select-session', session.id)"
        >
          <div class="session-item__title">
            <el-icon><ChatDotRound /></el-icon>
            <span>{{ session.title }}</span>
          </div>
          <div class="session-item__meta">
            <span>{{ session.messageCount || 0 }} 条消息</span>
            <span class="session-item__time">
              <el-icon><Clock /></el-icon>
              <span>{{ formatRelativeTime(session.updatedAt) }}</span>
            </span>
          </div>
        </button>

        <el-button
          class="session-item__delete"
          link
          :icon="Delete"
          :disabled="busy"
          :loading="deletingSessionId === session.id"
          @click.stop="requestDeleteSession(session)"
        />
      </div>
    </el-scrollbar>

    <div class="workspace-sidebar__footer">
      <div class="workspace-sidebar__account">
        <div class="workspace-sidebar__account-name">{{ user.email }}</div>
        <div class="workspace-sidebar__account-role">
          {{ user.isAdmin ? "管理员账号" : "普通账号" }}
        </div>
      </div>
      <button type="button" class="workspace-sidebar__logout" title="退出登录" @click="requestLogout">
        <el-icon><SwitchButton /></el-icon>
        <span>退出登录</span>
      </button>
    </div>

    <DeleteConfirmDialog
      v-model="deleteDialogVisible"
      title="删除会话"
      confirm-text="确认删除"
      :summary="sessionPendingDelete ? `确认删除会话「${sessionPendingDelete.title}」吗？` : ''"
      hint="删除后，该会话下的消息记录会一起移除。"
      :items="sessionPendingDelete ? [{ id: sessionPendingDelete.id, name: sessionPendingDelete.title }] : []"
      extra="删除完成后无法从页面恢复。"
      @confirm="confirmDeleteSession"
    />

    <DeleteConfirmDialog
      v-model="logoutDialogVisible"
      tone="primary"
      title="退出登录"
      badge-text="需要重新登录"
      confirm-text="确认退出"
      summary="确定要退出当前账号吗？"
      hint="退出后，将返回登录页。需要重新登录才能继续访问当前工作区。"
      extra="这不会删除任何会话和知识库数据。"
      @confirm="confirmLogout"
    />
  </aside>
</template>

<style scoped>
.workspace-sidebar {
  height: calc(100vh - 48px);
  padding: 14px 14px 12px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.96);
  color: var(--sidebar-ink);
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: var(--shadow-soft);
  border: 1px solid rgba(32, 85, 186, 0.08);
  transition: width 0.22s ease, padding 0.22s ease;
}

.workspace-sidebar__topbar,
.workspace-sidebar__brand,
.workspace-sidebar__top-actions {
  display: flex;
  align-items: center;
}

.workspace-sidebar__topbar {
  justify-content: space-between;
  gap: 12px;
  padding: 4px 4px 8px;
}

.workspace-sidebar__brand {
  gap: 10px;
  min-width: 0;
  overflow: hidden;
}

.workspace-sidebar__avatar {
  background: linear-gradient(135deg, #1d56d9, #7aafff);
  color: #fff;
  font-weight: 800;
}

.workspace-sidebar__brand-copy {
  min-width: 0;
}

.workspace-sidebar__brand-copy strong,
.workspace-sidebar__brand-copy span {
  display: block;
}

.workspace-sidebar__brand-copy strong {
  font-size: 1.1rem;
  color: var(--ink);
}

.workspace-sidebar__brand-copy span {
  margin-top: 2px;
  color: var(--muted);
  font-size: 0.82rem;
}

.workspace-sidebar__top-actions {
  gap: 8px;
  flex: none;
}

.workspace-sidebar__icon-button {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: 12px;
  background: rgba(245, 248, 255, 0.95);
  color: var(--ink);
  cursor: pointer;
}

.workspace-sidebar__create {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(46, 108, 246, 0.18);
  border-radius: 18px;
  background: rgba(237, 244, 255, 0.88);
  color: var(--accent);
  cursor: pointer;
}

.workspace-sidebar__create-main {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
}

.workspace-sidebar__shortcut {
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(46, 108, 246, 0.08);
  color: rgba(46, 108, 246, 0.72);
  font-size: 0.76rem;
}

.workspace-sidebar__nav {
  display: grid;
  gap: 4px;
  padding: 4px 0 6px;
}

.workspace-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: none;
  border-radius: 14px;
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
}

.workspace-nav-item:hover,
.workspace-nav-item--active {
  background: rgba(240, 246, 255, 0.96);
  color: var(--accent);
}

.workspace-nav-item__icon {
  width: 22px;
  display: grid;
  place-items: center;
  font-size: 18px;
}

.workspace-nav-item__label {
  font-size: 1rem;
}

.workspace-sidebar__history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 6px 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.workspace-sidebar__history-count {
  min-width: 22px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(237, 244, 255, 0.92);
  color: var(--accent);
  text-align: center;
  font-size: 0.8rem;
}

.workspace-sidebar__search {
  margin-top: 2px;
}

.workspace-sidebar__list {
  flex: 1;
  padding-right: 4px;
}

.session-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
  padding: 8px 8px 8px 10px;
  margin-bottom: 6px;
  border-radius: 16px;
  background: transparent;
  transition: background 0.18s ease;
}

.session-item:hover,
.session-item--active {
  background: rgba(245, 248, 255, 0.98);
}

.session-item__main {
  width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
}

.session-item__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.98rem;
  font-weight: 600;
}

.session-item__title span {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.session-item__meta {
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--muted);
  font-size: 0.78rem;
}

.session-item__time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.session-item__delete {
  margin-top: 2px;
  color: rgba(20, 40, 71, 0.44);
}

.workspace-sidebar__footer {
  display: grid;
  gap: 10px;
  padding: 10px 6px 4px;
  border-top: 1px solid rgba(32, 85, 186, 0.08);
}

.workspace-sidebar__account-name {
  font-size: 0.88rem;
  color: var(--ink);
  word-break: break-all;
}

.workspace-sidebar__account-role {
  margin-top: 2px;
  color: var(--muted);
  font-size: 0.8rem;
}

.workspace-sidebar__logout {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 40px;
  border: none;
  border-radius: 14px;
  background: rgba(245, 248, 255, 0.95);
  color: var(--ink);
  cursor: pointer;
}

.workspace-sidebar--collapsed {
  padding: 14px 10px 12px;
}

.workspace-sidebar--collapsed .workspace-sidebar__topbar {
  justify-content: center;
  align-items: stretch;
  flex-direction: column;
  gap: 10px;
}

.workspace-sidebar--collapsed .workspace-sidebar__brand {
  justify-content: center;
}

.workspace-sidebar--collapsed .workspace-sidebar__brand-copy,
.workspace-sidebar--collapsed .workspace-sidebar__shortcut,
.workspace-sidebar--collapsed .workspace-nav-item__label,
.workspace-sidebar--collapsed .workspace-sidebar__account {
  display: none;
}

.workspace-sidebar--collapsed .workspace-sidebar__top-actions {
  justify-content: center;
}

.workspace-sidebar--collapsed .workspace-sidebar__create {
  justify-content: center;
  width: 52px;
  height: 52px;
  margin: 0 auto;
  padding: 0;
  border-radius: 18px;
}

.workspace-sidebar--collapsed .workspace-sidebar__create-main {
  gap: 0;
}

.workspace-sidebar--collapsed .workspace-sidebar__nav {
  justify-items: center;
}

.workspace-sidebar--collapsed .workspace-nav-item {
  justify-content: center;
  width: 100%;
  padding: 12px 0;
}

.workspace-sidebar--collapsed .workspace-nav-item__icon {
  width: auto;
}

.workspace-sidebar--collapsed .workspace-sidebar__footer {
  justify-items: center;
  padding-left: 0;
  padding-right: 0;
}

.workspace-sidebar--collapsed .workspace-sidebar__logout {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  padding: 0;
}

.workspace-sidebar--collapsed .workspace-sidebar__create-main > span,
.workspace-sidebar--collapsed .workspace-sidebar__logout span {
  display: none;
}

.workspace-sidebar--compact .session-item {
  padding: 6px 8px 6px 10px;
}

.workspace-sidebar--compact .session-item__meta {
  margin-top: 4px;
}
</style>
