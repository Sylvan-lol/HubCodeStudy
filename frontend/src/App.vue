<template>
  <div class="app-container">
    <header class="app-header">
      <h1 class="app-title">GitChat - 智能代码仓库分析助手</h1>
      <button v-if="analyzed" class="back-btn" @click="handleBack">
        <el-icon><ArrowLeft /></el-icon> 重新分析仓库
      </button>
    </header>
    
    <main class="app-main">
      <transition name="fade" mode="out-in">
        <RepoInput v-if="!analyzed" @success="handleRepoAnalyzed" key="repo-input" />
        <ChatWindow v-else @back="handleBack" key="chat-window" />
      </transition>
    </main>
    
    <footer class="app-footer">
      <p>© 2026 GitChat. 企业级代码仓库分析助手</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import RepoInput from './components/RepoInput.vue'
import ChatWindow from './components/ChatWindow.vue'

const analyzed = ref(false)

// 从本地存储加载状态
onMounted(() => {
  const savedState = localStorage.getItem('gitchat_analyzed')
  if (savedState) {
    analyzed.value = JSON.parse(savedState)
  }
})

const handleRepoAnalyzed = () => {
  analyzed.value = true
  // 保存状态到本地存储
  localStorage.setItem('gitchat_analyzed', JSON.stringify(true))
}

const handleBack = () => {
  analyzed.value = false
  // 清除本地存储
  localStorage.removeItem('gitchat_analyzed')
  localStorage.removeItem('gitchat_messages')
}
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.app-header {
  background: white;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: 20px 40px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
}

.app-title {
  color: #333;
  font-size: 24px;
  font-weight: 700;
  margin: 0;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: white;
  color: #409eff;
  cursor: pointer;
  transition: all 0.3s ease;
}

.back-btn:hover {
  background: #ecf5ff;
  border-color: #409eff;
}

.app-main {
  flex: 1;
  padding: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.app-footer {
  background: white;
  padding: 20px;
  text-align: center;
  color: #606266;
  font-size: 14px;
  border-top: 1px solid #e4e7ed;
}

/* 动画效果 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease, transform 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
