<template>
  <div class="kg-chat-window relative flex h-full w-full overflow-hidden backdrop-blur-sm">
    <aside
      class="kg-chat-sidebar relative flex shrink-0 flex-col border-r border-slate-800/80 transition-all duration-300"
      :class="isSidebarCollapsed ? 'w-[88px]' : 'w-72 xl:w-80'"
    >
      <ElTooltip :content="isSidebarCollapsed ? '展开侧栏' : '折叠侧栏'" placement="bottom">
        <button
          class="sidebar-handle absolute -right-4 top-4 z-20 flex h-8 w-8 items-center justify-center rounded-full border shadow-[0_8px_24px_rgba(0,0,0,0.22)] transition-colors hover:opacity-80"
          @click="toggleSidebar"
        >
          <el-icon class="text-base transition-transform duration-300" :class="isSidebarCollapsed ? 'rotate-180' : ''">
            <Fold />
          </el-icon>
        </button>
      </ElTooltip>

      <div v-if="!isSidebarCollapsed" class="space-y-3 border-b border-slate-800/80 px-3 pb-3">
        <div class="grid grid-cols-2 gap-2">
          <ElSelect
            v-model="selectedStrategy"
            size="small"
            placeholder="搜索策略"
            class="strategy-select"
            popper-class="strategy-select-dropdown"
            :teleported="true"
            :popper-options="{ modifiers: [{ name: 'offset', options: { offset: [0, 4] } }] }"
          >
            <template #prefix>
              <el-icon class="text-slate-500"><Operation /></el-icon>
            </template>
            <ElOption
              v-for="opt in strategyOptions"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            >
              <div class="flex flex-col py-1">
                <span class="font-medium">{{ opt.label }}</span>
                <span class="mt-0.5 text-xs text-slate-500">{{ opt.desc }}</span>
              </div>
            </ElOption>
          </ElSelect>

          <ElSelect
            v-model="selectedDatabase"
            size="small"
            placeholder="选择数据库"
            class="doc-select"
            popper-class="doc-select-dropdown"
            :teleported="true"
            :popper-options="{ modifiers: [{ name: 'offset', options: { offset: [0, 4] } }] }"
          >
            <template #prefix>
              <el-icon class="text-slate-500"><Document /></el-icon>
            </template>
            <ElOption
              v-for="database in databases"
              :key="database.name"
              :value="database.name"
              :label="database.name"
            >
              <div class="truncate">{{ database.name }}</div>
            </ElOption>
          </ElSelect>
        </div>

      </div>

      <div v-if="!isSidebarCollapsed" class="px-4 pb-2 text-xs font-medium uppercase tracking-[0.24em] text-slate-500">
        历史会话
      </div>

      <ElScrollbar class="flex-1" :class="isSidebarCollapsed ? 'px-2' : 'px-3'">
        <div v-if="isSessionLoading" class="flex justify-center py-4">
          <el-icon class="is-loading text-sky-400"><Loading /></el-icon>
        </div>
        <div v-else class="space-y-2 pb-4">
          <div
            v-for="session in sessions"
            :key="session.session_id"
            class="session-item group relative cursor-pointer rounded-xl border transition-all duration-200"
            :class="[
              currentSessionId === session.session_id ? 'is-active' : '',
              isSidebarCollapsed ? 'p-2' : 'p-3',
            ]"
            :title="session.name || '未命名会话'"
            @click="switchSession(session.session_id)"
          >
            <template v-if="isSidebarCollapsed">
              <div
                class="session-icon mx-auto flex h-9 w-9 items-center justify-center rounded-lg border transition-colors"
              >
                <el-icon class="text-sm"><ChatDotSquare /></el-icon>
              </div>
            </template>
            <template v-else>
              <div class="session-name truncate pr-6 text-[12px] font-medium tracking-[0.01em]">
                {{ session.name || '未命名会话' }}
              </div>
              <button
                class="session-delete absolute right-2 top-1/2 -translate-y-1/2 opacity-0 transition-opacity hover:text-rose-400 group-hover:opacity-100"
                @click.stop="handleDeleteSession(session.session_id, $event)"
              >
                <el-icon><Delete /></el-icon>
              </button>
            </template>
          </div>

          <div v-if="sessions.length === 0" class="py-8 text-center text-sm text-slate-500" :class="isSidebarCollapsed ? 'px-1 text-[11px]' : ''">
            {{ isSidebarCollapsed ? '暂无' : '暂无历史会话' }}
          </div>
        </div>
      </ElScrollbar>
    </aside>

    <div class="kg-chat-main relative flex h-full min-w-0 flex-1 flex-col bg-background">
      <div class="relative flex h-full w-full flex-1 flex-col">
        <ElScrollbar ref="scrollRef" class="flex-1 px-2">
      <div class="chat-main-inner space-y-6 px-3 py-6">
        <!-- 服务状态提示 -->
        <div
          v-if="serviceStatus === 'offline'"
          class="status-offline-banner mb-6 p-3 rounded-lg border flex items-center justify-between"
        >
          <div class="flex items-center gap-2 text-red-400 text-sm">
            <el-icon class="text-lg"><Warning /></el-icon>
            <span>GraphRAG 服务未连接</span>
          </div>
          <button 
            class="retry-btn px-3 py-1 text-xs font-medium rounded transition-colors"
            @click="retryConnection"
          >
            重试连接
          </button>
        </div>

        <div
          v-if="serviceStatus === 'checking'"
          class="flex items-center justify-center gap-2 py-8 text-slate-500"
        >
          <el-icon class="text-xl text-sky-400 is-loading"><Loading /></el-icon>
          <span class="text-sm">正在连接知识图谱服务...</span>
        </div>

        <!-- 消息 -->
        <div
          v-for="message in messages"
          :key="message.id"
          class="message-item group"
          :class="message.role"
        >
          <!-- 用户消息 -->
          <div
            v-if="message.role === 'user'"
            class="flex justify-end pl-12"
          >
            <div class="flex max-w-full flex-col items-end">
              <div v-if="message.sourceLabel" class="message-source-badge user-source-badge mb-2">
                {{ message.sourceLabel }}
              </div>
              <div
                class="user-bubble px-4 py-2.5 text-sm leading-relaxed"
              >
                {{ message.content }}
              </div>
              <div
                v-if="message.patientIntake?.structured_summary"
                class="patient-intake-card"
              >
                <button
                  type="button"
                  class="patient-intake-card__header"
                  @click="toggleCollapse(message.id, 'patient-intake')"
                >
                  <div class="patient-intake-card__header-main">
                    <span class="patient-intake-card__title">患者定位摘要</span>
                    <span
                      v-if="getPatientIntakeAttachmentCount(message)"
                      class="patient-intake-card__meta"
                    >
                      已解析 {{ getPatientIntakeAttachmentCount(message) }} 份资料
                    </span>
                  </div>
                  <el-icon
                    class="patient-intake-card__arrow transition-transform duration-200"
                    :class="{ 'rotate-180': !isCollapsed(message.id, 'patient-intake') }"
                  >
                    <ArrowDown />
                  </el-icon>
                </button>
                <div
                  v-if="isCollapsed(message.id, 'patient-intake')"
                  class="patient-intake-card__preview"
                >
                  {{ getPatientIntakePreview(message) }}
                </div>
                <div v-else class="patient-intake-card__body">
                  <div
                    class="markdown-body prose prose-sm max-w-none"
                    v-html="renderMarkdown(formatPatientIntakeMarkdown(message.patientIntake.structured_summary))"
                  />
                  <div
                    v-if="getPatientIntakeAttachments(message).length"
                    class="patient-intake-attachments"
                  >
                    <div class="patient-intake-attachments__title">已解析资料</div>
                    <div class="patient-intake-attachments__list">
                      <div
                        v-for="attachment in getPatientIntakeAttachments(message)"
                        :key="`${message.id}-${attachment.filename}`"
                        class="patient-intake-attachment"
                      >
                        <div class="patient-intake-attachment__head">
                          <span class="patient-intake-attachment__name">{{ attachment.filename }}</span>
                          <span class="patient-intake-attachment__tag">
                            {{ attachment.category === 'image' ? '影像/图片' : '文档资料' }}
                          </span>
                        </div>
                        <div class="patient-intake-attachment__summary">{{ attachment.summary }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 助手消息 -->
          <div v-else class="assistant-message pr-8">
            <div class="assistant-label">
              <span class="assistant-label__spark"></span>
              <span>{{ message.strategy ? `${getStrategyLabel(message.strategy)} 图谱回答` : '知识图谱回答' }}</span>
            </div>

            <div class="flex max-w-full min-w-0 flex-col">
              <div
                class="assistant-bubble px-5 py-4 rounded-2xl rounded-tl-sm border shadow-sm backdrop-blur-sm"
              >
                <div v-if="message.expertStages?.length" class="expert-stage-card mb-3">
                  <div class="expert-stage-card__title">多专家协作</div>
                  <div class="expert-stage-list">
                    <div
                      v-for="stage in message.expertStages"
                      :key="stage.key"
                      class="expert-stage-item"
                      :class="`is-${stage.status}`"
                    >
                      <span class="expert-stage-dot" :class="`is-${stage.status}`"></span>
                      <div class="min-w-0 flex-1">
                        <div class="expert-stage-name">{{ stage.title }}</div>
                        <div
                          v-if="stage.detail"
                          class="expert-stage-detail markdown-body prose prose-sm max-w-none"
                          v-html="renderMarkdown(stage.detail)"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 加载中 -->
                <div v-if="message.loading" class="flex items-center gap-3 py-1">
                  <div class="flex gap-1">
                    <div class="h-2 w-2 rounded-full bg-sky-400 animate-bounce" style="animation-delay: 0ms"></div>
                    <div class="h-2 w-2 rounded-full bg-sky-400 animate-bounce" style="animation-delay: 150ms"></div>
                    <div class="h-2 w-2 rounded-full bg-sky-400 animate-bounce" style="animation-delay: 300ms"></div>
                  </div>
                  <span class="text-xs font-medium text-sky-400 animate-pulse">{{ message.loadingText || '正在思考...' }}</span>
                </div>

                <!-- 错误 -->
                <div
                  v-else-if="message.error"
                  class="text-red-400 flex items-start gap-2 text-sm"
                >
                  <el-icon class="mt-0.5 flex-shrink-0"><WarningFilled /></el-icon>
                  <span>{{ message.content }}</span>
                </div>

                <!-- 正常内容 -->
                <template v-else>
                  <div
                    class="markdown-body prose prose-sm max-w-none"
                    v-html="renderMarkdown(message.content)"
                  />

                  <!-- 追问补充面板 -->
                  <FollowUpPanel
                    v-if="message.followUpQuestions?.length && !message.loading"
                    :questions="message.followUpQuestions"
                    :loading="isLoading"
                    @submit="handleFollowUpSubmit(message, $event)"
                  />

                  <div v-if="message.isWelcome" class="welcome-intake-action mt-4">
                    <button
                      class="welcome-intake-action__btn"
                      type="button"
                      :disabled="isLoading"
                      @click="openPatientIntake"
                    >
                      快速定位患者信息
                    </button>
                    <div class="welcome-intake-action__hint">适合先补齐年龄、主诉、用药和检查资料，再自动发起一次更聚焦的诊断问答。</div>
                  </div>

                  <div v-if="hasMessageGraph(message.id)" class="inline-graph-card">
                    <div class="inline-graph-card__header">
                      <div class="inline-graph-card__title">可解释图谱</div>
                      <div class="inline-graph-card__meta">
                        <span>{{ getMessageGraphNodeCount(message.id) }} 个节点</span>
                        <span>{{ getMessageGraphLinkCount(message.id) }} 条关系</span>
                      </div>
                    </div>
                    <div class="inline-graph-card__body">
                      <KgGraph2D :graph-data="messageGraphMap[message.id]" />
                    </div>
                  </div>

                  <!-- 底部元数据栏 -->
                  <div class="ft-divider mt-4 flex flex-wrap items-center gap-3 border-t pt-3">
                    <!-- 策略标签 -->
                    <div
                      v-if="message.strategy"
                      class="meta-badge flex items-center gap-1.5 rounded border px-2 py-1"
                    >
                      <el-icon class="text-xs text-slate-500"><Operation /></el-icon>
                      <span class="text-xs font-medium" :class="getStrategyColorClass(message.strategy)">
                        {{ getStrategyLabel(message.strategy) }}
                      </span>
                    </div>

                    <div
                      v-if="message.sourceLabel"
                      class="meta-badge flex items-center gap-1.5 rounded border px-2 py-1"
                    >
                      <span class="text-xs font-medium text-sky-500 dark:text-sky-300">
                        {{ message.sourceLabel }}
                      </span>
                    </div>
                    
                    <div
                      v-if="message.communities_used"
                      class="meta-badge flex items-center gap-1.5 rounded border px-2 py-1"
                    >
                      <el-icon class="text-xs"><Connection /></el-icon>
                      <span class="text-xs">
                        {{ message.communities_used }} 个社区
                      </span>
                    </div>
                  </div>

                  <!-- 附加信息折叠面板 -->
                  <div
                    v-if="
                      message.entities?.length ||
                      message.relations?.length ||
                      message.chunks?.length
                    "
                    class="mt-3 space-y-2"
                  >
                    <!-- 相关实体 -->
                    <div v-if="message.entities?.length" class="collapse-panel overflow-hidden rounded-lg border">
                      <button 
                        class="panel-toggle-btn flex w-full items-center justify-between px-3 py-2 text-xs font-medium transition-colors"
                        @click="toggleCollapse(message.id, 'entities')"
                      >
                        <div class="flex items-center gap-2">
                          <el-icon class="text-cyan-400"><DataBoard /></el-icon>
                          <span>相关实体 ({{ message.entities.length }})</span>
                        </div>
                        <el-icon class="transition-transform duration-200" :class="{ 'rotate-180': !isCollapsed(message.id, 'entities') }"><ArrowDown /></el-icon>
                      </button>
                      
                      <div v-show="!isCollapsed(message.id, 'entities')" class="panel-content border-t px-3 pb-3 pt-1">
                        <div class="flex flex-wrap gap-1.5">
                          <button
                            v-for="entity in message.entities.slice(0, 20)"
                            :key="entity.name"
                            class="entity-chip flex items-center gap-1 rounded border px-2 py-1 text-xs transition-colors"
                            @click="handleEntityClick(entity)"
                          >
                            {{ entity.name }}
                            <span v-if="entity.type" class="chip-type text-[10px]">
                              {{ entity.type }}
                            </span>
                          </button>
                          <button
                            v-if="message.entities.length > 0"
                            class="ml-1 flex items-center gap-1 rounded px-2 py-1 text-xs text-sky-600 transition-colors hover:bg-sky-50 hover:text-sky-700 dark:text-sky-300 dark:hover:bg-sky-950/25 dark:hover:text-sky-100"
                            @click="handleHighlightEntities(message.entities!)"
                          >
                            <el-icon><Aim /></el-icon>
                            选择调用节点
                          </button>
                        </div>
                      </div>
                    </div>

                    <!-- 实体关系 -->
                    <div v-if="message.relations?.length" class="collapse-panel overflow-hidden rounded-lg border">
                      <button 
                        class="panel-toggle-btn flex w-full items-center justify-between px-3 py-2 text-xs font-medium transition-colors"
                        @click="toggleCollapse(message.id, 'relations')"
                      >
                        <div class="flex items-center gap-2">
                          <el-icon class="text-sky-400"><Share /></el-icon>
                          <span>实体关系 ({{ message.relations.length }})</span>
                        </div>
                        <el-icon class="transition-transform duration-200" :class="{ 'rotate-180': !isCollapsed(message.id, 'relations') }"><ArrowDown /></el-icon>
                      </button>
                      
                      <div v-show="!isCollapsed(message.id, 'relations')" class="panel-content border-t px-3 pb-3 pt-1">
                        <div class="space-y-1.5">
                          <div
                            v-for="(rel, idx) in message.relations.slice(0, 15)"
                            :key="idx"
                            class="rel-row flex items-center gap-2 rounded px-2 py-1.5 text-xs"
                          >
                            <span class="rel-src flex-shrink-0 font-medium">{{ rel.source }}</span>
                            <el-icon class="text-[10px] flex-shrink-0 opacity-40"><ArrowRight /></el-icon>
                            <span class="rel-badge max-w-[200px] truncate rounded border px-1.5 py-0.5 text-[10px]" :title="rel.description || rel.type">
                              {{ rel.description || rel.type }}
                            </span>
                            <el-icon class="text-[10px] flex-shrink-0 opacity-40"><ArrowRight /></el-icon>
                            <span class="rel-src flex-shrink-0 font-medium">{{ rel.target }}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- 原文片段 -->
                    <div v-if="message.chunks?.length" class="collapse-panel overflow-hidden rounded-lg border">
                      <button 
                        class="panel-toggle-btn flex w-full items-center justify-between px-3 py-2 text-xs font-medium transition-colors"
                        @click="toggleCollapse(message.id, 'chunks')"
                      >
                        <div class="flex items-center gap-2">
                          <el-icon class="text-yellow-500"><Document /></el-icon>
                          <span>原文片段 ({{ message.chunks.length }})</span>
                        </div>
                        <el-icon class="transition-transform duration-200" :class="{ 'rotate-180': !isCollapsed(message.id, 'chunks') }"><ArrowDown /></el-icon>
                      </button>
                      
                      <div v-show="!isCollapsed(message.id, 'chunks')" class="panel-content border-t px-3 pb-3 pt-1">
                        <div class="space-y-2">
                          <div
                            v-for="(chunk, idx) in message.chunks.slice(0, 5)"
                            :key="idx"
                            class="chunk-card rounded border p-2.5 text-xs transition-colors"
                          >
                            <div
                              v-if="chunk.score"
                              class="chunk-divider mb-1.5 flex items-center justify-between border-b pb-1.5"
                            >
                              <span class="text-[10px] text-slate-500">片段 #{{ idx + 1 }}</span>
                              <span class="text-[10px] font-mono text-sky-400/80">
                                Score: {{ (chunk.score as number).toFixed(3) }}
                              </span>
                            </div>
                            <div class="line-clamp-3 leading-relaxed opacity-90">{{ chunk.text }}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
              </div>

              <div v-if="!message.loading && !message.error && message.content" class="assistant-actions">
                <button
                  class="assistant-action"
                  type="button"
                  title="复制回答"
                  @click="copyMessageContent(message.content)"
                >
                  <el-icon><CopyDocument /></el-icon>
                </button>
                <button
                  class="assistant-action"
                  type="button"
                  title="重试此问题"
                  @click="retryMessage(message.id)"
                >
                  <el-icon><RefreshRight /></el-icon>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
        </ElScrollbar>

        <div
          class="chat-input px-5 py-4 border-t backdrop-blur-sm"
        >
          <div class="chat-main-inner">
            <div class="input-shell relative flex items-end gap-2">
              <!-- 角色选择器 -->
              <div class="relative shrink-0 self-center pl-2">
                <button
                  class="char-pick-btn flex items-center gap-1.5 rounded-full px-2 py-1 text-xs transition-all"
                  :class="selectedCharacter ? 'char-pick-active' : ''"
                  @click="toggleCharacterPicker"
                >
                  <img
                    v-if="selectedCharacter?.avatar"
                    :src="selectedCharacter.avatar"
                    class="h-5 w-5 rounded-full object-cover"
                  />
                  <span v-else class="flex h-5 w-5 items-center justify-center rounded-full bg-sky-500/20 text-[10px] text-sky-400">
                    AI
                  </span>
                  <span class="max-w-[60px] truncate">{{ selectedCharacter?.name || '默认' }}</span>
                  <span class="char-mode-pill">{{ expertMode === 'multi' ? '多专家' : '标准' }}</span>
                  <el-icon class="text-[10px] transition-transform" :class="showCharacterPicker ? 'rotate-180' : ''">
                    <ArrowDown />
                  </el-icon>
                </button>

                <Transition name="fade-up">
                  <div v-if="showCharacterPicker" class="char-picker-popup absolute bottom-full left-0 z-50 mb-2 w-52 rounded-xl border p-2 shadow-xl">
                    <div class="mb-1.5 px-2 text-[10px] font-medium uppercase tracking-wider opacity-50">回答模式</div>
                    <div class="mb-2 grid grid-cols-2 gap-1 px-1">
                      <button
                        class="char-mode-option rounded-lg px-2 py-1.5 text-[11px] font-medium transition-colors"
                        :class="expertMode === 'standard' ? 'char-mode-option-active' : ''"
                        @click="selectExpertMode('standard')"
                      >
                        标准回答
                      </button>
                      <button
                        class="char-mode-option rounded-lg px-2 py-1.5 text-[11px] font-medium transition-colors"
                        :class="expertMode === 'multi' ? 'char-mode-option-active' : ''"
                        @click="selectExpertMode('multi')"
                      >
                        多专家
                      </button>
                    </div>

                    <div class="mb-1.5 px-2 text-[10px] font-medium uppercase tracking-wider opacity-50">选择角色</div>
                    <div
                      class="char-picker-item flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 transition-colors"
                      :class="!selectedCharacter ? 'char-picker-active' : ''"
                      @click="selectCharacter(null)"
                    >
                      <span class="flex h-6 w-6 items-center justify-center rounded-full bg-slate-500/20 text-[10px]">AI</span>
                      <span class="text-xs">默认助手</span>
                    </div>
                    <div
                      v-for="char in characters"
                      :key="char.key"
                      class="char-picker-item flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 transition-colors"
                      :class="selectedCharacter?.key === char.key ? 'char-picker-active' : ''"
                      @click="selectCharacter(char)"
                    >
                      <img v-if="char.avatar" :src="char.avatar" class="h-6 w-6 rounded-full object-cover" />
                      <span v-else class="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500/20 text-[10px] text-sky-400">
                        {{ char.name?.charAt(0) || 'A' }}
                      </span>
                      <div class="min-w-0 flex-1">
                        <div class="truncate text-xs font-medium">{{ char.name }}</div>
                        <div class="truncate text-[10px] opacity-50">{{ char.personality || char.product }}</div>
                      </div>
                    </div>
                  </div>
                </Transition>
              </div>
              <ElInput
                v-model="inputText"
                type="textarea"
                :rows="1"
                :autosize="{ minRows: 1, maxRows: 4 }"
                placeholder="输入你的问题..."
                :disabled="isLoading"
                class="custom-input flex-1 min-w-0"
                @keydown="handleKeydown"
              />
              <div class="absolute right-2 bottom-1.5">
                <button
                  class="send-button rounded-lg bg-sky-600 p-1.5 text-white shadow-lg shadow-sky-950/30 transition-colors hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="!canSend"
                  @click="handleSend"
                >
                  <el-icon v-if="!isLoading" class="text-lg block"><Position /></el-icon>
                  <el-icon v-else class="animate-spin text-lg block"><Loading /></el-icon>
                </button>
              </div>
            </div>
            <div class="mt-2 flex justify-between px-1 text-[10px] text-slate-500">
              <span v-if="contextMessageCount > 0" class="flex items-center gap-1">
                <el-icon class="text-sky-400"><ChatDotSquare /></el-icon>
              </span>
              <span v-else></span>
              <span v-if="isLoading" class="text-sky-400 animate-pulse">正在生成回答...</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <PatientIntakeModal v-model="intakeDialogVisible" @submit="handlePatientIntakeSubmit" />
  </div>
</template>


<script lang="ts" setup>
import { computed, nextTick, onMounted, onUnmounted, ref, reactive, watch } from 'vue';
import {
  ElScrollbar,
  ElInput,
  ElTooltip,
  ElSelect,
  ElOption,
  ElMessage,
  ElIcon,
} from 'element-plus';
import {
  Operation,
  Delete,
  Fold,
  Warning,
  Loading,
  WarningFilled,
  Connection,
  DataBoard,
  ArrowDown,
  Aim,
  Share,
  ArrowRight,
  CopyDocument,
  Document,
  Position,
  RefreshRight,
  ChatDotSquare,
} from '@element-plus/icons-vue';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import KgGraph2D from './KgGraph2D.vue';
import PatientIntakeModal from './PatientIntakeModal.vue';
import {
  hybridSearchStream,
  getGraphStats,
  getKgSessions,
  createKgSession,
  getKgSessionMessages,
  deleteKgSession,
  getNeo4jDatabases,
  type KgSession,
  type KgChatMessage,
  type SearchStrategy,
  type EntityInfo,
  type RelationInfo,
  type ExpertStageState,
  type Neo4jDatabaseInfo,
  type PatientIntakeSubmitPayload,
  type PatientIntakeStreamPayload,
  type FollowUpQuestion,
} from '../../kg_preview/utils/api';
import FollowUpPanel from './FollowUpPanel.vue';
import { getAvailableCharacters, type CharacterVO } from '../../../kb/character/utils/api';

const props = defineProps<{
  selectedDatabase?: string;
}>();

const emit = defineEmits<{
  selectEntity: [entity: EntityInfo];
  highlightEntities: [entities: EntityInfo[]];
  'highlight-knowledge': [data: { entities: EntityInfo[]; relations: any[]; question?: string }];
  'kg-highlight': [payload: {
    seedNodeIds: string[];
    nodeIds: string[];
    linkIds: string[];
    maxDepth: number;
    graph?: { nodes: any[]; edges: any[]; links?: any[] };
  }];
  'update:selectedDatabase': [database: string];
}>();

// Markdown 渲染器
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: (str: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang, ignoreIllegals: true }).value;
      } catch (_) {}
    }
    return '';
  },
});

