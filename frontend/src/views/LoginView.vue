<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Lock, Message } from "@element-plus/icons-vue";

import AuthShell from "@/components/AuthShell.vue";
import { login } from "@/services/auth";
import { resolveHomeRoute } from "@/services/user";

const router = useRouter();
const formRef = ref(null);
const loading = ref(false);

const form = reactive({
  email: "",
  password: "",
});

const rules = {
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "邮箱格式不正确", trigger: ["blur", "change"] },
  ],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

async function submitLogin() {
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) {
    return;
  }

  loading.value = true;
  try {
    const user = await login(form);
    ElMessage.success("登录成功，正在进入工作台。");
    router.push({ name: resolveHomeRoute(user) });
  } catch (error) {
    ElMessage.error(error.message || "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <AuthShell
    eyebrow="登录你的知识库工作台"
    switch-text="还没有账号？"
    switch-label="去注册"
    switch-to="/register"
  >
    <div class="auth-form-head">
      <h2>欢迎回来</h2>
      <p>先登录，再进入新的 RAG 前端工作台。</p>
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="auth-form">
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="form.email" :prefix-icon="Message" placeholder="name@example.com" />
      </el-form-item>

      <el-form-item label="密码" prop="password">
        <el-input
          v-model="form.password"
          :prefix-icon="Lock"
          type="password"
          show-password
          placeholder="请输入密码"
          @keyup.enter="submitLogin"
        />
      </el-form-item>

      <el-button type="primary" class="auth-submit" :loading="loading" @click="submitLogin">
        登录并进入工作台
      </el-button>
    </el-form>
  </AuthShell>
</template>

<style scoped>
.auth-form-head h2 {
  margin: 0;
  font-size: 2rem;
}

.auth-form-head p {
  margin: 10px 0 0;
  color: var(--muted);
}

.auth-form {
  margin-top: 28px;
}

.auth-submit {
  width: 100%;
  height: 48px;
  margin-top: 12px;
  border: none;
  border-radius: 18px;
  background: linear-gradient(135deg, #1d4dcc, #326cf2);
  font-weight: 800;
}

.auth-demo-note {
  margin-top: 18px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  line-height: 1.7;
}
</style>
