<template>
  <ElDialog
    v-model="visible"
    title="病因信息收集"
    width="960px"
    top="6vh"
    append-to-body
    :close-on-click-modal="false"
    class="patient-intake-dialog"
  >
    <ElSteps
      :active="currentStep"
      finish-status="success"
      align-center
      class="mt-4"
    >
      <ElStep title="基础信息" description="年龄、性别、高危背景" />
      <ElStep title="症状定位" description="主诉、病程与动态追问" />
      <ElStep title="用药与附件" description="近期处理、报告和照片" />
    </ElSteps>

    <ElScrollbar max-height="68vh" class="mt-4 pr-2">
      <section v-if="currentStep === 0" class="step-panel">
        <div class="step-panel__title">患者基础身份与风险背景</div>
        <div class="step-panel__grid grid-cols-1">
          <label class="intake-field">
            <span class="field-label">年龄 <em>*</em></span>
            <ElInput
              v-model.number="form.age"
              type="number"
              :min="0"
              :max="120"
              style="width: 180px;"
              placeholder="请输入年龄"
            >
              <template #append>岁</template>
            </ElInput>
          </label>

          <label class="intake-field">
            <span class="field-label">性别 <em>*</em></span>
            <ElRadioGroup v-model="form.sex" class="w-full">
              <ElRadioButton value="男">男</ElRadioButton>
              <ElRadioButton value="女">女</ElRadioButton>
            </ElRadioGroup>
          </label>

          <label class="intake-field">
            <span class="field-label"
              >妊娠情况 <em v-if="form.sex === '女'">*</em></span
            >
            <ElRadioGroup v-model="form.pregnancyStatus" class="w-full">
              <ElRadioButton value="否">否</ElRadioButton>
              <ElRadioButton value="是">是</ElRadioButton>
              <ElRadioButton value="不适用" :disabled="form.sex === '女'"
                >不适用</ElRadioButton
              >
            </ElRadioGroup>
          </label>

          <div class="intake-field">
            <span class="field-label">过敏史</span>
            <div class="flex-1 flex items-center gap-3 w-full">
              <ElRadioGroup v-model="hasAllergy" @change="handleAllergyChange" class="shrink-0">
                <ElRadioButton :value="false">无</ElRadioButton>
                <ElRadioButton :value="true">有</ElRadioButton>
              </ElRadioGroup>
              <ElSelect
                v-if="hasAllergy"
                v-model="form.allergyHistory"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="请选择或输入过敏药物/物质"
                class="flex-1"
              >
                <ElOption
                  v-for="item in ['青霉素类', '头孢类', '磺胺类', '大环内酯类', '海鲜/异体蛋白']"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </ElSelect>
            </div>
          </div>

          <div class="intake-field">
            <span class="field-label">慢性病 / 既往史</span>
            <div class="flex-1 flex items-center gap-3 w-full">
              <ElRadioGroup v-model="hasChronic" @change="handleChronicChange" class="shrink-0">
                <ElRadioButton :value="false">无</ElRadioButton>
                <ElRadioButton :value="true">有</ElRadioButton>
              </ElRadioGroup>
              <ElSelect
                v-if="hasChronic"
                v-model="form.chronicDiseases"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="请选择或输入既往病史"
                class="flex-1"
              >
                <ElOption
                  v-for="item in ['高血压', '糖尿病', '冠心病', '高脂血症', '慢性支气管炎/哮喘', '慢性肾病', '恶性肿瘤史']"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </ElSelect>
            </div>
          </div>
        </div>
      </section>

      <section v-else-if="currentStep === 1" class="step-panel">
        <div class="step-panel__title">当前主诉与动态追问</div>
        <div class="step-panel__grid grid-cols-1">
          <label class="intake-field">
            <span class="field-label">生病特征 <em>*</em></span>
            <ElInput
              v-model="form.chiefComplaint"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              resize="none"
              placeholder="例如：发热伴咳嗽 3 天，今天气短加重；或右下腹持续疼痛 6 小时"
            />
          </label>

          <label class="intake-field">
            <span class="field-label">起病时长</span>
            <ElSelect
              v-model="form.duration"
              filterable
              allow-create
              placeholder="下拉选择或输入"
              class="w-full"
            >
              <ElOption
                v-for="item in ['24小时内', '1到3天', '4到7天', '1到2周', '1个月以上', '反复发作更久']"
                :key="item"
                :label="item"
                :value="item"
              />
            </ElSelect>
          </label>

          <label class="intake-field">
            <span class="field-label">主观严重程度</span>
            <ElRadioGroup v-model="form.severity" class="w-full">
              <ElRadioButton value="轻">轻</ElRadioButton>
              <ElRadioButton value="中">中</ElRadioButton>
              <ElRadioButton value="重">重</ElRadioButton>
            </ElRadioGroup>
          </label>

          <label class="intake-field">
            <span class="field-label">伴随症状</span>
            <ElSelect
              v-model="form.accompanyingSymptoms"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="可多选或直接输入（如：咽痛、咳痰、胸痛等）"
              class="w-full"
            >
              <ElOption
                v-for="item in ['无明显伴随症状', '发热', '乏力/酸痛', '咳嗽', '咳痰', '胸闷/胸痛', '恶心/呕吐', '腹痛', '腹泻', '头痛', '头晕', '皮疹', '排尿异常']"
                :key="item"
                :label="item"
                :value="item"
              />
            </ElSelect>
          </label>
        </div>

        <div class="followup-block mt-4">
          <div class="followup-block__header">
            <div>
              <div class="followup-block__title">动态追问</div>
            </div>
            <ElTag size="small" type="info">规则驱动</ElTag>
          </div>

          <div class="followup-list mt-2">
            <div
              v-for="question in followUpQuestions"
              :key="question.key"
              class="followup-card"
            >
              <div class="followup-question-label">{{ question.label }}</div>
              <div class="followup-question-content w-full mt-2">
                <ElInput
                  v-if="question.type === 'input'"
                  v-model="followUpAnswers[question.key]"
                  :placeholder="question.placeholder"
                  clearable
                  class="w-full"
                />
                <ElInput
                  v-else-if="question.type === 'textarea'"
                  v-model="followUpAnswers[question.key]"
                  type="textarea"
                  :autosize="{ minRows: 1, maxRows: 4 }"
                  resize="none"
                  :placeholder="question.placeholder"
                  class="w-full"
                />
                <ElRadioGroup
                  v-else
                  v-model="followUpAnswers[question.key]"
                  class="w-full"
                >
                  <ElRadioButton
                    v-for="option in question.options"
                    :key="option"
                    :value="option"
                  >
                    {{ option }}
                  </ElRadioButton>
                </ElRadioGroup>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-else class="step-panel">
        <div class="step-panel__title">近期用药、已做处理与附件上传</div>
        <div class="step-panel__grid grid-cols-1">
          <label class="intake-field">
            <span class="field-label">当前正在使用的药物</span>
            <ElSelect
              v-model="form.currentMedication"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="可多选或直接输入"
              class="w-full"
            >
              <ElOption
                v-for="item in ['未服药', '解热镇痛药(退烧/止痛)', '抗生素(消炎药)', '降血药/降脂药', '降糖药/胰岛素', '胃肠道用药', '中成药/草药']"
                :key="item"
                :label="item"
                :value="item"
              />
            </ElSelect>
          </label>

          <label class="intake-field">
            <span class="field-label">本次发病后已做处理</span>
            <ElSelect
              v-model="form.previousTreatment"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="可多选或直接输入"
              class="w-full"
            >
              <ElOption
                v-for="item in ['暂未处理', '已自行保守处理/休息', '已在急诊/门诊就诊', '已完成血液化验', '已完成影像学(CT/X光)', '已外用止血/包扎']"
                :key="item"
                :label="item"
                :value="item"
              />
            </ElSelect>
          </label>

          <label class="intake-field">
            <span class="field-label">附件补充说明</span>
            <ElInput
              v-model="form.attachmentNote"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              resize="none"
              placeholder="例如：图片是皮疹部位，PDF 是昨天的血常规和 CT 报告"
            />
          </label>
        </div>

        <div class="upload-block mt-4">
          <div class="upload-block__header">
            <div>
              <div class="followup-block__title">附件上传与解析</div>
              <div class="followup-block__desc">
              </div>
            </div>
            <div class="upload-block__stats" v-if="attachments.length">
              <ElTag size="small" type="success"
                >已上传 {{ attachments.length }} 份</ElTag
              >
              <ElTag v-if="parsingCount > 0" size="small" type="warning"
                >解析中 {{ parsingCount }}</ElTag
              >
            </div>
          </div>

          <ElUpload
            action="#"
            :auto-upload="false"
            :show-file-list="false"
            accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.jpg,.jpeg,.png,.webp"
            multiple
            @change="handleAttachmentChange"
          >
            <ElButton type="primary" plain>上传报告或图片</ElButton>
          </ElUpload>

          <div v-if="attachments.length" class="attachment-list mt-4">
            <div
              v-for="attachment in attachments"
              :key="attachment.id"
              class="attachment-card"
            >
              <div class="attachment-card__header">
                <div>
                  <div class="attachment-card__title">
                    {{ attachment.filename }}
                  </div>
                  <div class="attachment-card__meta">
                    {{
                      attachment.category === 'image' ? '图片附件' : '文档附件'
                    }}
                    <span>·</span>
                    <span>{{ formatFileSize(attachment.size) }}</span>
                    <span v-if="attachment.parser"
                      >· {{ attachment.parser }}</span
                    >
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <ElTag
                    :type="attachmentTagType(attachment.status)"
                    size="small"
                    >{{ attachmentStatusText(attachment.status) }}</ElTag
                  >
                  <ElButton
                    text
                    type="danger"
                    @click="removeAttachment(attachment.id)"
                    >移除</ElButton
                  >
                </div>
              </div>

              <div
                v-if="attachment.status === 'parsing'"
                class="attachment-parsing"
              >
                <span class="mr-2">正在抽取可用于诊断的摘要...</span>
              </div>
              <div
                v-else-if="attachment.status === 'error'"
                class="attachment-summary is-error"
              >
                {{ attachment.error || '附件解析失败，可移除后重新上传。' }}
              </div>
              <div
                v-else
                class="attachment-summary"
                :class="attachment.degraded ? 'is-degraded' : ''"
              >
                {{ attachment.summary }}
              </div>
            </div>
          </div>

          <ElEmpty
            v-else
            description="未上传附件时，也可以直接基于文字病情生成诊断问题。"
            :image-size="72"
          />
        </div>
      </section>
    </ElScrollbar>

    <template #footer>
      <div class="patient-intake-footer">
        <ElButton text @click="resetForm">清空重填</ElButton>
        <div class="flex items-center gap-2">
          <ElButton @click="visible = false">取消</ElButton>
          <ElButton v-if="currentStep > 0" @click="currentStep -= 1"
            >上一步</ElButton
          >
          <ElButton v-if="currentStep < 2" type="primary" @click="goNextStep"
            >下一步</ElButton
          >
          <ElButton
            v-else
            type="primary"
            :loading="submitting"
            @click="submitIntake"
            >生成诊断问题</ElButton
          >
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<script lang="ts" setup>
import { computed, reactive, ref, watch } from 'vue';
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElOption,
  ElScrollbar,
  ElStep,
  ElSteps,
  ElTag,
  ElUpload,
} from 'element-plus';
import type { UploadFile } from 'element-plus';
import {
  parsePatientIntakeAttachment,
  type PatientIntakeSubmitPayload,
  type PatientIntakeAttachmentSummary,
} from '../../kg_preview/utils/api';

