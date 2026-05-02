<template>
  <div style="padding: 40px; text-align: center;">
    <h1 style="font-size: 28px;">🔄 AI 分析中...</h1>
    <p style="color: #666; margin-top: 16px;">这里将展示流式推理过程</p>
    <button 
      @click="$router.push('/skin/result/' + $route.params.sessionId)"
      style="margin-top: 32px; padding: 16px 32px; font-size: 18px; background: #2C7A7B; color: white; border: none; border-radius: 24px; cursor: pointer;"
    >
      查看结果（演示用）
    </button>
  </div>
</template>