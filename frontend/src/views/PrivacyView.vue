<script setup>
import { useRouter } from "vue-router";
import { ArrowLeft, Shield } from "lucide-vue-next";

const router = useRouter();
</script>

<template>
  <div class="min-h-screen bg-white flex flex-col">
    <header class="px-6 py-4 flex items-center gap-3 border-b border-gray-100">
      <button @click="router.back()" class="flex items-center gap-2 text-gray-500 hover:text-gray-700">
        <ArrowLeft class="w-4 h-4" />
        <span class="text-sm">返回</span>
      </button>
    </header>

    <div class="flex-1 max-w-2xl mx-auto px-6 py-12 w-full">
      <div class="flex items-center gap-3 mb-8">
        <div class="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
          <Shield class="w-5 h-5 text-blue-600" />
        </div>
        <h1 class="text-2xl font-bold text-gray-900">隐私声明</h1>
      </div>

      <p class="text-sm text-gray-500 mb-8">最后更新日期：2026年5月</p>

      <div class="prose prose-sm text-gray-700 space-y-6">
        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">1. 信息收集</h2>
          <p>我们仅收集提供服务所必需的信息，包括：</p>
          <ul class="list-disc pl-5 mt-2 space-y-1">
            <li>账户信息：用户名、邮箱地址、密码（加密存储）</li>
            <li>使用数据：您上传的文档内容、对话记录</li>
            <li>技术信息：IP 地址、浏览器类型、访问日志</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">2. 信息使用</h2>
          <p>我们使用收集的信息用于：</p>
          <ul class="list-disc pl-5 mt-2 space-y-1">
            <li>提供、维护和改进 RAG 知识库问答服务</li>
            <li>处理您的文档上传和向量化请求</li>
            <li>保障账户安全和防止未授权访问</li>
            <li>遵守法律法规要求</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">3. 数据存储与安全</h2>
          <ul class="list-disc pl-5 space-y-1">
            <li>密码使用 bcrypt 加密存储，不可逆</li>
            <li>文档内容经向量化后存储于 Chroma 向量库，与用户账户隔离</li>
            <li>对话历史存储于 PostgreSQL 数据库</li>
            <li>JWT 令牌用于身份验证，支持随时吊销</li>
            <li>传输层使用 HTTPS 加密（生产环境）</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">4. 数据共享</h2>
          <p>我们不会将您的个人数据出售或分享给第三方，除非：</p>
          <ul class="list-disc pl-5 mt-2 space-y-1">
            <li>获得您的明确授权</li>
            <li>法律法规或监管机构要求</li>
            <li>保护我们的合法权益</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">5. 用户权利</h2>
          <p>您有权：</p>
          <ul class="list-disc pl-5 mt-2 space-y-1">
            <li>访问、更正或删除您的账户信息</li>
            <li>导出您的对话记录和上传文档</li>
            <li>随时删除您的账户及相关数据</li>
            <li>撤回同意（不影响撤回前已进行的处理）</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">6. Cookie 与跟踪</h2>
          <p>本服务使用 sessionStorage 存储登录令牌，不使用第三方 Cookie 或跟踪技术。会话令牌仅在浏览器标签页打开期间有效。</p>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">7. 第三方服务</h2>
          <p>当您使用 DashScope / 通义千问作为聊天模型时，您的提问和检索到的文档片段将被发送至阿里云 DashScope API 进行处理。请参阅对应服务的隐私政策了解详情。</p>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">8. 隐私声明更新</h2>
          <p>我们可能会不时更新本隐私声明。重大变更将通过系统通知或邮件告知。继续使用本服务即表示您同意更新后的条款。</p>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">9. 联系我们</h2>
          <p>如对本隐私声明有任何疑问，请联系系统管理员。</p>
        </section>
      </div>
    </div>
  </div>
</template>
