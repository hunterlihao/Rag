<script setup>
import { reactive, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { ArrowLeft, ArrowRight, User, Lock, AlertCircle, Sparkles, Loader2 } from "lucide-vue-next";
import { login } from "@/services/auth";
import { resolveHomeRoute } from "@/services/user";

const router = useRouter();
const loading = ref(false);
const serverError = ref("");

const form = reactive({
  email: "",
  password: "",
});

const touched = reactive({
  email: false,
  password: false,
});

const errors = computed(() => {
  const e = { email: "", password: "" };
  if (touched.email && !form.email.trim()) e.email = "请输入邮箱";
  else if (touched.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = "邮箱格式不正确";
  if (touched.password && !form.password.trim()) e.password = "请输入密码";
  return e;
});

const hasErrors = computed(() => errors.value.email || errors.value.password);

async function submitLogin() {
  serverError.value = "";
  touched.email = true;
  touched.password = true;
  if (hasErrors.value) return;
  loading.value = true;
  try {
    const user = await login(form);
    router.push({ name: resolveHomeRoute(user) });
  } catch (err) {
    serverError.value = err.message || "登录失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen bg-white flex">
    <div class="hidden lg:flex lg:w-[55%] relative overflow-hidden">
      <div class="absolute inset-0 bg-gradient-to-br from-blue-500 via-blue-600 to-cyan-500" />
      <div class="absolute inset-0 opacity-[0.08]" :style="{ backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)', backgroundSize: '32px 32px' }" />
      <div class="absolute top-1/4 left-1/4 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
      <div class="absolute bottom-1/4 right-1/4 w-48 h-48 bg-cyan-400/20 rounded-full blur-3xl" />
      <div class="relative z-10 flex flex-col justify-between w-full p-12">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center">
            <Sparkles class="w-5 h-5 text-white" />
          </div>
          <span class="text-xl font-semibold text-white">RAG Studio</span>
        </div>
        <div class="space-y-4">
          <h1 class="text-4xl font-bold text-white leading-tight">智能知识库问答</h1>
          <p class="text-white/70 text-lg">从未如此高效</p>
          <p class="text-white/50 text-sm max-w-md">RAG Studio 运用前沿 AI 技术，帮助你从文档中快速获取答案，让知识管理更高效。</p>
        </div>
        <div class="flex items-center gap-6 text-sm text-white/50">
          <span>256 位 SSL 加密</span>
          <span>JWT 安全认证</span>
        </div>
      </div>
    </div>

    <div class="w-full lg:w-[45%] flex flex-col">
      <header class="lg:hidden px-6 py-4 flex items-center justify-between">
        <button @click="router.push('/')" class="flex items-center gap-2 text-gray-500 hover:text-gray-700">
          <ArrowLeft class="w-4 h-4" />
          <span class="text-sm">返回首页</span>
        </button>
      </header>

      <div class="flex-1 flex items-center justify-center px-6 py-12 lg:px-12">
        <div class="w-full max-w-sm">
          <button @click="router.push('/')" class="hidden lg:flex items-center gap-2 text-gray-400 hover:text-gray-600 transition-colors mb-8">
            <ArrowLeft class="w-4 h-4" />
            <span class="text-sm">返回首页</span>
          </button>

          <div class="mb-10">
            <h1 class="text-3xl font-bold text-gray-900 tracking-tight mb-2">欢迎回来</h1>
            <p class="text-gray-500">登录账户，继续您的知识库问答工作</p>
          </div>

          <form @submit.prevent="submitLogin" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">邮箱</label>
              <div class="relative">
                <div class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                  <User class="w-5 h-5" />
                </div>
                <input
                  v-model="form.email"
                  type="email"
                  placeholder="请输入邮箱"
                  :class="['w-full h-12 pl-12 pr-4 rounded-xl text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:bg-white transition-all border', touched.email && errors.email ? 'bg-red-50 border-red-300 focus:ring-red-500' : 'bg-gray-50 border-gray-200 focus:ring-blue-500']"
                  @blur="touched.email = true"
                  @keyup.enter="submitLogin"
                />
              </div>
              <p v-if="touched.email && errors.email" class="flex items-center gap-1.5 mt-1.5 text-xs text-red-600">
                <AlertCircle class="w-3.5 h-3.5 flex-shrink-0" /> {{ errors.email }}
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">密码</label>
              <div class="relative">
                <div class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                  <Lock class="w-5 h-5" />
                </div>
                <input
                  v-model="form.password"
                  type="password"
                  placeholder="请输入密码"
                  :class="['w-full h-12 pl-12 pr-4 rounded-xl text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:bg-white transition-all border', touched.password && errors.password ? 'bg-red-50 border-red-300 focus:ring-red-500' : 'bg-gray-50 border-gray-200 focus:ring-blue-500']"
                  @blur="touched.password = true"
                  @keyup.enter="submitLogin"
                />
              </div>
              <p v-if="touched.password && errors.password" class="flex items-center gap-1.5 mt-1.5 text-xs text-red-600">
                <AlertCircle class="w-3.5 h-3.5 flex-shrink-0" /> {{ errors.password }}
              </p>
            </div>

            <div v-if="serverError" class="flex items-center gap-2 bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm">
              <AlertCircle class="w-4 h-4 flex-shrink-0" />
              <span>{{ serverError }}</span>
            </div>

            <button
              type="submit"
              :disabled="loading"
              class="w-full h-12 bg-gradient-to-r from-blue-500 to-blue-600 text-white text-sm font-medium rounded-xl hover:from-blue-600 hover:to-blue-700 transition-all flex items-center justify-center gap-2 disabled:opacity-70"
            >
              <template v-if="loading">
                <Loader2 class="w-4 h-4 animate-spin" /> 登录中...
              </template>
              <template v-else>
                登录 <ArrowRight class="w-4 h-4" />
              </template>
            </button>
          </form>

          <div class="flex items-center my-6">
            <div class="flex-1 border-t border-gray-200"></div>
            <span class="px-4 text-xs text-gray-400">或</span>
            <div class="flex-1 border-t border-gray-200"></div>
          </div>

          <button @click="router.push('/register')" class="w-full h-12 bg-white text-gray-700 text-sm font-medium rounded-xl border border-gray-200 hover:bg-gray-50 transition-all">
            注册新账户
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
