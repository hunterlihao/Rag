import { ref } from 'vue';

/**
 * 优化 #16: 统一的加载状态管理
 * B2C 风格的加载状态 Hook
 */
export function useLoading(initialState = false) {
  const loading = ref(initialState);
  const loadingMessage = ref('');
  const loadingProgress = ref(undefined);
  const showLoadingProgress = ref(false);

  /**
   * 显示加载状态
   * @param {string} message - 加载提示文本
   * @param {boolean} showProgress - 是否显示进度条
   */
  function startLoading(message = '加载中...', showProgress = false) {
    loadingMessage.value = message;
    loadingProgress.value = 0;
    showLoadingProgress.value = showProgress;
    loading.value = true;
  }

  /**
   * 更新加载进度
   * @param {number} progress - 进度值 (0-100)
   */
  function updateProgress(progress) {
    loadingProgress.value = progress;
  }

  /**
   * 隐藏加载状态
   */
  function stopLoading() {
    loading.value = false;
    loadingMessage.value = '';
    loadingProgress.value = undefined;
    showLoadingProgress.value = false;
  }

  /**
   * 异步操作包装器
   * @param {Function} asyncFn - 异步函数
   * @param {string} message - 加载提示
   * @returns {Promise} 异步函数的结果
   */
  async function withLoading(asyncFn, message = '处理中...') {
    startLoading(message);
    try {
      const result = await asyncFn();
      return result;
    } finally {
      stopLoading();
    }
  }

  return {
    loading,
    loadingMessage,
    loadingProgress,
    showLoadingProgress,
    startLoading,
    updateProgress,
    stopLoading,
    withLoading,
  };
}
