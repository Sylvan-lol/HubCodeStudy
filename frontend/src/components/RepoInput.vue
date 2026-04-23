<template>
  <div class="repo-input-container">
    <div class="repo-input-card">
      <div class="card-header">
        <h2 class="title">🚀 开始分析 GitHub 仓库</h2>
        <p class="subtitle">输入仓库地址，让 AI 帮你分析代码结构和逻辑</p>
      </div>
      
      <div class="card-body">
        <el-form :model="form" class="repo-form">
          <el-form-item label="仓库路径" :rules="[{ required: true, message: '请输入仓库地址', trigger: 'blur' }, { pattern: /^(github\.com\/[^/]+\/[^/]+|[^/]+\/[^/]+)$/, message: '请输入正确的格式: owner/repo 或 https://github.com/owner/repo', trigger: 'blur' }]">
            <el-input 
              v-model="form.repo_url" 
              placeholder="例如: langchain-ai/langchain" 
              style="width: 100%"
              :disabled="analyzing"
              clearable
            >
              <template #prefix>
                <el-icon><Link /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <div class="form-actions">
            <el-button type="primary" :loading="analyzing" @click="handleAnalyze" size="large" :disabled="analyzing">
              <el-icon v-if="!analyzing"><Search /></el-icon>
              <el-icon v-else><Loading /></el-icon>
              {{ analyzing ? '深度分析中...' : '启动分析' }}
            </el-button>
            <el-button type="success" @click="testJump" size="large" :disabled="analyzing" style="margin-left: 10px;">
              测试跳转
            </el-button>
          </div>
        </el-form>
        
        <div v-if="analyzing" class="analyzing-status">
          <el-progress :percentage="progress" :status="status" />
          <div class="status-text">
            <span class="dot pulse"></span>
            {{ statusText }}
          </div>
        </div>
      </div>
      
      <div class="card-footer">
        <div class="tips">
          <h3>💡 使用提示</h3>
          <ul>
            <li>支持公开 GitHub 仓库</li>
            <li>大型仓库分析可能需要 1-2 分钟</li>
            <li>分析完成后可以开始与 AI 聊天</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Link, Search, Loading } from '@element-plus/icons-vue'

const form = ref({ repo_url: '' })
const analyzing = ref(false)
const progress = ref(0)
const status = ref('')
const statusText = ref('准备分析仓库...')
const emit = defineEmits(['success'])

const testJump = () => {
    console.log('测试跳转...')
    // 直接显示成功弹窗并跳转
    ElMessageBox.alert('测试成功，现在跳转到聊天页面！', '测试成功', {
      confirmButtonText: '确定',
      type: 'success'
    }).then(() => {
      console.log('用户点击了确定，准备跳转...')
      emit('success') // 直接跳转
    }).catch(() => {
      console.log('弹窗被关闭...')
    })
  }

