import {
  ChatDotRound,
  CollectionTag,
  Setting,
  UserFilled,
} from "@element-plus/icons-vue";

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
    {
      name: "workspace",
      label: "问答主页",
      description: "集中提问、追问与查看历史回答",
      icon: ChatDotRound,
    },
    {
      name: "knowledge",
      label: "知识库",
      description: "独立导入文件并维护当前账号向量库",
      icon: CollectionTag,
    },
  ];

  if (user?.isAdmin) {
    items.push({
      name: "admin-users",
      label: "用户管理",
      description: "管理员可维护系统用户与权限",
      icon: UserFilled,
    });
  }

  items.push({
    name: "settings",
    label: "设置中心",
    description: "修改资料、密码和个性化偏好",
    icon: Setting,
  });

  return items;
}

export function buildRouteLocation(name, sessionId = "") {
  if (name === "workspace" || name === "knowledge") {
    return {
      name,
      query: sessionId ? { session: sessionId } : {},
    };
  }

  return { name };
}
