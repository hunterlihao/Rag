<script setup>
import { reactive, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { ArrowRight, User, Lock, AlertCircle, Sparkles, Loader2, CheckCircle, Eye, EyeOff } from "lucide-vue-next";
import { login } from "@/services/auth";
import { resolveHomeRoute } from "@/services/user";

const router = useRouter();
const loading = ref(false);
const serverError = ref("");
const showPassword = ref(false);
const rememberMe = ref(false);

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
  <div class="min-h-screen bg-zinc-50 flex">
    <!-- Left: Brand Panel -->
    <div class="hidden lg:flex lg:w-[52%] relative overflow-hidden bg-zinc-900">
      <!-- Ambient glow -->
      <div class="absolute -top-40 -right-40 w-[600px] h-[600px] bg-blue-500/20 rounded-full blur-[120px]" />
      <div class="absolute -bottom-40 -left-40 w-[500px] h-[500px] bg-violet-500/15 rounded-full blur-[120px]" />

      <!-- Grid texture -->
      <div class="absolute inset-0 opacity-[0.03]" :style="{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)', backgroundSize: '60px 60px' }" />

      <div class="relative z-10 flex flex-col justify-between w-full p-14">
        <!-- Logo -->
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25">
            <Sparkles class="w-5 h-5 text-white" />
          </div>
          <span class="text-xl font-semibold text-white tracking-tight">RAG Studio</span>
        </div>

        <!-- Hero -->
        <div class="space-y-8 -mt-8">
          <div class="space-y-3">
            <h1 class="text-[2.6rem] font-bold text-white leading-[1.15] tracking-tight">
              让知识<br />触手可及
            </h1>
            <p class="text-zinc-400 text-base leading-relaxed max-w-sm">
              上传文档，即时获得 AI 驱动的精准回答。将您的知识库转化为智能对话体验。
            </p>
          </div>

          <!-- Feature pills -->
          <div class="space-y-3">
            <div class="flex items-center gap-3 text-zinc-300">
              <CheckCircle class="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span class="text-sm">上传 PDF、Word、Excel 等任意文档</span>
            </div>
            <div class="flex items-center gap-3 text-zinc-300">
              <CheckCircle class="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span class="text-sm">AI 精准检索，秒级获取答案</span>
            </div>
            <div class="flex items-center gap-3 text-zinc-300">
              <CheckCircle class="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span class="text-sm">多用户协作，独立知识库隔离</span>
            </div>
          </div>
        </div>

        <!-- Testimonial -->
        <div class="border-t border-white/[0.06] pt-8">
          <blockquote class="text-zinc-400 text-sm leading-relaxed italic">
            "RAG Studio 让我们的团队知识管理效率提升了 3 倍。不再需要翻遍文件夹找答案，直接提问即可获得精准回复。"
          </blockquote>
          <div class="flex items-center gap-3 mt-4">
            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-zinc-600 to-zinc-500 flex items-center justify-center text-xs font-medium text-white">L</div>
            <div>
              <p class="text-white text-sm font-medium">Li Yuanhao</p>
              <p class="text-zinc-500 text-xs">技术团队负责人</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: Form Panel -->
    <div class="w-full lg:w-[48%] flex flex-col bg-white lg:bg-zinc-50">
      <div class="flex-1 flex items-center justify-center px-6 py-12 lg:px-16">
        <div class="w-full max-w-[380px]">
          <!-- Header -->
          <div class="mb-10">
            <div class="lg:hidden flex items-center gap-2 mb-8">
              <div class="w-8 h-8 bg-gradient-to-br from-blue-400 to-blue-600 rounded-lg flex items-center justify-center">
                <Sparkles class="w-4 h-4 text-white" />
              </div>
              <span class="text-lg font-semibold text-zinc-900">RAG Studio</span>
            </div>
            <h2 class="text-[1.75rem] font-bold text-zinc-900 tracking-tight mb-2">欢迎回来</h2>
            <p class="text-zinc-500 text-sm">输入您的邮箱和密码以继续</p>
          </div>

          <!-- Form -->
          <form @submit.prevent="submitLogin" class="space-y-5">
            <!-- Email -->
            <div>
              <label class="block text-sm font-medium text-zinc-700 mb-1.5">邮箱地址</label>
              <div class="relative">
                <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none">
                  <User class="w-[18px] h-[18px]" />
                </div>
                <input
                  v-model="form.email"
                  type="text"
                  placeholder="name@example.com"
                  :class="['w-full h-[46px] pl-10 pr-4 rounded-lg text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-offset-1 transition-all border bg-white', touched.email && errors.email ? 'border-red-300 focus:ring-red-500 focus:ring-offset-red-50' : 'border-zinc-200 focus:ring-zinc-900 focus:border-zinc-900']"
                  @blur="touched.email = true"
                  @keyup.enter="submitLogin"
                />
              </div>
              <p v-if="touched.email && errors.email" class="flex items-center gap-1.5 mt-1.5 text-xs text-red-600">
                <AlertCircle class="w-3 h-3 flex-shrink-0" /> {{ errors.email }}
              </p>
            </div>

            <!-- Password -->
            <div>
              <div class="flex items-center justify-between mb-1.5">
                <label class="text-sm font-medium text-zinc-700">密码</label>
                <router-link to="/forgot-password" class="text-xs text-zinc-500 hover:text-zinc-900 transition-colors">忘记密码？</router-link>
              </div>
              <div class="relative">
                <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none">
                  <Lock class="w-[18px] h-[18px]" />
                </div>
                <input
                  v-model="form.password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="输入您的密码"
                  :class="['w-full h-[46px] pl-10 pr-10 rounded-lg text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-offset-1 transition-all border bg-white', touched.password && errors.password ? 'border-red-300 focus:ring-red-500 focus:ring-offset-red-50' : 'border-zinc-200 focus:ring-zinc-900 focus:border-zinc-900']"
                  @blur="touched.password = true"
                  @keyup.enter="submitLogin"
                />
                <button
                  type="button"
                  @click="showPassword = !showPassword"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 transition-colors"
                >
                  <EyeOff v-if="showPassword" class="w-[18px] h-[18px]" />
                  <Eye v-else class="w-[18px] h-[18px]" />
                </button>
              </div>
              <p v-if="touched.password && errors.password" class="flex items-center gap-1.5 mt-1.5 text-xs text-red-600">
                <AlertCircle class="w-3 h-3 flex-shrink-0" /> {{ errors.password }}
              </p>
            </div>

            <!-- Remember me -->
            <div class="flex items-center gap-2">
              <button
                type="button"
                @click="rememberMe = !rememberMe"
                class="w-4 h-4 rounded border transition-colors flex items-center justify-center flex-shrink-0"
                :class="rememberMe ? 'bg-zinc-900 border-zinc-900' : 'border-zinc-300 hover:border-zinc-400'"
              >
                <CheckCircle v-if="rememberMe" class="w-3 h-3 text-white" />
              </button>
              <label @click="rememberMe = !rememberMe" class="text-sm text-zinc-600 cursor-pointer select-none">记住我</label>
            </div>

            <!-- Server error -->
            <div v-if="serverError" class="flex items-center gap-2 bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm border border-red-100">
              <AlertCircle class="w-4 h-4 flex-shrink-0" />
              <span>{{ serverError }}</span>
            </div>

            <!-- Submit -->
            <button
              type="submit"
              :disabled="loading"
              class="w-full h-[46px] bg-zinc-900 text-white text-sm font-medium rounded-lg hover:bg-zinc-800 transition-colors flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed active:scale-[0.99]"
            >
              <template v-if="loading">
                <Loader2 class="w-4 h-4 animate-spin" /> 登录中...
              </template>
              <template v-else>
                登录 <ArrowRight class="w-4 h-4" />
              </template>
            </button>
          </form>

          <!-- Divider -->
          <div class="flex items-center my-6">
            <div class="flex-1 border-t border-zinc-200"></div>
            <span class="px-4 text-xs text-zinc-400 font-medium">或</span>
            <div class="flex-1 border-t border-zinc-200"></div>
          </div>

          <!-- Social login mock buttons -->
          <div class="space-y-3">
            <button
              type="button"
              disabled
              class="w-full h-[46px] bg-white text-zinc-700 text-sm font-medium rounded-lg border border-zinc-200 flex items-center justify-center gap-3 opacity-50 cursor-not-allowed"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              使用 Google 登录
            </button>
            <button
              type="button"
              disabled
              class="w-full h-[46px] bg-white text-zinc-700 text-sm font-medium rounded-lg border border-zinc-200 flex items-center justify-center gap-3 opacity-50 cursor-not-allowed"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
              使用 GitHub 登录
            </button>
          </div>

          <!-- Footer -->
          <p class="mt-8 text-center text-sm text-zinc-500">
            还没有账户？
            <router-link to="/register" class="text-zinc-900 font-medium hover:underline underline-offset-4">创建账户</router-link>
          </p>

          <p class="mt-4 text-center text-xs text-zinc-400">
            登录即表示您同意我们的
            <router-link to="/terms" class="text-zinc-600 hover:text-zinc-900 underline underline-offset-2">使用条款</router-link>
            和
            <router-link to="/privacy" class="text-zinc-600 hover:text-zinc-900 underline underline-offset-2">隐私政策</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