// 状态
const messages = ref<KgChatMessage[]>([]);
const inputText = ref('');
const isLoading = ref(false);
const intakeDialogVisible = ref(false);
const scrollRef = ref<InstanceType<typeof ElScrollbar>>();
const isSidebarCollapsed = ref(false);
const selectedStrategy = ref<SearchStrategy>('auto');
const serviceStatus = ref<'checking' | 'online' | 'offline'>('checking');
const graphStatsInfo = ref<{ nodes: number; edges: number; communities?: number } | null>(null);
const messageGraphMap = reactive<Record<string, { entities: EntityInfo[]; relations: RelationInfo[] }>>({});

// 数据库选择
const databases = ref<Neo4jDatabaseInfo[]>([]);
const selectedDatabase = ref<string>(props.selectedDatabase || '');

// 角色选择
const characters = ref<CharacterVO[]>([]);
const selectedCharacter = ref<CharacterVO | null>(null);
const showCharacterPicker = ref(false);
const expertMode = ref<'standard' | 'multi'>('multi');
const expertStageTemplates: ExpertStageState[] = [
  { key: 'evidence', title: '证据专家', status: 'pending' },
  { key: 'pathology', title: '病理专家', status: 'pending' },
  { key: 'reviewer', title: '审稿专家', status: 'pending' },
  { key: 'synthesis', title: '综合专家', status: 'pending' },
];

