const SESSION_KEY = "rag.frontend.session";

function readSession() {
  try {
    const sessionValue = sessionStorage.getItem(SESSION_KEY);
    if (sessionValue) {
      return JSON.parse(sessionValue);
    }

    const legacyValue = localStorage.getItem(SESSION_KEY);
    if (legacyValue) {
      sessionStorage.setItem(SESSION_KEY, legacyValue);
      localStorage.removeItem(SESSION_KEY);
      return JSON.parse(legacyValue);
    }

    const rawValue = "";
    return rawValue ? JSON.parse(rawValue) : null;
  } catch (error) {
    return null;
  }
}

export function saveSession(session) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  localStorage.removeItem(SESSION_KEY);
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(SESSION_KEY);
}

export function getSession() {
  return readSession();
}

export async function requestJson(baseUrl, path, options = {}) {
  const session = readSession();
  const headers = new Headers(options.headers || {});
  const isFormData = options.body instanceof FormData;

  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (options.auth !== false && session?.token) {
    headers.set("Authorization", `Bearer ${session.token}`);
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.detail || payload.message || "请求失败";
    if (response.status === 401) {
      clearSession();
    }
    throw new Error(message);
  }
  return payload;
}
