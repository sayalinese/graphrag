<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { Page } from '@vben/common-ui';
import {
  ElButton,
  ElDialog,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElTable,
  ElTableColumn,
  ElTag,
  ElEmpty,
  ElUpload,
  ElProgress,
} from 'element-plus';
import type { UploadFile, UploadUserFile } from 'element-plus';
import { useKBApi, type KnowledgeBaseVO } from './utils/api';

const { kbList, loading, listKBs, createKB, updateKB, deleteKB } = useKBApi();

// 对话框状态
const showCreateDialog = ref(false);
const showDetailDrawer = ref(false);
const editingKB = ref<KnowledgeBaseVO | null>(null);

// 表单模型
const formModel = reactive({
  name: '',
  description: '',
});

// 上传文件
const uploadedFiles = ref<UploadUserFile[]>([]);

// 初始化
onMounted(() => {
  listKBs();
});

// ============ 知识库管理 ============

function handleCreate() {
  editingKB.value = null;
  Object.assign(formModel, {
    name: '',
    description: '',
  });
  showCreateDialog.value = true;
}

async function handleSave() {
  if (!formModel.name.trim()) {
    ElMessage.warning('请输入知识库名称');
    return;
  }

  try {
    if (editingKB.value && editingKB.value.id) {
      await updateKB(editingKB.value.id, {
        name: formModel.name,
        description: formModel.description,
      });
      ElMessage.success('更新成功');
    } else {
      await createKB({
        name: formModel.name,
        description: formModel.description,
      });
      ElMessage.success('创建成功');
    }
    showCreateDialog.value = false;
    await listKBs();
  } catch (error) {
    ElMessage.error('操作失败');
  }
}

function handleEdit(row: KnowledgeBaseVO) {
  editingKB.value = row;
  Object.assign(formModel, row);
  showCreateDialog.value = true;
}

function handleDelete(row: KnowledgeBaseVO) {
  if (!row.id) return;
  ElMessageBox.confirm(`删除知识库"${row.name}"？`, '确认删除', {
    type: 'warning',
  })
    .then(async () => {
      if (row.id) {
        await deleteKB(row.id);
        ElMessage.success('删除成功');
      }
    })
    .catch(() => {});
}

function handleViewDetail(row: KnowledgeBaseVO) {
  editingKB.value = row;
  showDetailDrawer.value = true;
}

// ============ 文档管理 ============

function handleFileChange(_file: UploadFile, fileList: UploadUserFile[]) {
  uploadedFiles.value = fileList;
}

function handleFileRemove(file: UploadFile) {
  uploadedFiles.value = uploadedFiles.value.filter((f) => f.uid !== file.uid);
}

async function handleUpload() {
  if (!editingKB.value || uploadedFiles.value.length === 0) {
    ElMessage.warning('请选择要上传的文件');
    return;
  }

  // TODO: 调用上传 API
  ElMessage.success('上传成功');
  uploadedFiles.value = [];
}
</script>

<template>
  <Page title="知识库管理">
    <template #extra>
      <ElButton type="primary" @click="handleCreate">
        <i class="i-line-md:plus mr-1" /> 新建知识库
      </ElButton>
    </template>

    <!-- 知识库列表 -->
    <div class="bg-card rounded-lg shadow-sm p-4">
      <ElTable :data="kbList" stripe v-loading="loading" style="width: 100%">
        <ElTableColumn prop="name" label="知识库名称" width="200" />
        <ElTableColumn prop="description" label="描述" />
        <ElTableColumn prop="document_count" label="文档数" width="100" />
        <ElTableColumn prop="chunk_count" label="分片数" width="100" />
        <ElTableColumn prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleDateString() : '-' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" size="small" @click="handleViewDetail(row)">
              详情
            </ElButton>
            <ElButton link type="primary" size="small" @click="handleEdit(row)">
              编辑
            </ElButton>
            <ElButton link type="danger" size="small" @click="handleDelete(row)">
              删除
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>

      <ElEmpty v-if="!loading && kbList.length === 0" description="暂无知识库" />
    </div>

    <!-- 创建/编辑对话框 -->
    <ElDialog
      v-model="showCreateDialog"
      :title="editingKB ? '编辑知识库' : '创建新知识库'"
      width="500px"
    >
      <ElForm :model="formModel" label-width="100px">
        <ElFormItem label="知识库名称" required>
          <ElInput v-model="formModel.name" placeholder="输入知识库名称" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput
            v-model="formModel.description"
            type="textarea"
            :rows="3"
            placeholder="输入知识库描述"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <div class="flex justify-end gap-2">
          <ElButton @click="showCreateDialog = false">取消</ElButton>
          <ElButton type="primary" @click="handleSave">
            {{ editingKB ? '更新' : '创建' }}
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- 知识库详情侧边栏 -->
    <ElDrawer v-model="showDetailDrawer" title="知识库详情" size="40%">
      <div v-if="editingKB" class="space-y-4">
        <!-- 基本信息 -->
        <div>
          <h3 class="font-semibold mb-3">基本信息</h3>
          <div class="space-y-2 text-sm">
            <div class="flex gap-4">
              <span class="text-muted-foreground w-20">名称:</span>
              <span>{{ editingKB.name }}</span>
            </div>
            <div class="flex gap-4">
              <span class="text-muted-foreground w-20">描述:</span>
              <span>{{ editingKB.description || '-' }}</span>
            </div>
            <div class="flex gap-4">
              <span class="text-muted-foreground w-20">分类:</span>
              <span>{{ editingKB.category || '-' }}</span>
            </div>
            <div class="flex gap-4">
              <span class="text-muted-foreground w-20">创建:</span>
              <span>{{ editingKB.created_at ? new Date(editingKB.created_at).toLocaleString() : '-' }}</span>
            </div>
          </div>
        </div>

        <!-- 统计信息 -->
        <div>
          <h3 class="font-semibold mb-3">统计信息</h3>
          <div class="space-y-2 text-sm">
            <div class="flex items-center justify-between">
              <span class="text-muted-foreground">文档数量:</span>
              <ElTag>{{ editingKB.document_count }}</ElTag>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-muted-foreground">分片数量:</span>
              <ElTag>{{ editingKB.chunk_count }}</ElTag>
            </div>
          </div>
        </div>

        <!-- 文档上传 -->
        <div>
          <h3 class="font-semibold mb-3">上传文档</h3>
          <ElUpload
            action="#"
            multiple
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :show-file-list="true"
            drag
          >
            <template #default>
              <div class="text-center p-6 border-2 border-dashed border-border rounded">
                <i class="i-line-md:upload-outline text-3xl mb-2" />
                <p class="text-sm">拖拽文件到此或点击选择</p>
              </div>
            </template>
          </ElUpload>

          <div v-if="uploadedFiles.length" class="mt-3 space-y-2">
            <div
              v-for="file in uploadedFiles"
              :key="file.uid"
              class="flex items-center justify-between p-2 bg-muted rounded"
            >
              <span class="text-sm truncate">{{ file.name }}</span>
              <span class="text-xs text-muted-foreground">
                {{ (file.size ? file.size / 1024 / 1024 : 0).toFixed(2) }}MB
              </span>
            </div>

            <ElButton type="primary" @click="handleUpload" class="w-full">
              开始上传
            </ElButton>
          </div>
        </div>
      </div>
    </ElDrawer>
  </Page>
</template>
