<script setup>
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ArrowLeft, ArrowRight, User, Mail, Lock, Check, AlertCircle, Sparkles, Loader2 } from "lucide-vue-next";
import { register } from "@/services/auth";
import { resolveHomeRoute } from "@/services/user";

const router = useRouter();
const step = ref(1);
const error = ref("");
const loading = ref(false);
const agreed = ref(false);
const shake = ref(false);

const form = reactive({
  name: "",
  email: "",
  password: "",
  confirmPassword: "",
});

const inputRef = ref(null);

onMounted(() => {
  setTimeout(() => inputRef.value?.focus(), 100);
});

async function handleNext() {
  error.value = "";

  if (step.value === 1) {
    if (!form.name.trim()) { error.value = "请输入用户名"; return; }
    if (!agreed.value) { shake.value = true; setTimeout(() => (shake.value = false), 300); return; }
    step.value = 2; setTimeout(() => inputRef.value?.focus(), 100); return;
  }

  if (step.value === 2) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) { error.value = "请输入有效的邮箱地址"; return; }
    step.value = 3; setTimeout(() => inputRef.value?.focus(), 100); return;
  }

  if (step.value === 3) {
    if (form.password.length < 6) { error.value = "密码长度至少为6位"; return; }
    step.value = 4; setTimeout(() => inputRef.value?.focus(), 100); return;
  }

  if (step.value === 4) {
    if (form.password !== form.confirmPassword) { error.value = "两次输入的密码不一致"; return; }
    loading.value = true;
    try {
      const user = await register({ name: form.name, email: form.email, password: form.password });
      router.push({ name: resolveHomeRoute(user) });
    } catch (err) {
      error.value = err.message || "注册失败";
    } finally {
      loading.value = false;
    }
  }
}
</script>

