<template>
  <div class="chat-container">
    <div class="chat-header">
      <h2>智能代码分析聊天</h2>
      <div class="status-indicator">
        <span class="status-dot" :class="{ active: connected }"></span>
        <span>{{ connected ? '已连接' : '连接中...' }}</span>
      </div>
    </div>

    <div class="messages-list" ref="scrollBox">
      <!-- 思考区域（仅在思考中或思考完成但未折叠时显示） -->
      <div v-if="thinking || (thoughts.length > 0 && !thoughtsCollapsed)" class="thought-section"
        :class="{ 'thinking-active': thinking, 'thought-done': !thinking && thoughts.length > 0 }"
      >
        <div class="thought-header" @click="toggleThoughts">
          <span class="thought-icon">{{ thinking ? '🤔' : '💡' }}</span>
          <span class="thought-title">{{ thinking ? 'AI 正在思考...' : '思考过程' }}</span>
          <span class="thought-toggle-btn">
            <el-icon v-if="thinking"><Loading /></el-icon>
            <span v-else>{{ thoughtsCollapsed ? '展开' : '收起' }}</span>
          </span>
        </div>
        <!-- 思考条目列表 -->
        <transition-group name="thought-list" tag="div" class="thought-items">
          <div v-for="(thought, idx) in thoughts" :key="idx" class="thought-item"
            :class="{ 'new-thought': idx === thoughts.length - 1 && thinking }"
          >
            <span class="thought-bullet">✦</span>
            <span class="thought-text">{{ thought }}</span>
          </div>
        </transition-group>
        <div v-if="thinking" class="thinking-dots">
          <span></span><span></span><span></span>
        </div>
      </div>

      <!-- 消息列表 -->
      <transition-group name="message" tag="div">
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role]">
          <div class="avatar">{{ msg.role === 'user' ? 'ME' : 'AI' }}</div>
          <div class="content-wrapper">
            <div class="content" v-html="renderMarkdown(msg.content)"></div>
            <!-- 生成动画（仅对assistant消息且处于思考完成后的生成阶段） -->
            <div v-if="msg.role === 'assistant' && index === messages.length - 1 && generating" class="generate-indicator">
              <span class="generate-bar"><span></span></span>
              <span class="generate-text">生成回答中...</span>
            </div>
            <div v-else-if="msg.role === 'assistant' && index === messages.length - 1 && !generating && !thinking && msg.content && msg.content.length > 0" class="generate-done">
              <span class="done-badge">✓ 生成完成</span>
            </div>
          </div>
        </div>
      </transition-group>
    </div>

    <div class="input-area">
      <el-input
        v-model="inputMsg"
        placeholder="问问这份代码的逻辑..."
        @keyup.enter="sendMessage"
        :disabled="loading"
        clearable
      >
        <template #append>
          <el-button type="primary" @click="sendMessage" :loading="loading" round>
            <el-icon><Promotion /></el-icon>
          </el-button>
        </template>
      </el-input>
      <div class="input-tips" v-if="!loading">按 Enter 发送消息</div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { marked } from 'marked'
import { Promotion, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  repoSlug: {
    type: String,
    default: '',
  },
})

const messages = ref([])
const inputMsg = ref('')
const loading = ref(false)
const scrollBox = ref(null)
const connected = ref(false)

// 思考过程状态
const thinking = ref(false)
const thoughts = ref([])
const thoughtsCollapsed = ref(false)

// 生成状态
const generating = ref(false)

const renderer = new marked.Renderer()
const origLink = renderer.link.bind(renderer)
renderer.link = (href, title, text) => {
  const html = origLink(href, title, text)
  if (href && /^https?:\/\//i.test(href)) {
    return html.replace(/^<a /, '<a target="_blank" rel="noopener noreferrer" ')
  }
  return html
}
marked.use({ renderer })