type AttachmentStatus = 'done' | 'error' | 'parsing';
type Sex = '' | '男' | '女';
type PregnancyStatus = '' | '不适用' | '否' | '是';
type FollowUpQuestionType = 'input' | 'select' | 'textarea';

interface FollowUpQuestion {
  key: string;
  label: string;
  type: FollowUpQuestionType;
  options?: string[];
  placeholder?: string;
  help?: string;
}

interface IntakeFormState {
  age: number | null;
  sex: Sex;
  pregnancyStatus: PregnancyStatus;
  allergyHistory: string[];
  chronicDiseases: string[];
  chiefComplaint: string;
  duration: string;
  severity: string;
  accompanyingSymptoms: string[];
  currentMedication: string[];
  previousTreatment: string[];
  attachmentNote: string;
}

interface LocalAttachment {
  id: string;
  filename: string;
  size: number;
  category: 'document' | 'image';
  status: AttachmentStatus;
  summary: string;
  parsedText?: string;
  parser?: string;
  degraded?: boolean;
  error?: string;
}

const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  submit: [payload: PatientIntakeSubmitPayload];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
});

const currentStep = ref(0);
const submitting = ref(false);
const attachments = ref<LocalAttachment[]>([]);
const followUpAnswers = reactive<Record<string, string>>({});
const form = reactive<IntakeFormState>(createInitialForm());

