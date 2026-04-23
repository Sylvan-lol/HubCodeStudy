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
      <transition-group name="message" tag="div">
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role]">
          <div class="avatar">{{ msg.role === 'user' ? 'ME' : 'AI' }}</div>
          <div class="content" v-html="renderMarkdown(msg.content)"></div>
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
import { ref, nextTick, onMounted, onUnmounted } from 'vue';
import { marked } from 'marked';
import { Promotion, Loading } from '@element-plus/icons-vue';

const emit = defineEmits(['back']);
const messages = ref([]);
const inputMsg = ref('');
const loading = ref(false);
const scrollBox = ref(null);
const connected = ref(false);
// 从本地存储加载消息
onMounted(() => {
  const savedMessages = localStorage.getItem('gitchat_messages');
  if (savedMessages) {
    messages.value = JSON.parse(savedMessages);
    scrollToBottom();
  }
  // 模拟连接状态
  setTimeout(() => {
    connected.value = true;
  }, 1000);
});

// 保存消息到本地存储
const saveMessages = () => {
  localStorage.setItem('gitchat_messages', JSON.stringify(messages.value));
};

const renderMarkdown = (text) => marked.parse(text);

const scrollToBottom = async () => {
  await nextTick();
  if (scrollBox.value) {
    scrollBox.value.scrollTop = scrollBox.value.scrollHeight;
  }
};

const sendMessage = async () => {
  if (!inputMsg.value || loading.value) return;

  const userQuery = inputMsg.value;
  messages.value.push({ role: 'user', content: userQuery });
  inputMsg.value = '';
  loading.value = true;
  saveMessages();
  scrollToBottom();

  const aiMsgIndex = messages.value.push({ role: 'assistant', content: '' }) - 1;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userQuery })
    });

    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ') && line !== 'data: [DONE]') {
          const data = JSON.parse(line.slice(6));
          messages.value[aiMsgIndex].content += data.content;
          saveMessages();
          scrollToBottom();
        }
      }
    }
  } catch (error) {
    console.error('Streaming Error:', error);
    messages.value[aiMsgIndex].content = '抱歉，服务器连接失败，请稍后重试。';
    saveMessages();
  } finally {
    loading.value = false;
  }
};
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

.content {
  background: white;
  padding: 16px 20px;
  border-radius: 12px;
  max-width: 75%;
  line-height: 1.6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: relative;
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

/* 动画效果 */
.message-enter-active,
.message-leave-active {
  transition: all 0.5s ease;
}

.message-enter-from,
.message-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

/* 滚动条样式 */
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

/* 响应式设计 */
@media (max-width: 768px) {
  .chat-container {
    height: 600px;
  }
  
  .content {
    max-width: 85%;
  }
}
</style>
