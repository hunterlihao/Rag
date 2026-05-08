<script setup>
import { useRouter } from "vue-router";
import { ArrowLeft, FileText } from "lucide-vue-next";

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
          <FileText class="w-5 h-5 text-blue-600" />
        </div>
        <h1 class="text-2xl font-bold text-gray-900">使用条款</h1>
      </div>

      <p class="text-sm text-gray-500 mb-8">最后更新日期：2026年5月</p>

      <div class="prose prose-sm text-gray-700 space-y-6">
        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">1. 服务说明</h2>
          <p>RAG Studio（以下简称"本服务"）是一个基于检索增强生成（RAG）技术的知识库问答系统。用户可上传文档，系统将解析文本、生成向量并存入向量库，在对话中基于知识库内容提供智能问答。</p>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">2. 账户注册</h2>
          <ul class="list-disc pl-5 space-y-1">
            <li>用户需提供真实有效的邮箱地址完成注册</li>
            <li>用户应对其账户下的所有活动负责</li>
            <li>不得将账户转让或授权他人使用</li>
            <li>如发现账户遭未授权使用，应立即通知管理员</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">3. 用户行为规范</h2>
          <p>用户不得利用本服务从事以下行为：</p>
          <ul class="list-disc pl-5 mt-2 space-y-1">
            <li>上传包含恶意代码、病毒或木马的文件</li>
            <li>上传侵犯他人知识产权或隐私权的内容</li>
            <li>上传违反法律法规的内容，包括但不限于色情、暴力、恐怖主义相关内容</li>
            <li>利用本服务进行网络攻击、爬虫或其他破坏性行为</li>
            <li>试图绕过或破坏本服务的安全机制</li>
            <li>批量注册账户或滥用系统资源</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">4. 知识产权</h2>
          <ul class="list-disc pl-5 space-y-1">
            <li>用户上传的文档内容，其知识产权仍归用户或原权利人所有</li>
            <li>本服务的源代码、界面设计、品牌标识等知识产权归服务提供方所有</li>
            <li>用户授予本服务为提供问答功能而对上传文档进行文本提取、向量化和检索的必要权利</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">5. AI 生成内容声明</h2>
          <ul class="list-disc pl-5 space-y-1">
            <li>本服务的回答由 AI 模型基于检索到的文档片段生成，仅供参考</li>
            <li>AI 生成内容可能存在不准确、不完整或过时的情况</li>
            <li>用户应自行判断和核实关键信息的准确性</li>
            <li>本服务不对 AI 生成内容引发的任何决策或后果承担责任</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">6. 服务可用性</h2>
          <ul class="list-disc pl-5 space-y-1">
            <li>我们尽力保证服务的稳定运行，但不对因维护、故障或不可抗力导致的服务中断承担责任</li>
            <li>我们保留随时修改、暂停或终止部分或全部服务的权利，并将提前通知用户</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">7. 责任限制</h2>
          <p>在法律允许的最大范围内，本服务不对以下情况承担责任：</p>
          <ul class="list-disc pl-5 mt-2 space-y-1">
            <li>因使用或无法使用本服务而产生的任何直接或间接损失</li>
            <li>因第三方服务（如 DashScope API、Ollama 等）故障导致的服务中断或数据丢失</li>
            <li>因用户上传内容引发的法律纠纷或第三方索赔</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">8. 违规处理</h2>
          <p>如发现用户违反本使用条款，我们有权：</p>
          <ul class="list-disc pl-5 mt-2 space-y-1">
            <li>发出警告并要求整改</li>
            <li>暂停或终止违规账户的使用权限</li>
            <li>删除违规内容</li>
            <li>保留追究法律责任的权利</li>
          </ul>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">9. 条款变更</h2>
          <p>我们可能会不时更新本使用条款。重大变更将通过系统通知告知。继续使用本服务即表示您同意更新后的条款。如不同意变更，应停止使用本服务并删除账户。</p>
        </section>

        <section>
          <h2 class="text-lg font-semibold text-gray-900 mb-3">10. 适用法律</h2>
          <p>本条款的订立、执行和解释均适用中华人民共和国法律。如因本条款产生争议，双方应友好协商解决；协商不成的，提交有管辖权的人民法院处理。</p>
        </section>
      </div>
    </div>
  </div>
</template>
