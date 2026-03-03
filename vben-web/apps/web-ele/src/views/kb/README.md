# 知识库 (KB) 前端模块说明

## 📁 目录结构

```
vben-web/apps/web-ele/src/views/kb/
├── chat/                          # 知识库对话模块
│   ├── index.vue                  # 主对话页面（会话列表 + 聊天窗口）
│   ├── components/
│   │   ├── ChatWindow.vue         # 聊天消息区域（流式、RAG 引用展示）
│   │   └── SessionList.vue        # 会话列表侧边栏
│   └── utils/
│       └── api.ts                 # API 类型定义和封装
│
├── management/                    # 知识库管理模块
│   ├── index.vue                  # 知识库列表、CRUD、文档上传
│   └── utils/
│       └── api.ts                 # API hook（模拟）
│
├── character/                     # AI 角色管理模块
│   ├── index.vue                  # 角色列表、CRUD、详情
│   └── utils/
│       └── api.ts                 # API hook（模拟）
│
└── config.ts                      # 路由配置和常量
```

## 🎯 功能概览

### 1. 知识库对话 (`chat/index.vue`)
- **会话管理**
  - 创建新会话（选择角色、设置上下文长度）
  - 列出所有会话
  - 删除会话
  
- **实时聊天**
  - 支持流式响应（SSE）
  - Markdown 渲染（支持代码高亮）
  - RAG 引用展示（得分、相关性等级、来源文件）
  - 文件上传（预留）

- **角色系统**
  - 从后端加载可用角色
  - 实时切换角色
  - 展示角色信息

### 2. 知识库管理 (`management/index.vue`)
- **知识库 CRUD**
  - 创建/编辑/删除知识库
  - 查看知识库统计（文档数、分片数）
  
- **文档管理**
  - 批量上传文档
  - 查看知识库内文档列表
  - 删除文档

### 3. AI 角色管理 (`character/index.vue`)
- **角色 CRUD**
  - 创建/编辑/删除角色
  - 启用/禁用角色
  
- **角色详情**
  - 展示角色所有属性
  - 编辑系统提示词
  - 管理专业领域标签

## 🔌 后端 API 对接清单

所有 API 调用都需要在对应的 `utils/api.ts` 中实现。目前是模拟实现，需要接入真实后端。

### Chat APIs

| 方法 | 端点 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/chat/session/create` | 创建会话 | ⏳ 待实现 |
| GET | `/api/chat/session/{sessionId}` | 获取会话详情 | ⏳ 待实现 |
| GET | `/api/chat/sessions` | 列出所有会话（分页） | ⏳ 待实现 |
| DELETE | `/api/chat/session/{sessionId}` | 删除会话 | ⏳ 待实现 |
| POST | `/api/chat/send` | 发送消息（单轮） | ⏳ 待实现 |
| SSE | `/api/chat/stream` | 流式发送消息 | ⏳ 待实现 |
| GET | `/api/chat/history/{sessionId}` | 获取历史消息（分页） | ⏳ 待实现 |
| POST | `/api/chat/session/{sessionId}/clear` | 清空会话上下文 | ⏳ 待实现 |
| GET | `/api/character/available` | 获取可用角色列表 | ⏳ 待实现 |
| GET | `/api/character/{key}` | 获取角色详情 | ⏳ 待实现 |

### Knowledge Base APIs

| 方法 | 端点 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/kb/list` | 列出知识库（分页） | ⏳ 待实现 |
| GET | `/api/kb/{kbId}` | 获取知识库详情 | ⏳ 待实现 |
| POST | `/api/kb/create` | 创建知识库 | ⏳ 待实现 |
| PUT | `/api/kb/{kbId}` | 更新知识库 | ⏳ 待实现 |
| DELETE | `/api/kb/{kbId}` | 删除知识库 | ⏳ 待实现 |
| POST | `/api/kb/{kbId}/upload` | 上传文档（FormData） | ⏳ 待实现 |
| GET | `/api/kb/{kbId}/documents` | 列出知识库内文档（分页） | ⏳ 待实现 |
| DELETE | `/api/kb/{kbId}/document/{docId}` | 删除知识库内文档 | ⏳ 待实现 |