const hasAllergy = ref(false);
const hasChronic = ref(false);

function handleAllergyChange(val: boolean) {
  if (!val) {
    form.allergyHistory = [];
  }
}

function handleChronicChange(val: boolean) {
  if (!val) {
    form.chronicDiseases = [];
  }
}

const followUpTemplates: Array<{
  keywords: string[];
  questions: FollowUpQuestion[];
}> = [
  {
    keywords: ['发热', '咳', '咽', '呼吸', '气短', '胸闷', '痰', '肺'],
    questions: [
      {
        key: 'temperaturePeak',
        label: '最高体温大概多少？',
        type: 'input',
        placeholder: '例如 38.7℃',
      },
      {
        key: 'sputumCharacter',
        label: '是否咳痰，痰是什么颜色？',
        type: 'textarea',
        placeholder: '例如 无痰、黄痰、白痰带血丝',
      },
      {
        key: 'dyspneaTrigger',
        label: '气短或胸闷在什么情况下明显？',
        type: 'textarea',
        placeholder: '例如 活动后加重、平躺加重、持续存在',
      },
    ],
  },
  {
    keywords: ['腹痛', '腹泻', '呕吐', '恶心', '胃', '肚子', '便血'],
    questions: [
      {
        key: 'painLocation',
        label: '腹痛主要在哪个部位？',
        type: 'input',
        placeholder: '例如 右下腹、上腹部、脐周',
      },
      {
        key: 'stoolChange',
        label: '近期大便有无变化？',
        type: 'textarea',
        placeholder: '例如 腹泻、便秘、黑便、便血',
      },
      {
        key: 'mealRelation',
        label: '症状与进食关系如何？',
        type: 'select',
        options: ['进食后加重', '空腹更明显', '无明显关系', '不确定'],
      },
    ],
  },
  {
    keywords: ['头痛', '头晕', '胸痛', '心慌', '血压', '麻木'],
    questions: [
      {
        key: 'painNature',
        label: '不适的性质更接近哪种？',
        type: 'select',
        options: ['胀痛', '刺痛', '压榨感', '眩晕感', '不清楚'],
      },
      {
        key: 'neurologicSymptoms',
        label: '是否伴随肢体无力、麻木、言语不清或意识改变？',
        type: 'select',
        options: ['是', '否', '不确定'],
      },
      {
        key: 'bloodPressureInfo',
        label: '近期血压或心率是否明显异常？',
        type: 'textarea',
        placeholder: '例如 血压 170/100，心率 120 次/分',
      },
    ],
  },
];