<template>
  <div class="min-h-screen bg-white flex">
    <!-- Left: Brand -->
    <div class="hidden lg:flex lg:w-[55%] relative overflow-hidden">
      <div class="absolute inset-0 bg-gradient-to-br from-blue-500 via-blue-600 to-cyan-500" />
      <div class="absolute inset-0 opacity-[0.08]" :style="{ backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)', backgroundSize: '32px 32px' }" />
      <div class="absolute top-1/4 left-1/4 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
      <div class="relative z-10 flex flex-col justify-between w-full p-12">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center">
            <Sparkles class="w-5 h-5 text-white" />
          </div>
          <span class="text-xl font-semibold text-white">RAG Studio</span>
        </div>
        <div class="space-y-4">
          <h1 class="text-4xl font-bold text-white">智能知识库问答</h1>
          <p class="text-white/70 text-lg">从未如此高效</p>
        </div>
        <div class="flex items-center gap-6 text-sm text-white/50">
          <span>256 位 SSL 加密</span>
          <span>JWT 安全认证</span>
        </div>
      </div>
    </div>

    <!-- Right: Form -->
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
            <h1 class="text-3xl font-bold text-gray-900 tracking-tight mb-2">欢迎加入</h1>
            <p class="text-gray-500">创建账户，开启智能知识库问答之旅</p>
          </div>

          <!-- Progress -->
          <div v-if="step > 1" class="flex items-center gap-2 mb-8">
            <div v-for="i in 4" :key="i" class="h-1 rounded-full transition-all duration-300" :class="i <= step ? 'bg-blue-500 flex-1' : 'bg-gray-100 flex-1'" />
          </div>

          <form @submit.prevent="handleNext" class="space-y-5">
            <!-- Step 1: Name + Agreement -->
            <div v-if="step === 1">
              <label class="block text-sm font-medium text-gray-700 mb-2">用户名</label>
              <div class="relative">
                <div class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                  <User class="w-5 h-5" />
                </div>
                <input
                  ref="inputRef"
                  v-model="form.name"
                  type="text"
                  placeholder="请输入用户名"
                  class="w-full h-12 pl-12 pr-4 bg-gray-50 rounded-xl text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all border border-gray-200"
                />
              </div>

              <div
                @click="agreed = !agreed"
                class="flex items-start gap-3 p-4 mt-5 rounded-xl border-2 cursor-pointer transition-all"
                :class="agreed ? 'bg-blue-50 border-blue-500' : 'bg-white border-gray-200 hover:border-gray-300'"
              >
                <div class="w-5 h-5 rounded flex items-center justify-center border-2 transition-all flex-shrink-0" :class="[shake ? 'animate-shake' : '', agreed ? 'bg-blue-500 border-blue-500' : 'border-gray-300']">
                  <Check v-if="agreed" class="w-3.5 h-3.5 text-white" />
                </div>
                <span class="text-sm text-gray-600 select-none">
                  我阅读并同意 <span class="text-blue-600 font-medium">隐私声明</span> 和 <span class="text-blue-600 font-medium">使用条款</span>
                </span>
              </div>
            </div>

            <!-- Step 2: Email -->
            <div v-if="step === 2">
              <label class="block text-sm font-medium text-gray-700 mb-2">邮箱</label>
              <div class="relative">
                <div class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                  <Mail class="w-5 h-5" />
                </div>
                <input
                  ref="inputRef"
                  v-model="form.email"
                  type="email"
                  placeholder="请输入邮箱地址"
                  class="w-full h-12 pl-12 pr-4 bg-gray-50 rounded-xl text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all border border-gray-200"
                />
              </div>
            </div>

            <!-- Step 3: Password -->
            <div v-if="step === 3">
              <label class="block text-sm font-medium text-gray-700 mb-2">密码</label>
              <div class="relative">
                <div class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                  <Lock class="w-5 h-5" />
                </div>
                <input
                  ref="inputRef"
                  v-model="form.password"
                  type="password"
                  placeholder="请设置密码（至少6位）"
                  class="w-full h-12 pl-12 pr-4 bg-gray-50 rounded-xl text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all border border-gray-200"
                />
              </div>
            </div>

            <!-- Step 4: Confirm -->
            <div v-if="step === 4">
              <label class="block text-sm font-medium text-gray-700 mb-2">确认密码</label>
              <div class="relative">
                <div class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                  <Lock class="w-5 h-5" />
                </div>
                <input
                  ref="inputRef"
                  v-model="form.confirmPassword"
                  type="password"
                  placeholder="请再次输入密码"
                  class="w-full h-12 pl-12 pr-4 bg-gray-50 rounded-xl text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all border border-gray-200"
                />
              </div>
            </div>

            <div v-if="error" class="flex items-center gap-2 bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm">
              <AlertCircle class="w-4 h-4 flex-shrink-0" />
              <span>{{ error }}</span>
            </div>

            <button
              type="submit"
              :disabled="loading"
              class="w-full h-12 bg-gradient-to-r from-blue-500 to-blue-600 text-white text-sm font-medium rounded-xl hover:from-blue-600 hover:to-blue-700 transition-all flex items-center justify-center gap-2 disabled:opacity-70"
            >
              <template v-if="loading">
                <Loader2 class="w-4 h-4 animate-spin" />
                {{ step === 4 ? '创建账户...' : '处理中...' }}
              </template>
              <template v-else>
                {{ step === 1 ? '继续' : step === 4 ? '完成注册' : '下一步' }}
                <ArrowRight v-if="step < 4" class="w-4 h-4" />
              </template>
            </button>
          </form>

          <!-- Back button -->
          <div v-if="step > 1" class="mt-6 text-center">
            <button type="button" @click="step--" class="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 transition-colors">
              <ArrowLeft class="w-4 h-4" />
              返回上一步
            </button>
          </div>

          <!-- Login link -->
          <p class="mt-6 text-center text-sm text-gray-500">
            已有账户？
            <router-link to="/login" class="text-blue-600 font-medium hover:underline">登录</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