function createExpertStages(): ExpertStageState[] {
  return expertStageTemplates.map(stage => ({ ...stage }));
}

function updateExpertStage(message: KgChatMessage, stageEvent: ExpertStageState) {
  const stages = message.expertStages?.length ? message.expertStages : createExpertStages();
  const stageIndex = stages.findIndex(stage => stage.key === stageEvent.key);
  const nextStage = { ...stageEvent };

  if (stageIndex >= 0) {
    stages.splice(stageIndex, 1, {
      ...stages[stageIndex],
      ...nextStage,
    });
  } else {
    stages.push(nextStage);
  }

  message.expertStages = [...stages];
}

async function loadCharacters() {
  try {
    characters.value = await getAvailableCharacters();
  } catch (e) {
    console.warn('Failed to load characters:', e);
  }
}

function selectCharacter(char: CharacterVO | null) {
  selectedCharacter.value = char;
  showCharacterPicker.value = false;
}

function toggleCharacterPicker() {
  showCharacterPicker.value = !showCharacterPicker.value;
}

function selectExpertMode(mode: 'standard' | 'multi') {
  expertMode.value = mode;
}

function refreshWelcomeMessage() {
  if (messages.value.length === 1 && messages.value[0]?.role === 'assistant') {
    messages.value = [];
    addWelcomeMessage();
  }
}

function extractPatientIntakeSource(rawSources: any): PatientIntakeStreamPayload | undefined {
  const payload = rawSources?.patient_intake;
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  return {
    source_label:
      typeof payload.source_label === 'string' && payload.source_label.trim()
        ? payload.source_label.trim()
        : '患者定位问诊',
    structured_summary:
      typeof payload.structured_summary === 'string' ? payload.structured_summary : '',
    question_prompt:
      typeof payload.question_prompt === 'string' ? payload.question_prompt : undefined,
    attachment_summaries: Array.isArray(payload.attachment_summaries)
      ? payload.attachment_summaries
      : undefined,
  };
}