const fallbackFollowUps: FollowUpQuestion[] = [
  {
    key: 'symptomProgression',
    label: '症状整体是在加重、缓解还是反复波动？',
    type: 'select',
    options: ['持续加重', '逐渐缓解', '反复波动', '不确定'],
  },
  {
    key: 'triggerFactors',
    label: '发病前是否有明确诱因？',
    type: 'textarea',
    placeholder: '例如 受凉、劳累、饮酒、饮食不洁、外伤、熬夜等',
  },
  {
    key: 'redFlags',
    label: '目前最担心或最危险的表现是什么？',
    type: 'textarea',
    placeholder: '例如 持续高热、胸痛、呼吸困难、便血、抽搐等',
  },
];

const followUpQuestions = computed<FollowUpQuestion[]>(() => {
  const text =
    `${form.chiefComplaint} ${(form.accompanyingSymptoms || []).join(' ')}`.toLowerCase();
  const matched = followUpTemplates.find((template) =>
    template.keywords.some((keyword) => text.includes(keyword)),
  );
  return matched?.questions || fallbackFollowUps;
});

const parsingCount = computed(
  () => attachments.value.filter((item) => item.status === 'parsing').length,
);

watch(
  () => form.sex,
  (value) => {
    if (value === '女') {
      if (form.pregnancyStatus === '不适用') {
        form.pregnancyStatus = '';
      }
    } else if (value) {
      form.pregnancyStatus = '不适用';
    } else {
      form.pregnancyStatus = '';
    }
  },
  { immediate: true },
);

watch(
  followUpQuestions,
  (questions) => {
    const validKeys = new Set(questions.map((question) => question.key));
    questions.forEach((question) => {
      if (followUpAnswers[question.key] == null) {
        followUpAnswers[question.key] = '';
      }
    });
    Object.keys(followUpAnswers).forEach((key) => {
      if (!validKeys.has(key)) {
        delete followUpAnswers[key];
      }
    });
  },
  { immediate: true },
);

