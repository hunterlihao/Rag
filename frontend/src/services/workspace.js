import { appConfig } from "./config";
import { clearSession, getSession, requestJson } from "./http";

export const suggestedPrompts = [
  "帮我概括一下当前知识库里最重要的主题",
  "从知识库里找出和数据库报错相关的内容",
  "总结一下上传文件里的关键知识点",
  "根据知识库给我一个排查思路",
];

export function formatRelativeTime(isoTime) {
  const diff = Date.now() - new Date(isoTime).getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diff < minute) {
    return "刚刚";
  }
  if (diff < hour) {
    return `${Math.floor(diff / minute)} 分钟前`;
  }
  if (diff < day) {
    return `${Math.floor(diff / hour)} 小时前`;
  }
  return `${Math.floor(diff / day)} 天前`;
}

export function buildWelcomeMessage(session) {
  return session?.welcome_message || "你好，我已经准备好结合知识库回答问题了。";
}

export async function fetchBackendMeta() {
  return requestJson(appConfig.apiBaseUrl, "/meta", {
    auth: false,
  });
}

export async function fetchSessions() {
  const result = await requestJson(appConfig.apiBaseUrl, "/sessions");
  return result.sessions || [];
}

export async function createSession() {
  const result = await requestJson(appConfig.apiBaseUrl, "/sessions", {
    method: "POST",
  });
  return result.session;
}

export async function fetchSessionDetail(sessionId) {
  const result = await requestJson(appConfig.apiBaseUrl, `/sessions/${sessionId}`);
  return result.session;
}

export async function deleteSession(sessionId) {
  return requestJson(appConfig.apiBaseUrl, `/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function sendPrompt(sessionId, prompt, answerMode = "auto", chatModelId = "") {
  const result = await requestJson(appConfig.apiBaseUrl, `/sessions/${sessionId}/ask`, {
    method: "POST",
    body: JSON.stringify({
      prompt,
      answer_mode: answerMode,
      chat_model_id: chatModelId,
    }),
  });
  return result.session;
}

function parseStreamLine(line) {
  try {
    return JSON.parse(line);
  } catch (error) {
    return null;
  }
}

async function readStreamError(response) {
  const payload = await response.json().catch(() => ({}));
  return payload.detail || payload.message || "回答失败了，请稍后重试。";
}

export async function sendPromptStream(
  sessionId,
  prompt,
  {
    answerMode = "auto",
    chatModelId = "",
    answerRequestId = "",
    signal,
    onDelta,
    onSession,
    onError,
    onStopped,
    onSources,
  } = {},
) {
  const session = getSession();
  const headers = new Headers({
    "Content-Type": "application/json",
  });

  if (session?.token) {
    headers.set("Authorization", `Bearer ${session.token}`);
  }

  const response = await fetch(`${appConfig.apiBaseUrl}/sessions/${sessionId}/ask/stream`, {
    method: "POST",
    headers,
    signal,
    body: JSON.stringify({
      prompt,
      answer_mode: answerMode,
      chat_model_id: chatModelId,
      answer_request_id: answerRequestId,
    }),
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearSession();
    }
    throw new Error(await readStreamError(response));
  }

  if (!response.body) {
    throw new Error("当前浏览器不支持流式回答。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let finalSession = null;

  function handleEvent(event) {
    if (!event?.type) {
      return;
    }

    if (event.type === "delta") {
      const content = String(event.content || "");
      if (content && typeof onDelta === "function") {
        onDelta(content);
      }
      return;
    }

    if (event.type === "sources") {
      if (event.sources && typeof onSources === "function") {
        onSources(event.sources);
      }
      return;
    }

    if (event.type === "session") {
      finalSession = event.session || null;
      if (finalSession && typeof onSession === "function") {
        onSession(finalSession);
      }
      if (event.stopped && typeof onStopped === "function") {
        onStopped(finalSession);
      }
      return;
    }

    if (event.type === "error") {
      const message = String(event.message || "回答失败了，请稍后重试。");
      if (typeof onError === "function") {
        onError(message);
      }
      throw new Error(message);
    }
  }

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const trimmedLine = line.trim();
      if (trimmedLine) {
        handleEvent(parseStreamLine(trimmedLine));
      }
    }

    if (done) {
      break;
    }
  }

  const remainingLine = buffer.trim();
  if (remainingLine) {
    handleEvent(parseStreamLine(remainingLine));
  }

  if (!finalSession) {
    throw new Error("回答完成但没有收到会话状态，请刷新后重试。");
  }
  return finalSession;
}

export async function stopPromptStream(sessionId, answerRequestId = "") {
  return requestJson(appConfig.apiBaseUrl, `/sessions/${sessionId}/ask/stop`, {
    method: "POST",
    body: JSON.stringify({
      answer_request_id: answerRequestId,
    }),
  });
}

export async function fetchUploads() {
  const result = await requestJson(appConfig.apiBaseUrl, "/uploads");
  return result.uploads || [];
}

export async function uploadFiles(fileList) {
  const formData = new FormData();
  fileList.forEach((file) => {
    const rawFile = file.raw || file;
    formData.append("files", rawFile, rawFile.name);
  });

  return requestJson(appConfig.apiBaseUrl, "/uploads", {
    method: "POST",
    body: formData,
  });
}

export function uploadFileWithProgress(file, { onProgress } = {}) {
  const session = getSession();
  const rawFile = file.raw || file;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${appConfig.apiBaseUrl}/uploads`);

    if (session?.token) {
      xhr.setRequestHeader("Authorization", `Bearer ${session.token}`);
    }

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || typeof onProgress !== "function") {
        return;
      }
      onProgress(event.loaded / event.total);
    };

    xhr.onload = () => {
      let payload = {};
      try {
        payload = JSON.parse(xhr.responseText || "{}");
      } catch (error) {
        payload = {};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload);
        return;
      }

      if (xhr.status === 401) {
        clearSession();
      }
      reject(new Error(payload.detail || payload.message || "上传失败"));
    };

    xhr.onerror = () => {
      reject(new Error("上传请求失败，请检查后端服务是否可用。"));
    };

    const formData = new FormData();
    formData.append("files", rawFile, rawFile.name);
    xhr.send(formData);
  });
}

