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

  items.push({ name: "settings", label: "设置中心" });

  return items;
}

export function buildRouteLocation(name, sessionId = "") {
  if (name === "workspace" || name === "knowledge") {
    return { name, query: sessionId ? { session: sessionId } : {} };
  }
  return { name };
}