function linkifyPlainEvidencePaths(text, repoSlug) {
  if (!repoSlug || !text) return text
  const lines = text.split('\n')
  let inEvidence = false
  const out = []
  const slug = repoSlug.replace(/\.git$/i, '')
  for (const line of lines) {
    if (line.trim() === '证据文件:' || /^#{1,6}\s*证据/.test(line.trim())) {
      inEvidence = true
      out.push(line)
      continue
    }
    if (inEvidence && /^\s*#{1,6}\s+\S/.test(line) && !line.includes('证据')) {
      inEvidence = false
    }
    const bullet = line.match(/^\s*-\s+(.+)$/)
    if (inEvidence && bullet) {
      const raw = bullet[1].trim().replace(/^`(.+)`$/, '$1')
      if (raw && !raw.includes('](') && !raw.startsWith('[')) {
        const enc = raw
          .split('/')
          .map((seg) => encodeURIComponent(seg))
          .join('/')
        const url = `https://github.com/${slug}/blob/HEAD/${enc}`
        out.push(line.replace(raw, `[${raw}](${url})`))
        continue
      }
    }
    out.push(line)
  }
  return out.join('\n')
}

const renderMarkdown = (text) => {
  const raw = linkifyPlainEvidencePaths(text || '', props.repoSlug)
  return marked.parse(raw)
}

onMounted(() => {
  const savedMessages = localStorage.getItem('gitchat_messages')
  if (savedMessages) {
    messages.value = JSON.parse(savedMessages)
    scrollToBottom()
  }
  setTimeout(() => {
    connected.value = true
  }, 500)
})

const saveMessages = () => {
  localStorage.setItem('gitchat_messages', JSON.stringify(messages.value))
}

const scrollToBottom = async () => {
  await nextTick()
  if (scrollBox.value) {
    scrollBox.value.scrollTop = scrollBox.value.scrollHeight
  }
}

const toggleThoughts = () => {
  if (!thinking.value) {
    thoughtsCollapsed.value = !thoughtsCollapsed.value
  }
}

