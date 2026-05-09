import { appConfig } from "./config";
import { replaceCurrentUser } from "./auth";
import { requestJson } from "./http";

const SETTINGS_KEY_PREFIX = "rag.frontend.preferences";

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function getUserPreferenceKey(user = null) {
  const userId = String(user?.id || "").trim();
  return userId ? `${SETTINGS_KEY_PREFIX}.${userId}` : "";
}

export async function updateMyProfile(payload) {
  const result = await requestJson(appConfig.apiBaseUrl, "/users/me", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

  if (result.user) {
    replaceCurrentUser(result.user);
  }
  return result;
}

export async function updateMyPassword(payload) {
  return requestJson(appConfig.apiBaseUrl, "/users/me/password", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function fetchAdminUsers(keyword = "") {
  const suffix = keyword.trim() ? `?keyword=${encodeURIComponent(keyword.trim())}` : "";
  return requestJson(appConfig.apiBaseUrl, `/admin/users${suffix}`);
}

export async function createAdminUser(payload) {
  return requestJson(appConfig.apiBaseUrl, "/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateAdminUser(userId, payload) {
  return requestJson(appConfig.apiBaseUrl, `/admin/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteAdminUser(userId) {
  return requestJson(appConfig.apiBaseUrl, `/admin/users/${userId}`, {
    method: "DELETE",
  });
}

// 异步删除用户 (RabbitMQ模式)
export async function deleteAdminUserAsync(userId) {
  return requestJson(appConfig.apiBaseUrl, `/admin/users/${userId}`, {
    method: "DELETE",
  });
}

export function getPreferences(user = null) {
  const storageKey = getUserPreferenceKey(user);
  try {
    if (!storageKey) {
      return normalizePreferences({}, user);
    }

    const rawValue = localStorage.getItem(storageKey);
    return normalizePreferences(rawValue ? JSON.parse(rawValue) : {}, user);
  } catch (error) {
    return normalizePreferences({}, user);
  }
}

export function savePreferences(preferences, user = null) {
  const normalizedPreferences = normalizePreferences(preferences, user);
  const storageKey = getUserPreferenceKey(user);
  if (!storageKey) {
    return normalizedPreferences;
  }

  localStorage.setItem(storageKey, JSON.stringify(normalizedPreferences));
  return normalizedPreferences;
}

export function buildDefaultPreferences() {
  return {
    homeRoute: "workspace",
    sessionDensity: "comfy",
    sendShortcut: "enter",
    showKnowledgeTips: true,
    sidebarCollapsed: false,
    answerMode: "auto",
    chatModelId: "",
  };
}

export function normalizePreferences(preferences, user = null) {
  const defaults = buildDefaultPreferences();
  const nextPreferences = isRecord(preferences)
    ? {
        ...defaults,
        ...preferences,
      }
    : { ...defaults };

  const candidateRoute = String(nextPreferences.homeRoute || defaults.homeRoute).trim();
  const routeWhitelist = new Set(["workspace", "knowledge", "settings", "admin-users"]);
  nextPreferences.homeRoute = routeWhitelist.has(candidateRoute)
    ? candidateRoute
    : defaults.homeRoute;

  if (nextPreferences.homeRoute === "admin-users" && !user?.isAdmin) {
    nextPreferences.homeRoute = defaults.homeRoute;
  }

  nextPreferences.sessionDensity =
    nextPreferences.sessionDensity === "compact" ? "compact" : defaults.sessionDensity;
  nextPreferences.sendShortcut =
    nextPreferences.sendShortcut === "ctrl-enter" ? "ctrl-enter" : defaults.sendShortcut;
  nextPreferences.showKnowledgeTips = nextPreferences.showKnowledgeTips !== false;
  nextPreferences.sidebarCollapsed = nextPreferences.sidebarCollapsed === true;
  nextPreferences.answerMode = ["auto", "knowledge", "chat"].includes(nextPreferences.answerMode)
    ? nextPreferences.answerMode
    : defaults.answerMode;
  nextPreferences.chatModelId = String(nextPreferences.chatModelId || "").trim();

  return nextPreferences;
}

export function resolveHomeRoute(user) {
  return normalizePreferences(getPreferences(user), user).homeRoute;
}
