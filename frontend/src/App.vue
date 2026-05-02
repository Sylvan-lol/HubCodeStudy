<template>
  <div class="app-container">
    <header class="app-header">
      <div class="header-left">
        <h1 class="app-title">GitChat - 智能代码仓库分析助手</h1>
        <nav class="nav">
          <router-link to="/" class="nav-link" active-class="active" exact-active-class="active">分析 / 聊天</router-link>
          <router-link to="/benchmark" class="nav-link" active-class="active">可量化评测</router-link>
        </nav>
      </div>
      <button
        v-if="route.path === '/' && analyzed"
        class="back-btn"
        type="button"
        @click="resetRepo"
      >
        <el-icon><ArrowLeft /></el-icon> 重新分析仓库
      </button>
    </header>

    <main class="app-main">
      <router-view />
    </main>

    <footer class="app-footer">
      <p>© 2026 GitChat. 企业级代码仓库分析助手</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, provide, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const analyzed = ref(false)
const repoSlug = ref('')

const setRepoAnalyzed = (payload = {}) => {
  analyzed.value = true
  repoSlug.value = payload.repo_slug || payload.repoSlug || ''
  localStorage.setItem('gitchat_analyzed', JSON.stringify(true))
  if (repoSlug.value) {
    localStorage.setItem('gitchat_repo_slug', repoSlug.value)
  }
}

const resetRepo = () => {
  analyzed.value = false
  repoSlug.value = ''
  localStorage.removeItem('gitchat_analyzed')
  localStorage.removeItem('gitchat_repo_slug')
  localStorage.removeItem('gitchat_messages')
}

onMounted(() => {
  const saved = localStorage.getItem('gitchat_analyzed')
  if (saved && JSON.parse(saved)) {
    analyzed.value = true
    repoSlug.value = localStorage.getItem('gitchat_repo_slug') || ''
  }
})

provide('gitchat', {
  analyzed,
  repoSlug,
  setRepoAnalyzed,
  resetRepo,
})
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
  padding: 16px 40px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.app-title {
  color: #333;
  font-size: 22px;
  font-weight: 700;
  margin: 0;
}

.nav {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.nav-link {
  color: #606266;
  text-decoration: none;
  font-size: 14px;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
}

.nav-link:hover {
  color: #409eff;
}

.nav-link.active {
  color: #409eff;
  font-weight: 600;
  border-bottom-color: #409eff;
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
</style>
