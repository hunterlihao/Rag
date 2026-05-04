function readPositiveInt(value, fallback) {
  const parsedValue = Number.parseInt(String(value || "").trim(), 10);
  return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : fallback;
}

export const appConfig = {
  useMockApi: import.meta.env.VITE_USE_MOCK_API === "true",
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL || "/api").trim(),
  modelProvider: import.meta.env.VITE_MODEL_PROVIDER || "DashScope / Ollama",
  chatModel: import.meta.env.VITE_CHAT_MODEL || "qwen-max",
  embeddingModel: import.meta.env.VITE_EMBEDDING_MODEL || "qwen3-embedding:latest",
  uploadConcurrency: readPositiveInt(import.meta.env.VITE_UPLOAD_CONCURRENCY, 3),
};
