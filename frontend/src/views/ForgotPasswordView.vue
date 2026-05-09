<script setup>
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import { ArrowLeft, ArrowRight, User, Mail, Lock, AlertCircle, CheckCircle, Sparkles, Loader2, Eye, EyeOff } from "lucide-vue-next";
import { forgotPassword } from "@/services/auth";

const router = useRouter();
const loading = ref(false);
const error = ref("");
const success = ref("");

const form = reactive({
  name: "",
  email: "",
  new_password: "",
  confirm_password: "",
});

const showPassword = ref(false);
const showConfirmPassword = ref(false);

async function submitReset() {
  error.value = "";
  success.value = "";

  if (!form.name.trim()) { error.value = "请输入用户名"; return; }
  if (!form.email.trim()) { error.value = "请输入邮箱地址"; return; }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) { error.value = "请输入有效的邮箱地址"; return; }
  if (!form.new_password) { error.value = "请输入新密码"; return; }
  if (form.new_password.length < 6) { error.value = "新密码至少需要 6 位"; return; }
  if (form.new_password !== form.confirm_password) { error.value = "两次输入的密码不一致"; return; }

  loading.value = true;
  try {
    const result = await forgotPassword({
      name: form.name,
      email: form.email,
      new_password: form.new_password,
    });
    success.value = result.message || "密码重置成功";
  } catch (err) {
    error.value = err.message || "重置失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen bg-zinc-50 flex">
    <!-- Left: Brand Panel -->
    <div class="hidden lg:flex lg:w-[52%] relative overflow-hidden bg-zinc-900">
      <div class="absolute -top-40 -right-40 w-[600px] h-[600px] bg-blue-500/20 rounded-full blur-[120px]" />
      <div class="absolute -bottom-40 -left-40 w-[500px] h-[500px] bg-violet-500/15 rounded-full blur-[120px]" />
      <div class="absolute inset-0 opacity-[0.03]" :style="{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)', backgroundSize: '60px 60px' }" />

      <div class="relative z-10 flex flex-col justify-between w-full p-14">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25">
            <Sparkles class="w-5 h-5 text-white" />
          </div>
          <span class="text-xl font-semibold text-white tracking-tight">RAG Studio</span>
        </div>

        <div class="space-y-8 -mt-8">
          <div class="space-y-3">
            <h1 class="text-[2.6rem] font-bold text-white leading-[1.15] tracking-tight">
              忘记密码？<br />不用担心
            </h1>
            <p class="text-zinc-400 text-base leading-relaxed max-w-sm">
              验证您的身份信息后即可重新设置密码。请确保输入与注册时一致的用户名和邮箱。
            </p>
          </div>
          <div class="space-y-3">
            <div class="flex items-center gap-3 text-zinc-300">
              <CheckCircle class="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span class="text-sm">验证用户名与邮箱</span>
            </div>
            <div class="flex items-center gap-3 text-zinc-300">
              <CheckCircle class="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span class="text-sm">设置新密码</span>
            </div>
            <div class="flex items-center gap-3 text-zinc-300">
              <CheckCircle class="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span class="text-sm">使用新密码重新登录</span>
            </div>
          </div>
        </div>

        <div class="border-t border-white/[0.06] pt-8">
          <p class="text-zinc-500 text-xs">如有困难，请联系系统管理员获取帮助。</p>
        </div>
      </div>
    </div>

    <!-- Right: Form Panel -->
    <div class="w-full lg:w-[48%] flex flex-col bg-white lg:bg-zinc-50">
      <div class="flex-1 flex items-center justify-center px-6 py-12 lg:px-16">
        <div class="w-full max-w-[380px]">
          <div class="mb-10">
            <div class="lg:hidden flex items-center gap-2 mb-8">
              <div class="w-8 h-8 bg-gradient-to-br from-blue-400 to-blue-600 rounded-lg flex items-center justify-center">
                <Sparkles class="w-4 h-4 text-white" />
              </div>
              <span class="text-lg font-semibold text-zinc-900">RAG Studio</span>
            </div>
            <h2 class="text-[1.75rem] font-bold text-zinc-900 tracking-tight mb-2">重置密码</h2>
            <p class="text-zinc-500 text-sm">验证身份并设置新的登录密码</p>
          </div>

          <!-- Success state -->
          <div v-if="success" class="space-y-6">
            <div class="flex items-center gap-2 bg-emerald-50 text-emerald-700 px-4 py-3 rounded-lg text-sm border border-emerald-100">
              <CheckCircle class="w-4 h-4 flex-shrink-0" />
              <span>{{ success }}</span>
            </div>
            <button @click="router.push('/login')" class="w-full h-[46px] bg-zinc-900 text-white text-sm font-medium rounded-lg hover:bg-zinc-800 transition-colors flex items-center justify-center gap-2 active:scale-[0.99]">
              返回登录 <ArrowRight class="w-4 h-4" />
            </button>
          </div>

          <!-- Form -->
          <form v-else @submit.prevent="submitReset" class="space-y-5">
            <div>
              <label class="block text-sm font-medium text-zinc-700 mb-1.5">用户名</label>
              <div class="relative">
                <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none">
                  <User class="w-[18px] h-[18px]" />
                </div>
                <input
                  v-model="form.name"
                  type="text"
                  placeholder="输入您的用户名"
                  class="w-full h-[46px] pl-10 pr-4 rounded-lg text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-zinc-900 focus:border-zinc-900 transition-all border bg-white border-zinc-200"
                />
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-zinc-700 mb-1.5">邮箱地址</label>
              <div class="relative">
                <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none">
                  <Mail class="w-[18px] h-[18px]" />
                </div>
                <input
                  v-model="form.email"
                  type="text"
                  placeholder="name@example.com"
                  class="w-full h-[46px] pl-10 pr-4 rounded-lg text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-zinc-900 focus:border-zinc-900 transition-all border bg-white border-zinc-200"
                />
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-zinc-700 mb-1.5">新密码</label>
              <div class="relative">
                <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none">
                  <Lock class="w-[18px] h-[18px]" />
                </div>
                <input
                  v-model="form.new_password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="至少 6 位字符"
                  class="w-full h-[46px] pl-10 pr-10 rounded-lg text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-zinc-900 focus:border-zinc-900 transition-all border bg-white border-zinc-200"
                />
                <button type="button" @click="showPassword = !showPassword" class="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 transition-colors">
                  <EyeOff v-if="showPassword" class="w-[18px] h-[18px]" />
                  <Eye v-else class="w-[18px] h-[18px]" />
                </button>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-zinc-700 mb-1.5">确认新密码</label>
              <div class="relative">
                <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none">
                  <Lock class="w-[18px] h-[18px]" />
                </div>
                <input
                  v-model="form.confirm_password"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  placeholder="再次输入新密码"
                  class="w-full h-[46px] pl-10 pr-10 rounded-lg text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-zinc-900 focus:border-zinc-900 transition-all border bg-white border-zinc-200"
                />
                <button type="button" @click="showConfirmPassword = !showConfirmPassword" class="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 transition-colors">
                  <EyeOff v-if="showConfirmPassword" class="w-[18px] h-[18px]" />
                  <Eye v-else class="w-[18px] h-[18px]" />
                </button>
              </div>
            </div>

            <div v-if="error" class="flex items-center gap-2 bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm border border-red-100">
              <AlertCircle class="w-4 h-4 flex-shrink-0" />
              <span>{{ error }}</span>
            </div>

            <button
              type="submit"
              :disabled="loading"
              class="w-full h-[46px] bg-zinc-900 text-white text-sm font-medium rounded-lg hover:bg-zinc-800 transition-colors flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed active:scale-[0.99]"
            >
              <template v-if="loading">
                <div class="flex gap-1">
                  <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" />
                  <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style="animation-delay: 150ms" />
                  <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style="animation-delay: 300ms" />
                </div>
                重置中...
              </template>
              <template v-else>
                重置密码 <ArrowRight class="w-4 h-4" />
              </template>
            </button>
          </form>

          <p class="mt-8 text-center text-sm text-zinc-500">
            想起密码了？
            <router-link to="/login" class="text-zinc-900 font-medium hover:underline underline-offset-4">返回登录</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
