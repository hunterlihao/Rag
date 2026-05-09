export function normalizeShellSession(session) {
  return {
    id: session.id,
    title: session.title || "新对话",
    preview: session.preview || "还没有消息",
    messageCount: session.message_count ?? session.messageCount ?? 0,
    updatedAt: session.updated_at || session.updatedAt || new Date().toISOString(),
    createdAt: session.created_at || session.createdAt || new Date().toISOString(),
    messages: session.messages || [],
    welcomeMessage: session.welcome_message || session.welcomeMessage || "",
  };
}

export function buildSidebarNavItems(user) {
  const items = [
    { name: "workspace", label: "问答主页" },
    { name: "knowledge", label: "知识库" },
  ];

  if (user?.isAdmin) {
    items.push({ name: "admin-users", label: "用户管理" });
  }

  return items;
}

/**
 * 构建路由位置
 * 注意：Session ID 现在存储在 localStorage 中，不再暴露在 URL 中
 * @param {string} name - 路由名称
 * @param {string} sessionId - Session ID（仅用于内部传递，不放入 URL）
 * @returns {object} 路由配置对象
 */
export function buildRouteLocation(name, sessionId = "") {
  // Session ID 通过 localStorage 存储，URL 保持简洁
  // 如果需要在路由间传递 sessionId，调用方应该先存储到 localStorage
  return { name };
}