function clipText(text: string, maxLength = 120): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength).trim()}...`;
}

function formatPatientIntakeMarkdown(summary: string): string {
  return summary
    .split(/\r?\n/)
    .map((line) => {
      const trimmed = line.trim();
      if (!trimmed) {
        return '';
      }

      const sectionMatch = trimmed.match(/^【(.+?)】$/);
      if (sectionMatch) {
        return `**${sectionMatch[1]}**`;
      }

      return trimmed;
    })
    .join('\n\n')
    .trim();
}

function getPatientIntakeAttachments(message: KgChatMessage) {
  return message.patientIntake?.attachment_summaries || [];
}

function getPatientIntakeAttachmentCount(message: KgChatMessage): number {
  return getPatientIntakeAttachments(message).length;
}

function getPatientIntakePreview(message: KgChatMessage): string {
  const summary = message.patientIntake?.structured_summary || '';
  const previewLines = summary
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line && !/^【.+】$/.test(line));

  if (!previewLines.length) {
    return '已提交结构化患者资料，可展开查看完整问诊摘要。';
  }

  return clipText(previewLines.slice(0, 3).join('；'));
}

// 监听外部数据库变化
watch(() => props.selectedDatabase, (newVal) => {
  if (newVal !== undefined && newVal !== selectedDatabase.value) {
    selectedDatabase.value = newVal;
  }
});

// 监听内部选择变化，通知父组件并刷新图谱状态
watch(selectedDatabase, async (newVal, oldVal) => {
  emit('update:selectedDatabase', newVal);
  if (newVal === oldVal) {
    return;
  }
  await checkServiceStatus();
  refreshWelcomeMessage();
});

// 加载 Neo4j 数据库列表
async function loadDatabases() {
  try {
    databases.value = await getNeo4jDatabases();
  } catch (error) {
    console.error('Failed to load neo4j databases:', error);
  }
}

// 会话管理
const sessions = ref<KgSession[]>([]);
const currentSessionId = ref<string>();
const isSessionLoading = ref(false);

// 加载会话列表
async function loadSessions() {
  try {
    sessions.value = await getKgSessions();
  } catch (error) {
    console.error('Failed to load sessions:', error);
  }
}

// 切换会话
async function switchSession(sessionId: string) {
  if (currentSessionId.value === sessionId) return;

  try {
    isSessionLoading.value = true;
    clearMessageGraphMap();
    const history = await getKgSessionMessages(sessionId);

    // 转换消息格式
    messages.value = history.map((msg) => {
      const localMeta = (msg as any).sources?.local || {};
      const patientIntakeSource = extractPatientIntakeSource(
        (msg as any).sources,
      );
      return {
        id: generateId(),
        role: msg.role,
        content: msg.content,
        apiContent:
          msg.role === 'user'
            ? patientIntakeSource?.question_prompt || msg.content
            : msg.content,
        timestamp: new Date(msg.timestamp),
        sources: msg.sources,
        sourceLabel: patientIntakeSource?.source_label,
        patientIntake: patientIntakeSource,
        entities: (msg as any).entities || localMeta.entities,
        relations: (msg as any).relations || localMeta.relations,
        chunks: (msg as any).chunks || localMeta.chunks,
        communities_used: (msg as any).communities_used ?? localMeta.communities_used,
        strategy: (msg as any).strategy || localMeta.strategy_used,
        loading: false,
      };
    });

    messages.value.forEach((message) => {
      if (message.role === 'assistant' && message.entities?.length) {
        setMessageGraphData(message.id, message.entities, message.relations || []);
      } else if (message.role === 'assistant' && message.relations?.length) {
        setMessageGraphData(message.id, [], message.relations);
      }
    });

    currentSessionId.value = sessionId;
  } catch (error) {
    ElMessage.error('加载会话消息失败');
    console.error(error);
  } finally {
    isSessionLoading.value = false;
  }
}

// 创建新会话
async function createNewSession() {
  currentSessionId.value = undefined;
  messages.value = [];
  clearMessageGraphMap();
  // 实际上我们不需要立即调用 API 创建，等到发送第一条消息时再创建
  // 或者在这里创建也可以，看交互设计。
  // 为了简单，这里只重置状态，发送消息时自动创建
}

// 删除会话
async function handleDeleteSession(sessionId: string, event: Event) {
  event.stopPropagation();
  try {
    await deleteKgSession(sessionId);
    sessions.value = sessions.value.filter((s) => s.session_id !== sessionId);
    if (currentSessionId.value === sessionId) {
      createNewSession();
    }
    ElMessage.success('会话已删除');
  } catch {
    ElMessage.error('删除会话失败');
  }
}

// 折叠状态管理
const collapseState = reactive<Record<string, Record<string, boolean>>>({});

function toggleCollapse(msgId: string, section: string) {
  if (!collapseState[msgId]) {
    collapseState[msgId] = {};
  }
  // 默认是展开的（undefined），点击后变为 true（折叠）
  // 或者默认折叠，点击展开。这里我们设计为默认折叠（true），点击展开（false）
  // 修正：UI上显示折叠面板，通常默认是折叠的。
  // isCollapsed 返回 true 表示折叠。
  // 初始状态：undefined -> 视为折叠(true)
  
  const current = isCollapsed(msgId, section);
  collapseState[msgId][section] = !current;
}

function isCollapsed(msgId: string, section: string): boolean {
  if (!collapseState[msgId]) {
    return true; // 默认折叠
  }
  return collapseState[msgId][section] !== false; // 除非明确设置为 false (展开)，否则折叠
}

// 策略选项
const strategyOptions = [
  { value: 'auto', label: '自动选择', desc: '智能判断搜索方式' },
  { value: 'local', label: 'Local Search', desc: '基于实体关系的精确搜索' },
  { value: 'global', label: 'Global Search', desc: '基于社区摘要的全局搜索' },
];

function normalizeVisibleStrategy(strategy: SearchStrategy | undefined): SearchStrategy {
  return strategy === 'both' ? 'auto' : (strategy ?? 'auto');
}

function clearMessageGraphMap() {
  Object.keys(messageGraphMap).forEach((key) => {
    delete messageGraphMap[key];
  });
}

function setMessageGraphData(messageId: string, entities: EntityInfo[], relations: RelationInfo[]) {
  if (!messageId || (!entities.length && !relations.length)) {
    delete messageGraphMap[messageId];
    return;
  }

  messageGraphMap[messageId] = {
    entities: [...entities],
    relations: [...relations],
  };
}

function hasMessageGraph(messageId: string) {
  const graphData = messageGraphMap[messageId];
  return !!graphData && (graphData.entities.length > 0 || graphData.relations.length > 0);
}

function getMessageGraphNodeCount(messageId: string) {
  return messageGraphMap[messageId]?.entities.length ?? 0;
}

function getMessageGraphLinkCount(messageId: string) {
  return messageGraphMap[messageId]?.relations.length ?? 0;
}

// 计算属性
const canSend = computed(() => inputText.value.trim() && !isLoading.value);
// 计算有效上下文消息数量（排除欢迎消息、加载中消息和错误消息）
const contextMessageCount = computed(() => {
  return messages.value.filter(msg => 
    !msg.loading && 
    !msg.error && 
    msg.content?.trim()
  ).length;
});

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
}

// 生成唯一 ID
function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// 滚动到底部
async function scrollToBottom() {
  await nextTick();
  if (scrollRef.value) {
    const scrollEl = scrollRef.value.wrapRef;
    if (scrollEl) {
      scrollEl.scrollTop = scrollEl.scrollHeight;
    }
  }
}

// 渲染 Markdown
function renderMarkdown(content: string): string {
  return md.render(content);
}

// 流式输出文本
// 检查服务状态
async function checkServiceStatus() {
  serviceStatus.value = 'checking';
  try {
    const stats = await getGraphStats(selectedDatabase.value);
    graphStatsInfo.value = stats;
    serviceStatus.value = 'online';
  } catch (error) {
    console.warn('GraphRAG service check failed:', error);
    graphStatsInfo.value = null;
    serviceStatus.value = 'offline';
  }
}

// 构建对话历史（用于 API 请求）
function buildApiChatHistory(limit = 12, endIndex = messages.value.length) {
  const history = messages.value
    .slice(0, endIndex)
    .filter((msg) => {
      if (msg.loading || msg.error) return false;
      if (!msg.content || !msg.content.trim()) return false;
      if (msg.isWelcome) return false;
      return msg.role === 'user' || msg.role === 'assistant';
    })
    .map((msg) => ({
      role: msg.role,
      content: msg.apiContent || msg.content,
    }));

  return history.slice(-limit);
}

function buildDemoRelationsByEntities(entities: EntityInfo[]): RelationInfo[] {
  if (!Array.isArray(entities) || entities.length < 2) return [];
  const relations: RelationInfo[] = [];
  for (let i = 0; i < entities.length - 1; i += 1) {
    const source = entities[i]?.name;
    const target = entities[i + 1]?.name;
    if (!source || !target) continue;
    relations.push({
      source,
      target,
      type: '关联',
      description: `${source} 与 ${target} 存在语义关联`,
    });
  }
  return relations;
}

function syncExpertLoadingText(message: KgChatMessage) {
  const runningStage = [...(message.expertStages || [])].reverse().find(stage => stage.status === 'running');
  if (runningStage) {
    message.loadingText = runningStage.detail || `${runningStage.title}处理中...`;
  }
}

interface SendQuestionOptions {
  displayContent?: string;
  sourceLabel?: string;
  patientIntake?: PatientIntakeStreamPayload;
  historyEndIndex?: number;
}

// 发送消息
async function sendQuestion(
  question: string,
  options: SendQuestionOptions = {},
) {
  const trimmedQuestion = question.trim();
  if (!trimmedQuestion || isLoading.value) return;

  const displayContent = (options.displayContent || trimmedQuestion).trim();

  // 发送前抓取历史上下文（不包含本轮问题）
  const apiChatHistory = buildApiChatHistory(
    12,
    options.historyEndIndex ?? messages.value.length,
  );

  if (!currentSessionId.value) {
    try {
      const session = await createKgSession(displayContent.slice(0, 20));
      currentSessionId.value = session.session_id;
      await loadSessions();
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  }

  const userMessage: KgChatMessage = {
    id: generateId(),
    role: 'user',
    content: displayContent,
    apiContent: trimmedQuestion,
    timestamp: new Date(),
    sourceLabel: options.sourceLabel,
    patientIntake: options.patientIntake,
    sources: options.patientIntake
      ? { patient_intake: options.patientIntake }
      : undefined,
  };
  messages.value.push(userMessage);

  const assistantMessage: KgChatMessage = {
    id: generateId(),
    role: 'assistant',
    content: '',
    timestamp: new Date(),
    loading: true,
    loadingText: '正在分析问题...',
    strategy: normalizeVisibleStrategy(selectedStrategy.value),
    expertStages: createExpertStages(),
    sourceLabel: options.sourceLabel,
    patientIntake: options.patientIntake,
    sources: options.patientIntake
      ? { patient_intake: options.patientIntake }
      : undefined,
  };
  messages.value.push(assistantMessage);

  inputText.value = '';
  isLoading.value = true;
  await scrollToBottom();

  const loadingStages = [
    '正在分析问题意图...',
    '正在检索知识图谱实体...',
    '正在构建可解释链路...',
    '正在生成最终回答...',
  ];
  let stageIndex = 0;
  let hasExpertStageEvent = false;
  const loadingInterval = setInterval(() => {
    const lastMsg = messages.value[messages.value.length - 1];
    if (lastMsg && lastMsg.loading) {
      if (stageIndex < loadingStages.length) {
        lastMsg.loadingText = loadingStages[stageIndex++];
      }
    } else {
      clearInterval(loadingInterval);
    }
  }, 800);

  try {
    const activeDatabase = selectedDatabase.value || props.selectedDatabase || '';
    if (!activeDatabase) {
      throw new Error('请先选择知识库（database）');
    }

    // 用于在 onMetadata 回调中发出图谱高亮
    const emitGraphHighlight = (
      entities: EntityInfo[],
      relations: RelationInfo[],
    ) => {
      const graphNodes = entities.map((entity: EntityInfo) => ({
        id: entity.name,
        label: entity.name,
        ...entity,
        value: 1,
      }));
      const graphEdges = relations.map((relation: RelationInfo, idx: number) => ({
        ...relation,
        id: `rel_${idx}`,
        source: relation.source,
        target: relation.target,
        relationType: relation.type,
        description: relation.description,
      }));
      emit('kg-highlight', {
        seedNodeIds: graphNodes.map((n: any) => n.id),
        nodeIds: graphNodes.map((n: any) => n.id),
        linkIds: graphEdges.map((e: any) => e.id),
        maxDepth: 1,
        graph: { nodes: graphNodes, edges: graphEdges, links: graphEdges },
      });
    };

    const lastMessage = messages.value[messages.value.length - 1];

    await hybridSearchStream(
      trimmedQuestion,
      normalizeVisibleStrategy(selectedStrategy.value),
      20,
      apiChatHistory,
      {
        onMetadata(meta) {
          if (!lastMessage || lastMessage.role !== 'assistant') return;
          clearInterval(loadingInterval);
          lastMessage.loading = false;
          lastMessage.strategy = normalizeVisibleStrategy(
            meta.strategy_used || selectedStrategy.value,
          );

          const apiEntities = meta.entities || [];
          const apiRelations = meta.relations || [];

          // 只有 API 返回了真实数据才更新图谱；无结果时保持图谱原样
          if (apiEntities.length > 0 || apiRelations.length > 0) {
            const explainRelations =
              apiRelations.length > 0
                ? apiRelations
                : buildDemoRelationsByEntities(apiEntities);

            lastMessage.entities = apiEntities;
            lastMessage.relations = explainRelations;
            lastMessage.chunks = meta.chunks || [];
            lastMessage.communities_used = meta.communities_used;
            setMessageGraphData(lastMessage.id, apiEntities, explainRelations);

            emit('highlight-knowledge', {
              entities: lastMessage.entities,
              relations: lastMessage.relations,
              question: trimmedQuestion,
            });
            emitGraphHighlight(apiEntities, explainRelations);
          } else {
            lastMessage.chunks = meta.chunks || [];
            lastMessage.communities_used = meta.communities_used;
            delete messageGraphMap[lastMessage.id];
          }
        },
        onExpertStage(stageEvent) {
          if (!lastMessage || lastMessage.role !== 'assistant') return;
          hasExpertStageEvent = true;
          updateExpertStage(lastMessage, {
            key: stageEvent.stage_key,
            title: stageEvent.title,
            status: stageEvent.status,
            detail: stageEvent.detail,
          });
          syncExpertLoadingText(lastMessage);
        },
        onToken(token) {
          if (!lastMessage || lastMessage.role !== 'assistant') return;
          lastMessage.content += token;
          scrollToBottom();
        },
        onFollowUpQuestions(questions: FollowUpQuestion[]) {
          if (!lastMessage || lastMessage.role !== 'assistant') return;
          lastMessage.followUpQuestions = questions;
        },
        onDone() {
          if (lastMessage && lastMessage.role === 'assistant') {
            lastMessage.loading = false;
            if (!hasExpertStageEvent) {
              lastMessage.expertStages = [];
            }
            if (!lastMessage.content) lastMessage.content = '未能生成回答';
          }
          scrollToBottom();
        },
        onError(err) {
          if (lastMessage && lastMessage.role === 'assistant') {
            lastMessage.loading = false;
            if (!hasExpertStageEvent) {
              lastMessage.expertStages = [];
            }
            lastMessage.error = err;
            lastMessage.content = `抱歉，搜索过程中出现错误：${err}。请检查后端服务是否正常运行。`;
            delete messageGraphMap[lastMessage.id];
          }
        },
      },
      currentSessionId.value,
      undefined,
      activeDatabase,
      undefined,
      selectedCharacter.value?.key,
      expertMode.value,
      displayContent,
      options.patientIntake,
    );
  } catch (error: any) {
    console.error('GraphRAG search failed:', error);

    const lastMessage = messages.value[messages.value.length - 1];
    if (lastMessage && lastMessage.role === 'assistant') {
      lastMessage.loading = false;
      lastMessage.expertStages = [];
      lastMessage.error = error.message || '请求失败';
      lastMessage.content = `抱歉，搜索过程中出现错误：${error.message || '未知错误'}。请检查后端服务是否正常运行。`;
      delete messageGraphMap[lastMessage.id];
    }
  } finally {
    clearInterval(loadingInterval);
    isLoading.value = false;
    await scrollToBottom();
  }
}

async function handleSend() {
  await sendQuestion(inputText.value.trim());
}

function openPatientIntake() {
  if (isLoading.value) {
    ElMessage.warning('当前回答仍在生成，请稍后再发起患者定位问诊');
    return;
  }
  intakeDialogVisible.value = true;
}

async function handlePatientIntakeSubmit(payload: PatientIntakeSubmitPayload) {
  const patientIntake: PatientIntakeStreamPayload = {
    source_label: payload.sourceLabel,
    structured_summary: payload.structuredSummary,
    question_prompt: payload.questionPrompt,
    attachment_summaries: payload.attachmentSummaries,
  };

  await sendQuestion(payload.questionPrompt, {
    displayContent: payload.displayQuestion,
    sourceLabel: payload.sourceLabel,
    patientIntake,
  });
}
// 点击实体
function handleEntityClick(entity: EntityInfo) {
  emit('selectEntity', entity);
}

// 追问补充提交
function handleFollowUpSubmit(message: KgChatMessage, answers: Record<string, string>) {
  const lines = Object.entries(answers)
    .filter(([_, v]) => v.trim())
    .map(([key, value]) => {
      const q = message.followUpQuestions?.find((q) => q.key === key);
      return `${q?.label || key}：${value}`;
    });
  if (!lines.length) return;

  const answersText = lines.join('\n');
  const supplementQuestion =
    `根据我之前的问题，补充以下信息：\n${answersText}\n\n请基于这些补充信息，结合之前的分析，重新给出更精准的分析和建议。`;

  message.followUpQuestions = []; // 隐藏面板
  sendQuestion(supplementQuestion, {
    displayContent: `补充信息：${lines.map((l) => l.split('：')[0]).join('、')}`,
    sourceLabel: message.sourceLabel,
    patientIntake: message.patientIntake,
  });
}

// 高亮所有实体
function handleHighlightEntities(entities: EntityInfo[]) {
  emit('highlightEntities', entities);
}

async function copyMessageContent(content: string) {
  const text = content.trim();
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制回答');
  } catch (error) {
    console.error('Failed to copy answer:', error);
    ElMessage.error('复制失败');
  }
}

async function retryMessage(messageId: string) {
  if (isLoading.value) return;

  const currentIndex = messages.value.findIndex((msg) => msg.id === messageId);
  if (currentIndex <= 0) return;

  const previousUserIndex = messages.value
    .slice(0, currentIndex)
    .map((msg, index) => ({ msg, index }))
    .reverse()
    .find(({ msg }) => msg.role === 'user' && msg.content?.trim())?.index;

  if (previousUserIndex == null) return;

  const previousUserMessage = messages.value[previousUserIndex];

  if (!previousUserMessage) return;

  await sendQuestion(
    previousUserMessage.apiContent || previousUserMessage.content,
    {
      displayContent: previousUserMessage.content,
      sourceLabel: previousUserMessage.sourceLabel,
      historyEndIndex: previousUserIndex,
      patientIntake: previousUserMessage.patientIntake,
    },
  );
}

// 键盘事件
function handleKeydown(event: Event | KeyboardEvent) {
  const keyEvent = event as KeyboardEvent;
  if (keyEvent.key === 'Enter' && !keyEvent.shiftKey) {
    event.preventDefault();
    handleSend();
  }
}

// 获取策略标签颜色
function getStrategyColorClass(strategy: SearchStrategy | undefined): string {
  switch (normalizeVisibleStrategy(strategy)) {
    case 'global': {
      return 'text-amber-600 dark:text-yellow-400';
    }
    case 'local': {
      return 'text-green-600 dark:text-green-400';
    }
    default: {
      return 'text-gray-500 dark:text-gray-400';
    }
  }
}

// 获取策略显示名称
function getStrategyLabel(strategy: SearchStrategy | undefined): string {
  switch (normalizeVisibleStrategy(strategy)) {
    case 'auto': {
      return 'Auto';
    }
    case 'global': {
      return 'Global';
    }
    case 'local': {
      return 'Local';
    }
    default: {
      return '';
    }
  }
}

// 添加欢迎消息
function addWelcomeMessage() {
  let statsInfo = '';
  if (graphStatsInfo.value) {
    statsInfo = `\n\n**图谱状态**: ${graphStatsInfo.value.nodes || 0} 个节点, ${graphStatsInfo.value.edges || 0} 条边`;
    if (graphStatsInfo.value.communities) {
      statsInfo += `, ${graphStatsInfo.value.communities} 个社区`;
    }
  }

  messages.value.push({
    id: generateId(),
    role: 'assistant',
    content: `你好！今天有什么我可以帮你的吗？

