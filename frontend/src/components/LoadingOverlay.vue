<template>
  <Transition name="loading-fade">
    <div v-if="visible" class="loading-overlay" :class="{ 'overlay-fullscreen': fullscreen }">
      <div class="loading-container">
        <!-- B2C 风格: 圆形旋转加载器 -->
        <div class="loading-spinner">
          <svg class="spinner" viewBox="0 0 50 50">
            <circle
              class="spinner-path"
              cx="25"
              cy="25"
              r="20"
              fill="none"
              stroke-width="4"
            />
          </svg>
        </div>
        
        <!-- 徽章文本（可选） -->
        <div v-if="badgeText" class="loading-badge">
          {{ badgeText }}
        </div>
        
        <!-- 加载标题 -->
        <div v-if="title" class="loading-title">
          {{ title }}
        </div>
        
        <!-- 加载描述 -->
        <div v-if="description" class="loading-description">
          {{ description }}
        </div>
        
        <!-- 进度条（可选） -->
        <div v-if="showProgress && progress !== undefined" class="loading-progress">
          <div class="progress-bar">
            <div 
              class="progress-fill" 
              :style="{ width: `${Math.min(100, Math.max(0, progress))}%` }"
            />
          </div>
          <span class="progress-text">{{ Math.round(progress) }}%</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  badgeText: {
    type: String,
    default: '',
  },
  title: {
    type: String,
    default: '',
  },
  description: {
    type: String,
    default: '',
  },
  message: {
    type: String,
    default: '',
  },
  progress: {
    type: Number,
    default: undefined,
  },
  showProgress: {
    type: Boolean,
    default: false,
  },
  fullscreen: {
    type: Boolean,
    default: true,
  },
});
</script>

<style scoped>
/* B2C 风格加载动画 */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.overlay-fullscreen {
  background: rgba(255, 255, 255, 0.95);
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px;
}

/* 旋转加载器 */
.loading-spinner {
  width: 48px;
  height: 48px;
}

.spinner {
  animation: rotate 2s linear infinite;
  width: 100%;
  height: 100%;
}

.spinner-path {
  stroke: #3b82f6; /* B2C 蓝色 */
  stroke-linecap: round;
  animation: dash 1.5s ease-in-out infinite;
}

@keyframes rotate {
  100% {
    transform: rotate(360deg);
  }
}

@keyframes dash {
  0% {
    stroke-dasharray: 1, 150;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -35;
  }
  100% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -124;
  }
}

/* 徽章文本 */
.loading-badge {
  display: inline-block;
  padding: 4px 12px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  font-weight: 500;
  border-radius: 9999px;
  margin-bottom: 8px;
}

/* 加载标题 */
.loading-title {
  font-size: 16px;
  color: #111827;
  text-align: center;
  font-weight: 600;
  margin-bottom: 4px;
}

/* 加载描述 */
.loading-description {
  font-size: 13px;
  color: #6b7280;
  text-align: center;
  line-height: 1.5;
}

/* 加载文本（兼容旧版） */
.loading-message {
  font-size: 14px;
  color: #6b7280;
  text-align: center;
  font-weight: 500;
}

/* 进度条 */
.loading-progress {
  width: 100%;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: #e5e7eb;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%);
  transition: width 0.3s ease;
  border-radius: 2px;
}

.progress-text {
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}

/* 过渡动画 */
.loading-fade-enter-active,
.loading-fade-leave-active {
  transition: opacity 0.3s ease;
}

.loading-fade-enter-from,
.loading-fade-leave-to {
  opacity: 0;
}
</style>