const normalizeRepoPath = (rawInput) => {
    let repoPath = rawInput.trim()

    const fullUrlMatch = repoPath.match(/^https?:\/\/github\.com\/([^/]+)\/([^/#?]+)/i)
    if (fullUrlMatch) {
      return `${fullUrlMatch[1]}/${fullUrlMatch[2].replace(/\.git$/i, '')}`
    }

    const shortPathMatch = repoPath.match(/^([^/]+)\/([^/]+)$/)
    if (shortPathMatch) {
      return `${shortPathMatch[1]}/${shortPathMatch[2].replace(/\.git$/i, '')}`
    }

    return ''
  }

const handleAnalyze = async () => {
    // 处理完整的 GitHub URL，提取 owner/repo
    const repoPath = normalizeRepoPath(form.value.repo_url)
    if (!repoPath) {
      ElMessage.warning('请输入正确的仓库地址，例如 owner/repo 或 https://github.com/owner/repo')
      return
    }
    
    console.log('开始分析仓库:', repoPath)
    
    analyzing.value = true
    progress.value = 0 // 重置进度
    statusText.value = '准备分析仓库...'

    // 模拟进度条，但最高只到 95%，等待后端真正返回
    const timer = setInterval(() => {
      if (progress.value < 95) {
        progress.value += 5
        if (progress.value < 30) statusText.value = '正在克隆仓库...'
        else if (progress.value < 70) statusText.value = '正在解析代码并生成索引...'
        else statusText.value = '正在完成收尾工作...'
      }
    }, 800)
    
    try {
      console.log('发送分析请求到后端...')
      console.log('请求URL:', 'http://localhost:8000/analyze')
      console.log('请求数据:', { repo_url: repoPath })
      
      // 添加 60 秒超时
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 60000)
      
      try {
        console.log('开始发送 fetch 请求...')
        console.log('请求 URL:', 'http://localhost:8000/analyze')
        console.log('请求数据:', JSON.stringify({ repo_url: repoPath }))
        
        // 使用相对路径，利用 Vite 的代理
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ repo_url: repoPath }),
          signal: controller.signal
        })
        
        console.log('fetch 请求发送成功，收到响应...')
        console.log('响应状态:', res.status)
        console.log('响应状态文本:', res.statusText)
        
        clearTimeout(timeoutId)
        
        console.log('收到后端响应:', res)
        console.log('响应状态:', res.status)
        console.log('响应状态文本:', res.statusText)
        
        if (res.ok) {
          console.log('响应成功，开始解析响应数据...')
          const data = await res.json()
          console.log('响应数据:', data)
          
          clearInterval(timer)
          progress.value = 100
          statusText.value = '分析完成！'
          
          // 先切页，确保“分析成功后立即进入聊天”
          emit('success')
          ElMessage.success('仓库分析完成，已进入聊天页面')
        } else {
          clearTimeout(timeoutId)
          console.error('响应失败:', res.status, res.statusText)
          const errorData = await res.json().catch(() => ({}))
          console.error('错误数据:', errorData)
          throw new Error(`分析失败: ${res.statusText}`)
        }
      } catch (err) {
        clearTimeout(timeoutId)
        if (err.name === 'AbortError') {
          throw new Error('分析超时，请检查网络连接或尝试分析较小的仓库')
        }
        throw err
      }
    } catch (err) {
      clearInterval(timer)
      console.error('分析过程出错:', err)
      progress.value = 0
      status.value = 'exception'
      statusText.value = '分析失败'
      ElMessage.error(`分析失败: ${err.message}`)
    } finally {
      analyzing.value = false
    }
  }
</script>

<style scoped>
.repo-input-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.repo-input-card {
  width: 100%;
  max-width: 800px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  animation: fadeIn 0.8s ease;
}

.card-header {
  background: linear-gradient(135deg, #409eff 0%, #667eea 100%);
  color: white;
  padding: 32px;
  text-align: center;
}

.title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 16px;
  opacity: 0.9;
  margin: 0;
}

.card-body {
  padding: 32px;
}

.repo-form {
  margin-bottom: 24px;
}

.form-actions {
  margin-top: 24px;
  text-align: center;
}

.analyzing-status {
  margin-top: 24px;
}

.status-text {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
  font-size: 14px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409eff;
}

.dot.pulse {
  animation: pulse 1.5s infinite;
}

.card-footer {
  background: #f5f7fa;
  padding: 24px 32px;
  border-top: 1px solid #e4e7ed;
}

.tips h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: #303133;
}

.tips ul {
  margin: 0;
  padding-left: 20px;
  color: #606266;
  font-size: 14px;
}

.tips li {
  margin-bottom: 6px;
}

/* 动画效果 */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0% {
    transform: scale(0.8);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.7;
  }
  100% {
    transform: scale(0.8);
    opacity: 1;
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .card-header,
  .card-body,
  .card-footer {
    padding: 20px;
  }
  
  .title {
    font-size: 20px;
  }
}
</style>
