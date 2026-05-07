<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Lock, Message, User } from "@element-plus/icons-vue";

import AuthShell from "@/components/AuthShell.vue";
import { register } from "@/services/auth";
import { resolveHomeRoute } from "@/services/user";

const router = useRouter();
const formRef = ref(null);
const loading = ref(false);

const form = reactive({
  name: "",
  email: "",
  password: "",
  confirmPassword: "",
});

const validateConfirmPassword = (_rule, value, callback) => {
  if (!value) {
    callback(new Error("请再次输入密码"));
    return;
  }
  if (value !== form.password) {
    callback(new Error("两次输入的密码不一致"));
    return;
  }
  callback();
};

const rules = {
  name: [{ required: true, message: "请输入昵称", trigger: "blur" }],
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "邮箱格式不正确", trigger: ["blur", "change"] },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 6, message: "密码长度至少 6 位", trigger: "blur" },
  ],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: ["blur", "change"] }],
};

async function submitRegister() {
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) {
    return;
  }

  loading.value = true;
  try {
    const { confirmPassword, ...payload } = form;
    const user = await register(payload);
    ElMessage.success("注册成功，已自动登录。");
    router.push({ name: resolveHomeRoute(user) });
  } catch (error) {
    ElMessage.error(error.message || "注册失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <AuthShell
    eyebrow="创建你的新工作台"
    switch-text="已经有账号？"
    switch-label="去登录"
    switch-to="/login"
  >
    <div class="auth-form-head">
      <h2>创建账号</h2>
      <p>注册成功后会自动进入工作台。</p>
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="auth-form">
      <el-form-item label="昵称" prop="name">
        <el-input v-model="form.name" :prefix-icon="User" placeholder="例如：Hunter" />
      </el-form-item>

      <el-form-item label="邮箱" prop="email">
        <el-input v-model="form.email" :prefix-icon="Message" placeholder="name@example.com" />
      </el-form-item>

      <el-form-item label="密码" prop="password">
        <el-input
          v-model="form.password"
          :prefix-icon="Lock"
          type="password"
          show-password
          placeholder="请输入至少 6 位密码"
        />
      </el-form-item>

      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input
          v-model="form.confirmPassword"
          :prefix-icon="Lock"
          type="password"
          show-password
          placeholder="请再次输入密码"
          @keyup.enter="submitRegister"
        />
      </el-form-item>

      <el-button type="primary" class="auth-submit" :loading="loading" @click="submitRegister">
        注册并进入工作台
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
</style>