function createInitialForm(): IntakeFormState {
  return {
    age: null,
    sex: '',
    pregnancyStatus: '',
    allergyHistory: [],
    chronicDiseases: [],
    chiefComplaint: '',
    duration: '',
    severity: '',
    accompanyingSymptoms: [],
    currentMedication: [],
    previousTreatment: [],
    attachmentNote: '',
  };
}

async function startDiagnosis() {
  if (submitting.value) {
    return;
  }
  submitting.value = true;
  try {
    const combinedSummary = buildStructuredSummary();
    const payload: PatientIntakeSubmitPayload = {
      summary: combinedSummary,
      attachments: buildAttachmentSummaries(),
    };
    emit('submit', payload);
    emit('update:modelValue', false);
  } finally {
    submitting.value = false;
  }
}

function goNextStep() {
  if (!validateStep(currentStep.value)) {
    return;
  }
  currentStep.value += 1;
}

function validateStep(step: number) {
  if (step === 0) {
    if (form.age == null || Number.isNaN(form.age)) {
      ElMessage.warning('请先填写患者年龄');
      return false;
    }
    if (!form.sex) {
      ElMessage.warning('请先选择患者性别');
      return false;
    }
    if (form.sex === '女' && !form.pregnancyStatus) {
      ElMessage.warning('请补充妊娠情况');
      return false;
    }
  }

  if (step === 1) {
    if (!form.chiefComplaint.trim()) {
      ElMessage.warning('请先填写当前主诉');
      return false;
    }
  }

  if (step === 2 && parsingCount.value > 0) {
    ElMessage.warning('还有附件正在解析，请稍等片刻');
    return false;
  }

  return true;
}

async function handleAttachmentChange(file: UploadFile) {
  const rawFile = file.raw as File | undefined;
  if (!rawFile) {
    return;
  }

  const localItem: LocalAttachment = {
    id: String(file.uid),
    filename: rawFile.name,
    size: rawFile.size,
    category: rawFile.type.startsWith('image/') ? 'image' : 'document',
    status: 'parsing',
    summary: '正在解析附件内容...',
  };

  attachments.value = [
    localItem,
    ...attachments.value.filter((item) => item.id !== localItem.id),
  ];

  try {
    const parsed = await parsePatientIntakeAttachment(rawFile);
    updateAttachment(localItem.id, {
      filename: parsed.filename,
      size: parsed.size,
      category: parsed.category,
      status: parsed.error ? 'error' : 'done',
      summary: parsed.summary,
      parsedText: parsed.parsed_text,
      parser: parsed.parser,
      degraded: parsed.degraded,
      error: parsed.error,
    });
  } catch (error: any) {
    updateAttachment(localItem.id, {
      status: 'error',
      summary: '附件解析失败',
      error: error?.message || '附件解析失败，请稍后重试',
    });
  }
}

function updateAttachment(id: string, patch: Partial<LocalAttachment>) {
  attachments.value = attachments.value.map((item) =>
    item.id === id ? { ...item, ...patch } : item,
  );
}

function removeAttachment(id: string) {
  attachments.value = attachments.value.filter((item) => item.id !== id);
}

function attachmentStatusText(status: AttachmentStatus) {
  if (status === 'parsing') {
    return '解析中';
  }
  if (status === 'error') {
    return '失败';
  }
  return '完成';
}

function attachmentTagType(status: AttachmentStatus) {
  if (status === 'parsing') {
    return 'warning';
  }
  if (status === 'error') {
    return 'danger';
  }
  return 'success';
}

function formatFileSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${size} B`;
}

function buildAttachmentSummaries(): PatientIntakeAttachmentSummary[] {
  return attachments.value.map((attachment) => ({
    filename: attachment.filename,
    category: attachment.category,
    parser:
      attachment.parser ||
      (attachment.category === 'image' ? 'image-metadata' : 'document-preview'),
    summary: attachment.error || attachment.summary,
    parsed_text: attachment.parsedText,
    degraded: attachment.degraded,
    error: attachment.error,
  }));
}

function buildStructuredSummary() {
  const followUpLines = followUpQuestions.value
    .map((question) => {
      const answer = (followUpAnswers[question.key] || '').trim();
      return answer ? `- ${question.label}：${answer}` : '';
    })
    .filter(Boolean);

  const attachmentLines = buildAttachmentSummaries().map((attachment) => {
    const prefix = attachment.category === 'image' ? '图片' : '文档';
    return `- ${prefix}《${attachment.filename}》：${attachment.summary}`;
  });

  return [
    '【患者基础信息】',
    `- 年龄：${form.age ?? '未提供'}`,
    `- 性别：${form.sex || '未提供'}`,
    `- 妊娠情况：${form.pregnancyStatus || '未提供'}`,
    `- 过敏史：${hasAllergy.value ? (form.allergyHistory.length ? form.allergyHistory.join('、') : '有（未说明）') : '无'}`,
    `- 慢性病 / 既往史：${hasChronic.value ? (form.chronicDiseases.length ? form.chronicDiseases.join('、') : '有（未说明）') : '无'}`,
    '',
    '【本次主诉】',
    `- 当前主诉：${form.chiefComplaint.trim() || '未提供'}`,
    `- 起病时间 / 持续时长：${form.duration.trim() || '未提供'}`,
    `- 严重程度：${form.severity || '未提供'}`,
    `- 伴随症状：${form.accompanyingSymptoms.length ? form.accompanyingSymptoms.join('、') : '未提供'}`,
    '',
    '【动态追问】',
    ...(followUpLines.length ? followUpLines : ['- 暂无额外补充']),
    '',
    '【近期用药与处理】',
    `- 当前用药：${form.currentMedication.length ? form.currentMedication.join('、') : '未提供'}`,
    `- 已做处理：${form.previousTreatment.length ? form.previousTreatment.join('、') : '未提供'}`,
    '',
    '【附件摘要】',
    ...(attachmentLines.length ? attachmentLines : ['- 未上传附件']),
    `- 附件补充说明：${form.attachmentNote.trim() || '未提供'}`,
  ].join('\n');
}

function buildQuestionPrompt(structuredSummary: string) {
  return [
    '请基于以下患者定位信息，进行一次偏临床实用的初步诊断分析。',
    '',
    structuredSummary,
    '',
    '请按以下结构回答：',
    '1. 初步判断与最需要优先关注的问题',
    '2. 重点鉴别诊断',
    '3. 建议补充的检查或化验',
    '4. 当前可行的治疗与处理建议',
    '5. 明确的风险边界与何时需要立即线下就医',
    '6. 如果信息仍不足，请指出最关键的下一步追问',
  ].join('\n');
}

async function submitIntake() {
  if (!validateStep(2)) {
    return;
  }

  submitting.value = true;
  try {
    const structuredSummary = buildStructuredSummary();
    const questionPrompt = buildQuestionPrompt(structuredSummary);
    emit('submit', {
      sourceLabel: '患者定位问诊',
      structuredSummary,
      questionPrompt,
      displayQuestion: `已提交患者定位信息：${form.chiefComplaint.trim() || '请结合上述资料进行诊断分析'}`,
      attachmentSummaries: buildAttachmentSummaries(),
    });

    resetForm();
    visible.value = false;
  } finally {
    submitting.value = false;
  }
}

function resetForm() {
  Object.assign(form, createInitialForm());
  hasAllergy.value = false;
  hasChronic.value = false;
  attachments.value = [];
  Object.keys(followUpAnswers).forEach((key) => {
    delete followUpAnswers[key];
  });
  currentStep.value = 0;
}
</script>

<style scoped>
.step-panel {
  padding: 4px;
  animation: fadeIn 0.4s ease-out;
  max-width: 800px;
  margin: 0 auto;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.step-panel__title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.step-panel__grid {
  display: grid;
  gap: 12px;
}

.grid-cols-1 { grid-template-columns: minmax(0, 1fr); }
.col-span-1 { grid-column: span 1 / span 1; }

.intake-field {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16px;
}

.intake-field > :not(.field-label) {
  flex: 1;
  min-width: 0;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  display: flex;
  align-items: center;
  width: 140px;
  flex-shrink: 0;
  justify-content: flex-end;
}

.field-label em {
  color: #ef4444;
  font-style: normal;
  margin-left: 4px;
}

.field-help {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.followup-block,
.upload-block {
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 12px;
  padding: 16px;
  background: #f8fafc;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
  transition: all 0.3s ease;
  margin-top: 16px;
  margin-left: 156px;
}

.followup-block:hover,
.upload-block:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
  border-color: rgba(203, 213, 225, 0.8);
}

.followup-block__header,
.upload-block__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.followup-block__title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.followup-block__desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.followup-list {
  display: grid;
  gap: 12px;
}

.followup-card,
.attachment-card {
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 10px;
  padding: 12px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.followup-card:hover,
.attachment-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
}

.followup-question-label {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.followup-question-content {
  display: flex;
}

.attachment-list {
  display: grid;
  gap: 16px;
}

.attachment-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.attachment-card__title {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
}

.attachment-card__meta {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.attachment-summary,
.attachment-parsing {
  margin-top: 16px;
  border-radius: 10px;
  padding: 14px 16px;
  font-size: 13px;
  line-height: 1.6;
  color: #334155;
  background: #f1f5f9;
  border-left: 3px solid #cbd5e1;
}

.attachment-summary.is-error {
  color: #991b1b;
  background: #fef2f2;
  border-left-color: #f87171;
}

.attachment-summary.is-degraded {
  color: #92400e;
  background: #fffbeb;
  border-left-color: #fbbf24;
}

.patient-intake-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding-top: 20px;
  border-top: 1px solid #f1f5f9;
  margin: 20px auto 0;
  max-width: 800px;
}

:deep(.el-input-number.w-full) { width: 100%; }

:deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

:deep(.el-radio-button__inner) {
  border-radius: 8px !important;
  border: 1px solid #e2e8f0 !important;
  box-shadow: none !important;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background-color: #f0f9ff;
  border-color: #38bdf8 !important;
  color: #0284c7;
  box-shadow: 0 2px 6px rgba(14, 165, 233, 0.15) !important;
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  border-radius: 6px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  transition: all 0.2s ease;
  padding-top: 4px;
  padding-bottom: 4px;
}

:deep(.el-input__inner) {
  height: 32px;
}

:deep(.el-select) {
  --el-component-size: 32px;
}

:deep(.el-input__wrapper:hover),
:deep(.el-textarea__inner:hover) {
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}

:deep(.el-input__wrapper.is-focus),
:deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1.5px #38bdf8 inset !important;
}

:deep(.el-step__title.is-process) {
  font-weight: 700;
  color: #0284c7;
}

:deep(.el-step__head.is-process) {
  color: #0284c7;
  border-color: #0284c7;
}

/* Dark mode */
:deep(.dark .step-panel__title),
:deep(.dark .followup-block__title),
:deep(.dark .attachment-card__title) { color: #f8fafc; }

:deep(.dark .field-label) { color: #e2e8f0; }
:deep(.dark .field-help),
:deep(.dark .followup-block__desc),
:deep(.dark .attachment-card__meta) { color: #94a3b8; }

:deep(.dark .followup-block),
:deep(.dark .upload-block) {
  border-color: rgba(51, 65, 85, 0.5);
  background: rgba(30, 41, 59, 0.4);
}

:deep(.dark .followup-card),
:deep(.dark .attachment-card) {
  border-color: rgba(51, 65, 85, 0.8);
  background: rgba(30, 41, 59, 0.8);
}

:deep(.dark .attachment-summary),
:deep(.dark .attachment-parsing) {
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.6);
  border-left-color: #475569;
}

:deep(.dark .attachment-summary.is-error) {
  color: #fca5a5;
  background: rgba(69, 10, 10, 0.4);
  border-left-color: #7f1d1d;
}

:deep(.dark .attachment-summary.is-degraded) {
  color: #fde68a;
  background: rgba(69, 26, 3, 0.4);
  border-left-color: #78350f;
}

:deep(.dark .patient-intake-footer) { border-top-color: rgba(51, 65, 85, 0.5); }

:deep(.dark .el-radio-button__inner) {
  background-color: transparent;
  border-color: #334155 !important;
  color: #cbd5e1;
}

:deep(.dark .el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background-color: rgba(14, 165, 233, 0.15);
  border-color: #0ea5e9 !important;
  color: #38bdf8;
  box-shadow: none !important;
}

@media (max-width: 860px) {
  .intake-field {
    flex-direction: column;
    align-items: stretch;
  }
  .field-label {
    width: auto;
    justify-content: flex-start;
    margin-top: 0;
  }
  .patient-intake-footer,
  .followup-block__header,
  .upload-block__header,
  .attachment-card__header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
