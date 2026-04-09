<template>
  <div class="follow-up-panel">
    <div class="follow-up-panel__header">
      <svg class="follow-up-panel__icon" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
        <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm1 11H9v-2h2v2zm0-4H9V5h2v4z"/>
      </svg>
      <span>为了给您更精准的分析，请补充以下信息：</span>
    </div>
    <div class="follow-up-panel__body">
      <div
        v-for="question in questions"
        :key="question.key"
        class="follow-up-item"
      >
        <div class="follow-up-item__label">{{ question.label }}</div>
        <div class="follow-up-item__input">
          <ElInput
            v-if="question.type === 'input'"
            v-model="answers[question.key]"
            :placeholder="'请输入...'"
            size="default"
          />
          <ElInput
            v-else-if="question.type === 'textarea'"
            v-model="answers[question.key]"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 3 }"
            :placeholder="'请输入...'"
          />
          <ElRadioGroup
            v-else-if="question.type === 'select' && question.options?.length"
            v-model="answers[question.key]"
          >
            <ElRadioButton
              v-for="opt in question.options"
              :key="opt"
              :value="opt"
            >
              {{ opt }}
            </ElRadioButton>
          </ElRadioGroup>
          <ElInput
            v-else
            v-model="answers[question.key]"
            :placeholder="'请输入...'"
            size="default"
          />
        </div>
      </div>
    </div>
    <div class="follow-up-panel__footer">
      <ElButton
        type="primary"
        size="default"
        :disabled="!hasAnyAnswer || loading"
        :loading="loading"
        @click="handleSubmit"
      >
        补充提交
      </ElButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, watch } from 'vue';
import { ElInput, ElButton, ElRadioGroup, ElRadioButton } from 'element-plus';
import type { FollowUpQuestion } from '../../kg_preview/utils/api';

const props = defineProps<{
  questions: FollowUpQuestion[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  submit: [answers: Record<string, string>];
}>();

const answers = reactive<Record<string, string>>({});

watch(
  () => props.questions,
  (qs) => {
    const validKeys = new Set(qs.map((q) => q.key));
    qs.forEach((q) => {
      if (answers[q.key] == null) answers[q.key] = '';
    });
    Object.keys(answers).forEach((k) => {
      if (!validKeys.has(k)) delete answers[k];
    });
  },
  { immediate: true },
);

const hasAnyAnswer = computed(() =>
  Object.values(answers).some((v) => v.trim()),
);

function handleSubmit() {
  const filled: Record<string, string> = {};
  for (const [k, v] of Object.entries(answers)) {
    if (v.trim()) filled[k] = v.trim();
  }
  emit('submit', filled);
}
</script>

<style scoped>
.follow-up-panel {
  margin-top: 12px;
  border: 1px solid #d0e8ff;
  border-radius: 8px;
  background: #f0f7ff;
  padding: 14px 16px;
}

.follow-up-panel__header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
  margin-bottom: 12px;
}

.follow-up-panel__icon {
  flex-shrink: 0;
  color: #3b82f6;
}

.follow-up-panel__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.follow-up-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.follow-up-item__label {
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}

.follow-up-item__input {
  max-width: 480px;
}

.follow-up-item__input :deep(textarea) {
  resize: none;
}

.follow-up-panel__footer {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