export async function deleteUpload(uploadId) {
  return requestJson(appConfig.apiBaseUrl, `/uploads/${uploadId}`, {
    method: "DELETE",
  });
}

export async function deleteUploads(uploadIds) {
  return requestJson(appConfig.apiBaseUrl, "/uploads/batch-delete", {
    method: "POST",
    body: JSON.stringify({ upload_ids: uploadIds }),
  });
}

// WebSocket 连接管理
let uploadWebSocket = null;
const uploadWsListeners = [];

export function connectUploadWebSocket(onMessage) {
  const session = getSession();
  if (!session?.token) return null;

  // 如果已有连接，先关闭
  if (uploadWebSocket) {
    uploadWebSocket.close();
  }

  const apiBase = import.meta.env.VITE_PROXY_TARGET || "http://127.0.0.1:8520";
  const wsUrl = `${apiBase.replace(/^http/, "ws")}/ws/uploads?token=${encodeURIComponent(session.token)}`;

  uploadWebSocket = new WebSocket(wsUrl);

  uploadWebSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (typeof onMessage === "function") {
        onMessage(data);
      }
      // 通知所有注册的监听器
      uploadWsListeners.forEach((listener) => listener(data));
    } catch (error) {
      console.error("WebSocket message parse error:", error);
    }
  };

  uploadWebSocket.onclose = () => {
    console.log("Upload WebSocket closed");
    uploadWebSocket = null;
  };

  uploadWebSocket.onerror = (error) => {
    console.error("Upload WebSocket error:", error);
  };

  return uploadWebSocket;
}

export function addUploadWsListener(listener) {
  if (!uploadWsListeners.includes(listener)) {
    uploadWsListeners.push(listener);
  }
}

export function removeUploadWsListener(listener) {
  const index = uploadWsListeners.indexOf(listener);
  if (index > -1) {
    uploadWsListeners.splice(index, 1);
  }
}

export function disconnectUploadWebSocket() {
  if (uploadWebSocket) {
    uploadWebSocket.close();
    uploadWebSocket = null;
  }
}