我可以结合知识图谱中的实体、关系和原文片段来回答你的问题。${statsInfo}`,
    timestamp: new Date(),
    isWelcome: true,
  });
}

// 重试连接
async function retryConnection() {
  await checkServiceStatus();
  if (serviceStatus.value === 'online') {
    ElMessage.success('服务连接成功！');
  }
}

// 初始化
onMounted(async () => {
  await loadSessions();
  await checkServiceStatus();
  await loadDatabases();
  await loadCharacters();
  addWelcomeMessage();

  // 点击外部关闭角色选择弹窗
  document.addEventListener('click', handleDocClick);
});

function handleDocClick(e: MouseEvent) {
  if (showCharacterPicker.value) {
    const target = e.target as HTMLElement;
    if (
      !target.closest('.char-pick-btn') &&
      !target.closest('.char-picker-popup')
    ) {
      showCharacterPicker.value = false;
    }
  }
}

onUnmounted(() => {
  document.removeEventListener('click', handleDocClick);
});
</script>

<style scoped>
/* ═══ Theme tokens ════════════════════════════════════════════════════════ */
:global(:root) {
  --kc-win-bg:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.04), transparent 24%),
    linear-gradient(180deg, #f7f8fa, #f0f2f4 68%);
  --kc-win-color: #1e293b;
  --kc-sidebar-bg: linear-gradient(180deg, rgba(248, 249, 251, 0.98), rgba(244, 245, 248, 0.98));
  --kc-sidebar-shadow: inset -1px 0 0 rgba(0, 0, 0, 0.06);
  --kc-sidebar-border: rgba(0, 0, 0, 0.1);
  --kc-main-bg: linear-gradient(180deg, rgba(247, 248, 250, 0.92), #f5f6f8);
  --kc-handle-bg: linear-gradient(180deg, rgba(240, 242, 246, 0.96), rgba(244, 245, 248, 0.96));
  --kc-handle-border: rgba(0, 0, 0, 0.12);
  --kc-handle-text: #475569;
  --kc-user-bubble-bg: linear-gradient(180deg, rgba(226, 232, 240, 0.96), rgba(215, 222, 233, 0.98));
  --kc-user-bubble-border: rgba(0, 0, 0, 0.08);
  --kc-user-bubble-text: #1e293b;
  --kc-intake-card-border: rgba(14, 165, 233, 0.16);
  --kc-intake-card-bg: linear-gradient(180deg, rgba(244, 249, 252, 0.96), rgba(236, 244, 250, 0.98));
  --kc-intake-card-title: #0f172a;
  --kc-intake-card-text: #334155;
  --kc-intake-card-muted: #64748b;
  --kc-intake-card-pill-bg: rgba(14, 165, 233, 0.1);
  --kc-intake-card-pill-text: #0369a1;
  --kc-intake-card-divider: rgba(100, 116, 139, 0.14);
  --kc-intake-card-attachment-bg: rgba(255, 255, 255, 0.58);
  --kc-assistant-label-color: #475569;
  --kc-graph-card-border: rgba(100, 116, 139, 0.2);
  --kc-graph-card-bg: linear-gradient(180deg, rgba(245, 247, 250, 0.95), rgba(238, 242, 248, 0.98));
  --kc-graph-card-shadow: inset 0 1px 0 rgba(0, 0, 0, 0.03);
  --kc-graph-header-border: rgba(100, 116, 139, 0.15);
  --kc-graph-title-color: #1e293b;
  --kc-graph-meta-color: #64748b;
  --kc-expert-card-border: rgba(14, 165, 233, 0.18);
  --kc-expert-card-bg: linear-gradient(180deg, rgba(241, 245, 249, 0.96), rgba(235, 241, 247, 0.98));
  --kc-expert-title: #0f172a;
  --kc-expert-item-border: rgba(100, 116, 139, 0.14);
  --kc-expert-item-bg: rgba(255, 255, 255, 0.55);
  --kc-expert-name: #334155;
  --kc-expert-detail: #64748b;
  --kc-expert-pending: #cbd5e1;
  --kc-expert-running: #0ea5e9;
  --kc-expert-done: #10b981;
  --kc-expert-error: #ef4444;
  --kc-action-border: rgba(0, 0, 0, 0.08);
  --kc-action-bg: rgba(0, 0, 0, 0.02);
  --kc-action-color: #64748b;
  --kc-action-border-hover: rgba(0, 0, 0, 0.15);
  --kc-action-bg-hover: rgba(0, 0, 0, 0.05);
  --kc-action-color-hover: #1e293b;
  --kc-chat-input-bg: linear-gradient(180deg, rgba(245, 246, 248, 0), rgba(245, 246, 248, 0.9) 26%, #f5f6f8);
  --kc-chat-input-border: rgba(0, 0, 0, 0.08);
  --kc-shell-border: rgba(0, 0, 0, 0.1);
  --kc-shell-bg: rgba(255, 255, 255, 0.96);
  --kc-shell-shadow: 0 16px 36px rgba(0, 0, 0, 0.08);
  --kc-md-color: #1e293b;
  --kc-md-heading-color: #0f172a;
  --kc-code-bg: rgba(234, 236, 240, 0.9);
  --kc-code-color: #1e293b;
  --kc-pre-bg: rgba(225, 229, 236, 0.96);
  --kc-pre-border: rgba(0, 0, 0, 0.08);
  --kc-strong-color: #0f172a;
  --kc-link-color: #2563eb;
  --kc-input-color: #1e293b;
  --kc-input-placeholder: #94a3b8;
  --kc-select-wrapper-bg: rgba(240, 242, 246, 0.66);
  --kc-select-wrapper-shadow: inset 0 0 0 1px rgba(100, 116, 139, 0.4) !important;
  --kc-select-color: #374151;
  --kc-dropdown-bg: #f8f9fb;
  --kc-dropdown-border: #cbd5e1;
  --kc-dropdown-item-color: #1e293b;
  --kc-dropdown-item-hover-bg: rgba(59, 130, 246, 0.08);
  --kc-dropdown-item-hover-color: #1e293b;
  --kc-panel-bg: rgba(245, 247, 250, 0.9);
  --kc-panel-border: rgba(0, 0, 0, 0.1);
  --kc-panel-btn-text: #64748b;
  --kc-panel-btn-hover: rgba(0, 0, 0, 0.04);
  --kc-panel-inner-border: rgba(0, 0, 0, 0.08);
  --kc-chip-border: rgba(0, 0, 0, 0.12);
  --kc-chip-bg: rgba(240, 242, 246, 0.8);
  --kc-chip-text: #374151;
  --kc-chip-type-text: #94a3b8;
  --kc-mode-pill-bg: rgba(14, 165, 233, 0.1);
  --kc-mode-pill-text: #0369a1;
  --kc-mode-option-bg: rgba(241, 245, 249, 0.9);
  --kc-mode-option-border: rgba(148, 163, 184, 0.22);
  --kc-mode-option-text: #475569;
  --kc-mode-option-active-bg: rgba(14, 165, 233, 0.12);
  --kc-mode-option-active-border: rgba(14, 165, 233, 0.28);
  --kc-mode-option-active-text: #0369a1;
  --kc-rel-row-bg: rgba(0, 0, 0, 0.03);
  --kc-rel-src-text: #1e293b;
  --kc-rel-text: #64748b;
  --kc-rel-badge-border: rgba(59, 130, 246, 0.25);
  --kc-rel-badge-bg: rgba(59, 130, 246, 0.06);
  --kc-rel-badge-text: #1d4ed8;
  --kc-chunk-border: rgba(0, 0, 0, 0.1);
  --kc-chunk-bg: rgba(0, 0, 0, 0.02);
  --kc-chunk-text: #475569;
  --kc-chunk-divider: rgba(0, 0, 0, 0.06);
  --kc-meta-badge-border: rgba(0, 0, 0, 0.1);
  --kc-meta-badge-bg: rgba(0, 0, 0, 0.025);
  --kc-meta-badge-text: #64748b;
  --kc-ft-divider: rgba(0, 0, 0, 0.06);
  --kc-session-icon-border: rgba(0, 0, 0, 0.12);
  --kc-session-icon-bg: rgba(0, 0, 0, 0.025);
  --kc-session-icon-text: #64748b;
  --kc-session-border: rgba(0, 0, 0, 0.08);
  --kc-session-hover-border: rgba(0, 0, 0, 0.16);
  --kc-session-hover-bg: rgba(0, 0, 0, 0.04);
  --kc-session-active-border: rgba(6, 182, 212, 0.3);
  --kc-session-active-bg: rgba(6, 182, 212, 0.06);
  --kc-session-text: #374151;
  --kc-session-delete-text: #94a3b8;
  --kc-section-label: #94a3b8;
  --kc-status-bg: rgba(239, 68, 68, 0.08);
  --kc-status-border: rgba(239, 68, 68, 0.15);
  --kc-retry-bg: rgba(239, 68, 68, 0.1);
  --kc-retry-text: #dc2626;
  --kc-retry-hover: rgba(239, 68, 68, 0.15);
}

:global(.dark) {
  --kc-win-bg: linear-gradient(180deg, #1e2025, #1b1d22);
  --kc-win-color: #dbe7f3;
  --kc-sidebar-bg: linear-gradient(180deg, rgba(27, 29, 34, 0.98), rgba(24, 26, 31, 0.96));
  --kc-sidebar-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.04);
  --kc-sidebar-border: rgba(255, 255, 255, 0.08);
  --kc-main-bg: linear-gradient(180deg, rgba(28, 30, 35, 0.92), rgba(25, 27, 32, 1));
  --kc-handle-bg: linear-gradient(180deg, rgba(32, 34, 40, 0.96), rgba(27, 29, 34, 0.96));
  --kc-handle-border: rgba(6, 182, 212, 0.15);
  --kc-handle-text: #a5f3fc;
  --kc-user-bubble-bg: linear-gradient(180deg, rgba(50, 51, 56, 0.96), rgba(42, 43, 47, 0.98));
  --kc-user-bubble-border: rgba(255, 255, 255, 0.08);
  --kc-user-bubble-text: #f1f5f9;
  --kc-intake-card-border: rgba(56, 189, 248, 0.14);
  --kc-intake-card-bg: linear-gradient(180deg, rgba(16, 24, 33, 0.9), rgba(13, 20, 28, 0.94));
  --kc-intake-card-title: #e2e8f0;
  --kc-intake-card-text: #dbe7f3;
  --kc-intake-card-muted: #94a3b8;
  --kc-intake-card-pill-bg: rgba(14, 165, 233, 0.14);
  --kc-intake-card-pill-text: #7dd3fc;
  --kc-intake-card-divider: rgba(148, 163, 184, 0.12);
  --kc-intake-card-attachment-bg: rgba(15, 23, 42, 0.34);
  --kc-assistant-label-color: #d7dbdf;
  --kc-graph-card-border: rgba(148, 163, 184, 0.16);
  --kc-graph-card-bg: linear-gradient(180deg, rgba(20, 25, 34, 0.92), rgba(14, 18, 24, 0.96));
  --kc-graph-card-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  --kc-graph-header-border: rgba(148, 163, 184, 0.12);
  --kc-graph-title-color: #e2e8f0;
  --kc-graph-meta-color: #94a3b8;
  --kc-expert-card-border: rgba(14, 165, 233, 0.16);
  --kc-expert-card-bg: linear-gradient(180deg, rgba(16, 22, 30, 0.86), rgba(12, 18, 26, 0.92));
  --kc-expert-title: #e2e8f0;
  --kc-expert-item-border: rgba(148, 163, 184, 0.1);
  --kc-expert-item-bg: rgba(15, 23, 42, 0.46);
  --kc-expert-name: #dbe7f3;
  --kc-expert-detail: #94a3b8;
  --kc-expert-pending: #475569;
  --kc-expert-running: #38bdf8;
  --kc-expert-done: #34d399;
  --kc-expert-error: #f87171;
  --kc-action-border: rgba(255, 255, 255, 0.06);
  --kc-action-bg: rgba(255, 255, 255, 0.02);
  --kc-action-color: #9aa0a6;
  --kc-action-border-hover: rgba(255, 255, 255, 0.1);
  --kc-action-bg-hover: rgba(255, 255, 255, 0.05);
  --kc-action-color-hover: #e8eaed;
  --kc-chat-input-bg: linear-gradient(180deg, rgba(25, 27, 32, 0), rgba(25, 27, 32, 0.9) 26%, rgba(25, 27, 32, 1));
  --kc-chat-input-border: rgba(255, 255, 255, 0.05);
  --kc-shell-border: rgba(255, 255, 255, 0.06);
  --kc-shell-bg: rgba(35, 37, 43, 0.95);
  --kc-shell-shadow: 0 16px 36px rgba(0, 0, 0, 0.28);
  --kc-md-color: #eceff1;
  --kc-md-heading-color: #f8fafc;
  --kc-code-bg: rgba(36, 38, 44, 0.9);
  --kc-code-color: #e8eaed;
  --kc-pre-bg: rgba(32, 34, 40, 0.96);
  --kc-pre-border: rgba(255, 255, 255, 0.06);
  --kc-strong-color: #ffffff;
  --kc-link-color: #8ab4f8;
  --kc-input-color: #f1f3f4;
  --kc-input-placeholder: #b0b4b8;
  --kc-select-wrapper-bg: rgba(15, 23, 42, 0.66);
  --kc-select-wrapper-shadow: inset 0 0 0 1px rgba(51, 65, 85, 0.78) !important;
  --kc-select-color: #cbd5e1;
  --kc-dropdown-bg: #0f172a;
  --kc-dropdown-border: #334155;
  --kc-dropdown-item-color: #dbe7f3;
  --kc-dropdown-item-hover-bg: rgba(8, 47, 73, 0.45);
  --kc-dropdown-item-hover-color: #f8fbff;
  --kc-panel-bg: rgba(15, 18, 24, 0.3);
  --kc-panel-border: rgba(255, 255, 255, 0.07);
  --kc-panel-btn-text: #94a3b8;
  --kc-panel-btn-hover: rgba(255, 255, 255, 0.04);
  --kc-panel-inner-border: rgba(255, 255, 255, 0.05);
  --kc-chip-border: rgba(255, 255, 255, 0.1);
  --kc-chip-bg: rgba(15, 18, 24, 0.8);
  --kc-chip-text: #e2e8f0;
  --kc-chip-type-text: #64748b;
  --kc-mode-pill-bg: rgba(14, 165, 233, 0.16);
  --kc-mode-pill-text: #7dd3fc;
  --kc-mode-option-bg: rgba(15, 23, 42, 0.82);
  --kc-mode-option-border: rgba(51, 65, 85, 0.65);
  --kc-mode-option-text: #94a3b8;
  --kc-mode-option-active-bg: rgba(14, 165, 233, 0.16);
  --kc-mode-option-active-border: rgba(14, 165, 233, 0.26);
  --kc-mode-option-active-text: #e0f2fe;
  --kc-rel-row-bg: rgba(15, 18, 24, 0.35);
  --kc-rel-src-text: #e2e8f0;
  --kc-rel-text: #94a3b8;
  --kc-rel-badge-border: rgba(14, 165, 233, 0.2);
  --kc-rel-badge-bg: rgba(14, 165, 233, 0.07);
  --kc-rel-badge-text: #7dd3fc;
  --kc-chunk-border: rgba(255, 255, 255, 0.07);
  --kc-chunk-bg: rgba(15, 18, 24, 0.45);
  --kc-chunk-text: #94a3b8;
  --kc-chunk-divider: rgba(255, 255, 255, 0.07);
  --kc-meta-badge-border: rgba(255, 255, 255, 0.07);
  --kc-meta-badge-bg: rgba(15, 18, 24, 0.45);
  --kc-meta-badge-text: #94a3b8;
  --kc-ft-divider: rgba(255, 255, 255, 0.06);
  --kc-session-icon-border: rgba(255, 255, 255, 0.08);
  --kc-session-icon-bg: rgba(15, 18, 24, 0.85);
  --kc-session-icon-text: #94a3b8;
  --kc-session-border: rgba(15, 18, 24, 0.4);
  --kc-session-hover-border: rgba(255, 255, 255, 0.1);
  --kc-session-hover-bg: rgba(255, 255, 255, 0.04);
  --kc-session-active-border: rgba(34, 211, 238, 0.25);
  --kc-session-active-bg: rgba(8, 47, 73, 0.2);
  --kc-session-text: #cbd5e1;
  --kc-session-delete-text: #64748b;
  --kc-section-label: #64748b;
  --kc-status-bg: rgba(239, 68, 68, 0.1);
  --kc-status-border: rgba(239, 68, 68, 0.2);
  --kc-retry-bg: rgba(239, 68, 68, 0.2);
  --kc-retry-text: #fca5a5;
  --kc-retry-hover: rgba(239, 68, 68, 0.28);
}

/* ═══ Component styles ════════════════════════════════════════════════════ */
.kg-chat-window {
  min-width: 320px;
  color: var(--kc-win-color);
  background: var(--kc-win-bg);
}

.kg-chat-sidebar {
  background: var(--kc-sidebar-bg);
  box-shadow: var(--kc-sidebar-shadow);
  border-right-color: var(--kc-sidebar-border) !important;
}

.kg-chat-sidebar .border-b {
  border-bottom-color: var(--kc-sidebar-border) !important;
}

.kg-chat-main {
  background: var(--kc-main-bg);
}

.chat-main-inner {
  width: min(80%, 920px);
  margin: 0 auto;
}

.sidebar-handle {
  backdrop-filter: blur(12px);
  background-image: var(--kc-handle-bg);
  border-color: var(--kc-handle-border) !important;
  color: var(--kc-handle-text) !important;
}

.sidebar-handle:hover {
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
}

.user-bubble {
  max-width: min(540px, 62vw);
  border: 1px solid var(--kc-user-bubble-border);
  border-radius: 14px 4px 14px 14px;
  background: var(--kc-user-bubble-bg);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  color: var(--kc-user-bubble-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.message-source-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(14, 165, 233, 0.18);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: #0369a1;
  background: rgba(224, 242, 254, 0.82);
}

.user-source-badge {
  align-self: flex-end;
}

.patient-intake-card {
  margin-top: 12px;
  width: min(540px, 62vw);
  overflow: hidden;
  border: 1px solid var(--kc-intake-card-border);
  border-radius: 18px;
  background: var(--kc-intake-card-bg);
}

.patient-intake-card__header {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  text-align: left;
}

.patient-intake-card__header-main {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.patient-intake-card__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--kc-intake-card-title);
}

.patient-intake-card__meta {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  color: var(--kc-intake-card-pill-text);
  background: var(--kc-intake-card-pill-bg);
}

.patient-intake-card__arrow {
  flex-shrink: 0;
  color: var(--kc-intake-card-muted);
}

.patient-intake-card__preview {
  padding: 0 14px 14px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--kc-intake-card-text);
}

.patient-intake-card__body {
  border-top: 1px solid var(--kc-intake-card-divider);
  padding: 14px;
}

.patient-intake-card__body :deep(.markdown-body) {
  color: var(--kc-intake-card-text);
}

.patient-intake-card__body :deep(.markdown-body strong) {
  color: var(--kc-intake-card-title);
}

.patient-intake-attachments {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.patient-intake-attachments__title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--kc-intake-card-muted);
}

.patient-intake-attachments__list {
  display: grid;
  gap: 8px;
}

.patient-intake-attachment {
  border: 1px solid var(--kc-intake-card-divider);
  border-radius: 14px;
  padding: 10px 12px;
  background: var(--kc-intake-card-attachment-bg);
}

.patient-intake-attachment__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.patient-intake-attachment__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  color: var(--kc-intake-card-title);
}

.patient-intake-attachment__tag {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--kc-intake-card-muted);
}

.patient-intake-attachment__summary {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--kc-intake-card-text);
}

.assistant-message {
  max-width: min(100%, 840px);
}

.assistant-label {
  margin-bottom: 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--kc-assistant-label-color);
  font-size: 11px;
  font-weight: 600;
}

.assistant-label__spark {
  width: 8px;
  height: 8px;
  border-radius: 3px;
  transform: rotate(45deg);
  background: linear-gradient(135deg, #6ea8ff, #3b82f6);
  box-shadow: 0 0 18px rgba(59, 130, 246, 0.35);
}

.assistant-bubble {
  padding: 0;
  background: transparent;
  border-color: transparent;
  box-shadow: none;
}

.welcome-intake-action {
  display: grid;
  gap: 10px;
}

.welcome-intake-action__btn {
  width: fit-content;
  border: 1px solid rgba(14, 165, 233, 0.2);
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 700;
  color: #0369a1;
  background: linear-gradient(135deg, rgba(224, 242, 254, 0.94), rgba(240, 249, 255, 0.98));
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.welcome-intake-action__btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(14, 165, 233, 0.14);
}

.welcome-intake-action__btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.welcome-intake-action__hint {
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.expert-stage-card {
  overflow: hidden;
  border: 1px solid var(--kc-expert-card-border);
  border-radius: 16px;
  background: var(--kc-expert-card-bg);
  padding: 12px;
}

.expert-stage-card__title {
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--kc-expert-title);
}

.expert-stage-list {
  display: grid;
  gap: 8px;
}

.expert-stage-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border: 1px solid var(--kc-expert-item-border);
  border-radius: 12px;
  background: var(--kc-expert-item-bg);
  padding: 10px 12px;
}

.expert-stage-dot {
  margin-top: 5px;
  height: 8px;
  width: 8px;
  flex-shrink: 0;
  border-radius: 999px;
  background: var(--kc-expert-pending);
}

.expert-stage-dot.is-running {
  background: var(--kc-expert-running);
  box-shadow: 0 0 0 4px rgba(14, 165, 233, 0.14);
}

.expert-stage-dot.is-done {
  background: var(--kc-expert-done);
}

.expert-stage-dot.is-error {
  background: var(--kc-expert-error);
}

.expert-stage-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--kc-expert-name);
}

.expert-stage-detail {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--kc-expert-detail);
}

.expert-stage-detail :deep(p:first-child) {
  margin-top: 0;
}

.expert-stage-detail :deep(p:last-child) {
  margin-bottom: 0;
}

.expert-stage-detail :deep(table) {
  width: 100%;
}

.inline-graph-card {
  margin-top: 12px;
  overflow: hidden;
  border: 1px solid var(--kc-graph-card-border);
  border-radius: 16px;
  background: var(--kc-graph-card-bg);
  box-shadow: var(--kc-graph-card-shadow);
}

.inline-graph-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--kc-graph-header-border);
}

.inline-graph-card__title {
  font-size: 11px;
  font-weight: 600;
  color: var(--kc-graph-title-color);
}

.inline-graph-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: var(--kc-graph-meta-color);
}

.inline-graph-card__body {
  height: 420px;
  min-height: 420px;
}

.assistant-actions {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  transform: translateY(-2px);
}

.assistant-action {
  display: inline-flex;
  height: 26px;
  width: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid var(--kc-action-border);
  background: var(--kc-action-bg);
  color: var(--kc-action-color);
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease;
}

.assistant-action:hover {
  border-color: var(--kc-action-border-hover);
  background: var(--kc-action-bg-hover);
  color: var(--kc-action-color-hover);
}

.chat-input {
  border-top-color: var(--kc-chat-input-border) !important;
  background: var(--kc-chat-input-bg);
}

.input-shell {
  border: 1px solid var(--kc-shell-border);
  border-radius: 28px;
  background: var(--kc-shell-bg);
  box-shadow: var(--kc-shell-shadow);
}

.send-button {
  height: 32px;
  width: 32px;
  border-radius: 999px;
  background-image: linear-gradient(135deg, rgba(76, 125, 255, 0.96), rgba(59, 130, 246, 0.92));
}

/* ─── Character picker ───────────────────────────────────────────────────── */
.char-pick-btn {
  border: 1px solid var(--kc-chip-border);
  background: var(--kc-chip-bg);
  color: var(--kc-chip-text);
  cursor: pointer;
  white-space: nowrap;
}

.char-pick-btn:hover {
  border-color: var(--kc-action-border-hover);
  background: var(--kc-action-bg-hover);
}

.char-pick-active {
  border-color: rgba(14, 165, 233, 0.35);
  background: rgba(14, 165, 233, 0.08);
}

.char-mode-pill {
  border-radius: 999px;
  background: var(--kc-mode-pill-bg);
  color: var(--kc-mode-pill-text);
  padding: 1px 6px;
  font-size: 10px;
  line-height: 1.4;
}

.char-picker-popup {
  background: var(--kc-dropdown-bg);
  border-color: var(--kc-dropdown-border);
  max-height: 260px;
  overflow-y: auto;
}

.char-mode-option {
  border: 1px solid var(--kc-mode-option-border);
  background: var(--kc-mode-option-bg);
  color: var(--kc-mode-option-text);
}

.char-mode-option:hover {
  color: var(--kc-dropdown-item-hover-color);
}

.char-mode-option-active {
  border-color: var(--kc-mode-option-active-border);
  background: var(--kc-mode-option-active-bg);
  color: var(--kc-mode-option-active-text);
}

.char-picker-item {
  color: var(--kc-dropdown-item-color);
}

.char-picker-item:hover {
  background: var(--kc-dropdown-item-hover-bg);
  color: var(--kc-dropdown-item-hover-color);
}

.char-picker-active {
  background: rgba(14, 165, 233, 0.1) !important;
  color: var(--kc-dropdown-item-hover-color);
}

/* fade-up transition */
.fade-up-enter-active,
.fade-up-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.fade-up-enter-from,
.fade-up-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@media (max-width: 1280px) {
  .chat-main-inner {
    width: min(88%, 1080px);
  }
}

@media (max-width: 768px) {
  .chat-main-inner {
    width: 100%;
  }
}

/* ─── Session items ──────────────────────────────────────────────────────── */
.session-item {
  border-color: var(--kc-session-border) !important;
}

.session-item:hover {
  background-color: var(--kc-session-hover-bg) !important;
  border-color: var(--kc-session-hover-border) !important;
}

.session-item.is-active {
  background-color: var(--kc-session-active-bg) !important;
  border-color: var(--kc-session-active-border) !important;
}

.session-icon {
  background-color: var(--kc-session-icon-bg) !important;
  border-color: var(--kc-session-icon-border) !important;
  color: var(--kc-session-icon-text) !important;
}

.session-item.is-active .session-icon {
  background-color: var(--kc-session-active-bg) !important;
  border-color: var(--kc-session-active-border) !important;
  color: #22d3ee !important;
}

.session-name {
  color: var(--kc-session-text) !important;
}

.session-delete {
  color: var(--kc-session-delete-text) !important;
}

/* ─── Offline banner ─────────────────────────────────────────────────────── */
.status-offline-banner {
  background-color: var(--kc-status-bg) !important;
  border-color: var(--kc-status-border) !important;
}

.retry-btn {
  background-color: var(--kc-retry-bg) !important;
  color: var(--kc-retry-text) !important;
}

.retry-btn:hover {
  background-color: var(--kc-retry-hover) !important;
}

/* ─── Collapse panels ─────────────────────────────────────────────────────── */
.collapse-panel {
  border-color: var(--kc-panel-border) !important;
  background-color: var(--kc-panel-bg) !important;
}

.collapse-panel .panel-toggle-btn {
  color: var(--kc-panel-btn-text) !important;
}

.collapse-panel .panel-toggle-btn:hover {
  background-color: var(--kc-panel-btn-hover) !important;
}

.collapse-panel .panel-content {
  border-top-color: var(--kc-panel-inner-border) !important;
}

/* ─── Entity chips ────────────────────────────────────────────────────────── */
.entity-chip {
  border-color: var(--kc-chip-border) !important;
  background-color: var(--kc-chip-bg) !important;
  color: var(--kc-chip-text) !important;
}

.entity-chip:hover {
  background-color: var(--kc-session-hover-bg) !important;
  border-color: var(--kc-session-hover-border) !important;
}

.entity-chip .chip-type {
  color: var(--kc-chip-type-text) !important;
}

/* ─── Relation rows ───────────────────────────────────────────────────────── */
.rel-row {
  background-color: var(--kc-rel-row-bg) !important;
  color: var(--kc-rel-text) !important;
}

.rel-src {
  color: var(--kc-rel-src-text) !important;
}

.rel-badge {
  border-color: var(--kc-rel-badge-border) !important;
  background-color: var(--kc-rel-badge-bg) !important;
  color: var(--kc-rel-badge-text) !important;
}

/* ─── Chunk cards ─────────────────────────────────────────────────────────── */
.chunk-card {
  border-color: var(--kc-chunk-border) !important;
  background-color: var(--kc-chunk-bg) !important;
  color: var(--kc-chunk-text) !important;
}

.chunk-card .chunk-divider {
  border-top-color: var(--kc-chunk-divider) !important;
}

/* ─── Meta badges ─────────────────────────────────────────────────────────── */
.meta-badge {
  border-color: var(--kc-meta-badge-border) !important;
  background-color: var(--kc-meta-badge-bg) !important;
  color: var(--kc-meta-badge-text) !important;
}

/* ─── Footer divider ──────────────────────────────────────────────────────── */
.ft-divider {
  border-top-color: var(--kc-ft-divider) !important;
}

/* ─── Markdown ────────────────────────────────────────────────────────────── */
.markdown-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--kc-md-color);
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  color: var(--kc-md-heading-color);
  font-weight: 700;
  line-height: 1.35;
}

.markdown-body :deep(h1) {
  margin: 0.8em 0 0.55em;
  font-size: 1.5em;
}

.markdown-body :deep(h2) {
  margin: 0.75em 0 0.5em;
  font-size: 1.28em;
}

.markdown-body :deep(h3) {
  margin: 0.7em 0 0.45em;
  font-size: 1.12em;
}

.markdown-body :deep(p) {
  margin: 0.45em 0 0.8em;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.markdown-body :deep(li) {
  margin: 0.25em 0;
}

.markdown-body :deep(code) {
  background-color: var(--kc-code-bg);
  padding: 0.125em 0.375em;
  border-radius: 4px;
  font-size: 0.875em;
  color: var(--kc-code-color);
}

.markdown-body :deep(pre) {
  background-color: var(--kc-pre-bg);
  padding: 1em;
  border-radius: 8px;
  overflow-x: auto;
  border: 1px solid var(--kc-pre-border);
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.markdown-body :deep(strong) {
  font-weight: 600;
  color: var(--kc-strong-color);
}

.markdown-body :deep(a) {
  color: var(--kc-link-color);
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: auto;
  margin: 0.75em 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--kc-pre-border);
  padding: 0.4em 0.8em;
  color: var(--kc-md-color);
}

.markdown-body :deep(th) {
  background-color: var(--kc-code-bg);
  font-weight: 600;
}

/* ─── Inputs ──────────────────────────────────────────────────────────────── */
.custom-input :deep(.el-textarea__inner) {
  min-height: 44px !important;
  background-color: transparent;
  border: none;
  border-radius: 20px;
  padding: 12px 52px 10px 14px;
  color: var(--kc-input-color);
  box-shadow: none;
  resize: none;
  transition: all 0.2s;
}

.custom-input :deep(.el-textarea__inner::-webkit-resizer) {
  display: none;
}

.custom-input :deep(.el-textarea__inner:focus) {
  background-color: transparent;
  border-color: transparent;
  box-shadow: none;
}

.custom-input :deep(.el-textarea__inner::placeholder) {
  color: var(--kc-input-placeholder);
}

/* ─── Selectors ───────────────────────────────────────────────────────────── */
.strategy-select :deep(.el-input__wrapper) {
  background-color: var(--kc-select-wrapper-bg);
  border-radius: 0.75rem;
  box-shadow: var(--kc-select-wrapper-shadow);
  min-height: 28px;
  padding: 0 8px;
}

.strategy-select :deep(.el-input__inner) {
  color: var(--kc-select-color);
  font-size: 11px;
  font-weight: 500;
}

.strategy-select :deep(.el-input__suffix) {
  display: none;
}

.doc-select :deep(.el-input__wrapper) {
  background-color: var(--kc-select-wrapper-bg);
  border-radius: 0.75rem;
  box-shadow: var(--kc-select-wrapper-shadow);
  min-height: 28px;
  padding: 0 8px;
}

.doc-select :deep(.el-input__inner) {
  color: var(--kc-select-color);
  font-size: 11px;
  font-weight: 500;
}

.doc-select :deep(.el-input__suffix) {
  display: none;
}
</style>

<style>
/* 选择器下拉框 - 全局样式确保 teleported 时生效 */
.strategy-select-dropdown,
.doc-select-dropdown {
  background: var(--kc-dropdown-bg) !important;
  border: 1px solid var(--kc-dropdown-border) !important;
  padding: 4px !important;
  z-index: 9999 !important;
}

.doc-select-dropdown {
  max-height: 300px;
}

.strategy-select-dropdown .el-select-dropdown__item,
.doc-select-dropdown .el-select-dropdown__item {
  color: var(--kc-dropdown-item-color);
  border-radius: 4px;
  margin-bottom: 2px;
  height: auto;
  padding: 8px 12px;
}

.strategy-select-dropdown .el-select-dropdown__item.hover,
.strategy-select-dropdown .el-select-dropdown__item.is-hovering,
.strategy-select-dropdown .el-select-dropdown__item.selected,
.doc-select-dropdown .el-select-dropdown__item.hover,
.doc-select-dropdown .el-select-dropdown__item.is-hovering,
.doc-select-dropdown .el-select-dropdown__item.selected {
  background: var(--kc-dropdown-item-hover-bg);
  color: var(--kc-dropdown-item-hover-color);
}

/* Dark mode overrides - scoped to .kg-chat-window to prevent leaking to framework */
.dark .kg-chat-window .message-source-badge {
  border-color: rgba(56, 189, 248, 0.22);
  color: #7dd3fc;
  background: rgba(8, 47, 73, 0.55);
}

.dark .kg-chat-window .welcome-intake-action__btn {
  border-color: rgba(56, 189, 248, 0.22);
  color: #bae6fd;
  background: linear-gradient(135deg, rgba(8, 47, 73, 0.72), rgba(15, 23, 42, 0.88));
}

.dark .kg-chat-window .welcome-intake-action__hint {
  color: #94a3b8;
}
</style>
