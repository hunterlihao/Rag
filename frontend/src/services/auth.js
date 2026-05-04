import { appConfig } from "./config";
import { clearSession, getSession, requestJson, saveSession } from "./http";

let validatedToken = "";
let pendingAuthRequest = null;

function sanitizeUser(user) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    isAdmin: Boolean(user.is_admin ?? user.isAdmin),
    createdAt: user.created_at || user.createdAt,
  };
}

export function getCurrentSession() {
  return getSession();
}

export function getCurrentUser() {
  const session = getCurrentSession();
  if (!session?.token || isTokenExpired(session.token)) {
    resetAuthState();
    return null;
  }
  return session.user || null;
}

export async function logout() {
  try {
    if (getCurrentSession()?.token) {
      await requestJson(appConfig.apiBaseUrl, "/auth/logout", {
        method: "POST",
      });
    }
  } catch (error) {
    return;
  } finally {
    resetAuthState();
  }
}

export function replaceCurrentUser(user, token = "") {
  const session = getCurrentSession();
  const nextToken = token || session?.token || "";
  if (!nextToken) {
    return null;
  }

  const sanitizedUser = sanitizeUser(user);
  saveSession({
    token: nextToken,
    user: sanitizedUser,
  });
  validatedToken = nextToken;
  return sanitizedUser;
}

export async function login(payload) {
  const result = await requestJson(appConfig.apiBaseUrl, "/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
    auth: false,
  });
  if (!result.user || !result.access_token) {
    throw new Error("后端登录接口返回格式不正确。");
  }
  const user = sanitizeUser(result.user);
  saveSession({
    token: result.access_token,
    user,
  });
  validatedToken = result.access_token;
  return user;
}

export async function register(payload) {
  const result = await requestJson(appConfig.apiBaseUrl, "/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
    auth: false,
  });
  if (!result.user || !result.access_token) {
    throw new Error("后端注册接口返回格式不正确。");
  }
  const user = sanitizeUser(result.user);
  saveSession({
    token: result.access_token,
    user,
  });
  validatedToken = result.access_token;
  return user;
}

export async function ensureAuthenticatedUser({ force = false } = {}) {
  const session = getCurrentSession();
  if (!session?.token || isTokenExpired(session.token)) {
    resetAuthState();
    return null;
  }

  if (!force && validatedToken === session.token && session.user) {
    return session.user;
  }

  if (!force && pendingAuthRequest) {
    return pendingAuthRequest;
  }

  pendingAuthRequest = requestJson(appConfig.apiBaseUrl, "/auth/me", {
    method: "GET",
  })
    .then((result) => {
      if (!result.user) {
        throw new Error("后端未返回当前用户信息。");
      }

      const user = sanitizeUser(result.user);
      saveSession({
        token: session.token,
        user,
      });
      validatedToken = session.token;
      return user;
    })
    .catch(() => {
      resetAuthState();
      return null;
    })
    .finally(() => {
      pendingAuthRequest = null;
    });

  return pendingAuthRequest;
}

function resetAuthState() {
  validatedToken = "";
  pendingAuthRequest = null;
  clearSession();
}

function isTokenExpired(token) {
  try {
    const parts = String(token || "").split(".");
    if (parts.length < 2) {
      return true;
    }
    const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
    const payload = JSON.parse(window.atob(padded));
    const exp = Number(payload.exp || 0);
    if (!Number.isFinite(exp) || exp <= 0) {
      return true;
    }
    return Date.now() >= exp * 1000;
  } catch (error) {
    return true;
  }
}