### Character APIs

| 方法 | 端点 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/character/list` | 列出所有角色 | ⏳ 待实现 |
| GET | `/api/character/{id}` | 获取角色详情 | ⏳ 待实现 |
| POST | `/api/character/create` | 创建角色 | ⏳ 待实现 |
| PUT | `/api/character/{id}` | 更新角色 | ⏳ 待实现 |
| DELETE | `/api/character/{id}` | 删除角色 | ⏳ 待实现 |

## 📝 API 响应格式示例

### Chat Session
```json
{
  "session_id": "uuid-xxx",
  "name": "我的会话",
  "character_key": "student",
  "character_name": "学生",
  "max_context_length": 10,
  "kb_id": 1,
  "user_id": 123,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "message_count": 5
}
```

### Chat Message
```json
{
  "id": "msg-xxx",
  "session_id": "session-xxx",
  "role": "assistant",
  "content": "这是一条消息",
  "sources": [
    {
      "kb_id": 1,
      "text": "引用的文本片段",
      "score": 0.95,
      "metadata": {
        "filename": "document.pdf"
      },
      "citation_id": "ref_1",
      "source_type": "document",
      "relevance_level": "high"
    }
  ],
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Knowledge Base
```json
{
  "id": 1,
  "name": "企业知识库",
  "description": "企业内部文档库",
  "category": "企业",
  "doc_count": 15,
  "chunk_count": 245,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Character
```json
{
  "id": 1,
  "key": "student",
  "name": "学生",
  "product": "学习助手",
  "hobby": "学习",
  "personality": "勤奋好学",
  "expertise": ["学习方法", "知识理解"],
  "system_prompt": "你是一个勤奋的学生...",
  "avatar": "👨‍🎓",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

## 🔧 对接指南

### 1. 实现 Chat API
编辑 `chat/utils/api.ts`：
- 替换模拟的 `getAvailableCharacters()` 为真实后端调用
- 实现 `sendChatMessage()` 和 `sendChatMessageStream()`
- 实现 `getChatHistory()` 等持久化接口

### 2. 实现 Knowledge Base API
编辑 `management/utils/api.ts`：
- 替换 `useKBApi()` 中的模拟实现
- 调用 `/api/kb/*` 端点

### 3. 实现 Character API
编辑 `character/utils/api.ts`：
- 替换 `useCharacterApi()` 中的模拟实现
- 调用 `/api/character/*` 端点

## 🚀 快速开始

1. **启动前端开发服务器**
   ```bash
   cd vben-web
   pnpm install
   pnpm dev
   ```

2. **导航到知识库模块**
   - 对话：`/kb/chat`
   - 知识库管理：`/kb/management`
   - 角色管理：`/kb/character`

3. **对接后端**
   - 确保后端服务运行在 `http://localhost:5000` 或配置的地址
   - 实现上述 API 端点
   - 在各 `api.ts` 文件中调用真实后端

## 📌 注意事项

- 所有 API 调用都应使用项目的 HTTP 工具（如 `axios` wrapper）
- 错误处理已在前端中加入（`ElMessage.error()` 等）
- 流式 API 使用 EventSource（SSE），确保后端支持
- 文件上传使用 FormData，后端需要对应处理
- 所有日期时间使用 ISO 8601 格式

## 🎨 样式约定

- 使用 Tailwind CSS + Element Plus 的混合样式
- 响应式设计，支持移动端
- 深色模式支持通过 CSS 变量 `hsl(var(--xxx))`
- 图标使用 UnoCSS 的 `i-line-md` 图标库

## 📞 支持

如有问题或需要修改，请联系开发团队。
