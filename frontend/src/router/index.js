import { createRouter, createWebHistory } from "vue-router";

import { ensureAuthenticatedUser, getCurrentSession } from "@/services/auth";
import { resolveHomeRoute } from "@/services/user";
import AdminUsersView from "@/views/AdminUsersView.vue";
import KnowledgeView from "@/views/KnowledgeView.vue";
import LoginView from "@/views/LoginView.vue";
import RegisterView from "@/views/RegisterView.vue";
import SettingsView from "@/views/SettingsView.vue";
import WorkspaceView from "@/views/WorkspaceView.vue";

const routes = [
  {
    path: "/",
    redirect: () => {
      return { name: resolveHomeRoute(getCurrentSession()?.user) };
    },
  },
  {
    path: "/login",
    name: "login",
    component: LoginView,
    meta: { guestOnly: true },
  },
  {
    path: "/register",
    name: "register",
    component: RegisterView,
    meta: { guestOnly: true },
  },
  {
    path: "/workspace",
    name: "workspace",
    component: WorkspaceView,
    meta: { requiresAuth: true },
  },
  {
    path: "/knowledge",
    name: "knowledge",
    component: KnowledgeView,
    meta: { requiresAuth: true },
  },
  {
    path: "/admin/users",
    name: "admin-users",
    component: AdminUsersView,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: "/settings",
    name: "settings",
    component: SettingsView,
    meta: { requiresAuth: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const hasToken = Boolean(getCurrentSession()?.token);
  const shouldLoadUser = to.meta.requiresAuth || to.meta.requiresAdmin || to.meta.guestOnly;
  const user = hasToken && shouldLoadUser ? await ensureAuthenticatedUser() : null;

  if (to.meta.requiresAuth && !user) {
    return { name: "login" };
  }

  if (to.meta.requiresAdmin && !user?.isAdmin) {
    return { name: "workspace" };
  }

  if (to.meta.guestOnly && hasToken && user) {
    return { name: resolveHomeRoute(user) };
  }

  return true;
});

export default router;