const sendMessage = async () => {
  if (!inputMsg.value || loading.value) return

  const userQuery = inputMsg.value
  messages.value.push({ role: 'user', content: userQuery })
  inputMsg.value = ''
  loading.value = true

  // 重置思考状态
  thinking.value = true
  thoughts.value = []
  thoughtsCollapsed.value = false
  generating.value = false

  saveMessages()
  scrollToBottom()

  const aiMsgIndex = messages.value.push({ role: 'assistant', content: '' }) - 1

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userQuery }),
    })

    if (!response.body) return
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ') && line !== 'data: [DONE]') {
          try {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'thought') {
              // 思考过程内容
              thoughts.value.push(data.content)
              scrollToBottom()
            } else if (data.type === 'thought_done') {
              // 思考完成，自动折叠，进入生成阶段
              thinking.value = false
              thoughtsCollapsed.value = true
              generating.value = true
              scrollToBottom()
            } else if (data.type === 'response') {
              // 回答内容（流式）
              messages.value[aiMsgIndex].content += data.content || ''
              saveMessages()
              scrollToBottom()
            }
          } catch (e) {
            // 如果解析失败，当作普通内容处理（兼容旧格式）
            console.warn('SSE parse error, treating as content:', e)
            messages.value[aiMsgIndex].content += line.slice(6) || ''
            saveMessages()
            scrollToBottom()
          }
        }
      }
    }

    // 生成完成
    generating.value = false
    scrollToBottom()
  } catch (error) {
    console.error('Streaming Error:', error)
    messages.value[aiMsgIndex].content = '抱歉，服务器连接失败，请稍后重试。'
    thinking.value = false
    generating.value = false
    saveMessages()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.chat-container {
  width: 100%;
  max-width: 900px;
  height: 700px;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.chat-header {
  background: linear-gradient(135deg, #409eff 0%, #667eea 100%);
  color: white;
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
  transition: all 0.3s ease;
}

.status-dot.active {
  background: #67c23a;
  box-shadow: 0 0 8px #67c23a;
}

.messages-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background-color: #f5f7fa;
}

/* ========== 思考区域样式 ========== */
.thought-section {
  background: linear-gradient(135deg, #fdf6ec 0%, #fef0ef 100%);
  border: 1px solid #fbe2d4;
  border-radius: 12px;
  margin-bottom: 16px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.thought-section.thinking-active {
  border-color: #e6a23c;
  box-shadow: 0 2px 12px rgba(230, 162, 60, 0.15);
}

.thought-section.thought-done {
  border-color: #67c23a;
  background: linear-gradient(135deg, #f0f9eb 0%, #f2fcf0 100%);
}

.thought-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;
}

.thought-header:hover {
  background: rgba(0, 0, 0, 0.03);
}

.thought-icon {
  font-size: 18px;
}

.thought-title {
  font-size: 14px;
  font-weight: 600;
  color: #7a6a5c;
  flex: 1;
}

.thought-toggle-btn {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}

.thought-items {
  padding: 0 16px 8px;
}

.thought-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  color: #5a4a3a;
  line-height: 1.5;
}

.thought-item.new-thought {
  color: #e6a23c;
  font-weight: 500;
}

.thought-bullet {
  flex-shrink: 0;
  font-size: 10px;
  margin-top: 4px;
  color: #d4a574;
}

.thought-text {
  word-break: break-word;
}

/* 思考点子动画 */
.thinking-dots {
  display: flex;
  gap: 4px;
  padding: 0 16px 12px;
  align-items: center;
}

.thinking-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e6a23c;
  display: inline-block;
  animation: dotBounce 1.4s ease-in-out infinite both;
}

.thinking-dots span:nth-child(1) {
  animation-delay: -0.32s;
}
.thinking-dots span:nth-child(2) {
  animation-delay: -0.16s;
}
.thinking-dots span:nth-child(3) {
  animation-delay: 0s;
}

@keyframes dotBounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 思考条目进入动画 */
.thought-list-enter-active,
.thought-list-leave-active {
  transition: all 0.4s ease;
}

.thought-list-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.thought-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* ========== 生成动画样式 ========== */
.generate-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #e4e7ed;
}

.generate-bar {
  width: 60px;
  height: 4px;
  background: #e4e7ed;
  border-radius: 2px;
  overflow: hidden;
}

.generate-bar span {
  display: block;
  height: 100%;
  width: 40%;
  background: linear-gradient(90deg, #409eff, #667eea);
  border-radius: 2px;
  animation: generateSlide 1.2s ease-in-out infinite;
}

@keyframes generateSlide {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(250%);
  }
}

.generate-text {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.generate-done {
  margin-top: 8px;
  display: flex;
  align-items: center;
}

.done-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #67c23a;
  background: #f0f9eb;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
  border: 1px solid #b3e19d;
}

/* ========== 消息样式 ========== */
.message {
  margin-bottom: 24px;
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff 0%, #667eea 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.message.user .avatar {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
}

.content-wrapper {
  max-width: 75%;
}

.content {
  background: white;
  padding: 16px 20px;
  border-radius: 12px;
  line-height: 1.6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.content :deep(a) {
  color: #409eff;
  word-break: break-all;
}

.content :deep(a:hover) {
  text-decoration: underline;
}

.message.user .content {
  background: #ecf5ff;
  color: #333;
}

.input-area {
  padding: 20px 24px;
  border-top: 1px solid #e4e7ed;
  background-color: white;
}

.input-tips {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
  text-align: right;
}

.message-enter-active,
.message-leave-active {
  transition: all 0.5s ease;
}

.message-enter-from,
.message-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

.messages-list::-webkit-scrollbar {
  width: 6px;
}

.messages-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.messages-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.messages-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

@media (max-width: 768px) {
  .chat-container {
    height: 600px;
  }

  .content,
  .content-wrapper {
    max-width: 85%;
  }
}
</style>