<template>
  <div class="repo-input-container">
    <div class="repo-input-card">
      <div class="card-header">
        <h2 class="title">开始代码分析</h2>
        <p class="subtitle">选择要分析的项目来源：GitHub 远程仓库 或 本地项目目录</p>
      </div>

      <div class="card-body">
        <!-- 模式切换标签页 -->
        <el-tabs v-model="activeMode" class="mode-tabs" stretch>
          <el-tab-pane label="🌐 GitHub 仓库" name="github">
            <div class="mode-content">
              <p class="mode-desc">输入公开 GitHub 仓库地址，AI 将自动克隆并分析整个仓库代码。</p>
              <el-form :model="form" class="repo-form">
                <el-form-item
                  label="仓库路径"
                  :rules="[
                    { required: true, message: '请输入仓库地址', trigger: 'blur' },
                  ]"
                >
                  <el-input
                    v-model="form.repo_url"
                    placeholder="例如: langchain-ai/langchain 或 https://github.com/langchain-ai/langchain"
                    :disabled="analyzing"
                    clearable
                  >
                    <template #prefix>
                      <el-icon><Link /></el-icon>
                    </template>
                  </el-input>
                </el-form-item>
              </el-form>
            </div>
          </el-tab-pane>
          <el-tab-pane label="📁 本地项目目录" name="local">
            <div class="mode-content">
              <p class="mode-desc">输入本地项目目录的绝对路径，AI 将直接读取并分析你的项目代码。</p>
              <el-form :model="form" class="repo-form">
                <el-form-item
                  label="本地路径"
                  :rules="[
                    { required: true, message: '请输入本地路径', trigger: 'blur' },
                  ]"
                >
                  <el-input
                    v-model="form.local_path"
                    placeholder="例如: D:\MyProject\my-app 或 /home/user/projects/my-app"
                    :disabled="analyzing"
                    clearable
                  >
                    <template #prefix>
                      <el-icon><Folder /></el-icon>
                    </template>
                  </el-input>
                </el-form-item>
              </el-form>
            </div>
          </el-tab-pane>
        </el-tabs>

        <el-steps :active="stepIndex" finish-status="success" align-center class="flow-steps" v-if="analyzing">
          <el-step title="排队" description="等待启动" />
          <el-step title="分析中" description="加载文件" />
          <el-step title="索引完成" description="BM25 就绪" />
          <el-step title="可聊天" description="进入对话" />
        </el-steps>

        <div class="form-actions">
          <el-button type="primary" :loading="analyzing" @click="handleAnalyze" size="large" :disabled="analyzing">
            <el-icon v-if="!analyzing"><Search /></el-icon>
            <el-icon v-else><Loading /></el-icon>
            {{ analyzing ? '分析进行中…' : '启动分析' }}
          </el-button>
        </div>

        <el-alert
          v-if="lastResult && lastResult.kind === 'success'"
          type="success"
          :closable="true"
          @close="lastResult = null"
          show-icon
          class="result-alert"
        >
          <template #title>分析完成</template>
          <div class="result-body">
            <p v-if="lastResult.cache_hit" class="cache-line">
              <strong>缓存命中</strong> — 本次未重复扫描，加载更快。
            </p>
            <p v-else class="cache-line">冷启动：已完成全量扫描。</p>
            <p v-if="lastResult.timings" class="timing-line">
              耗时：加载 {{ lastResult.timings.load }} ms，索引 {{ lastResult.timings.index }} ms，合计
              {{ lastResult.timings.total }} ms
            </p>
          </div>
        </el-alert>

        <el-alert
          v-if="lastError"
          type="error"
          :title="lastError.title"
          :description="lastError.description"
          show-icon
          :closable="true"
          @close="lastError = null"
          class="result-alert"
        />

        <div v-if="analyzing" class="analyzing-status">
          <el-progress :percentage="progress" :indeterminate="indeterminate" :status="progressStatus" />
          <div class="status-text">
            <span class="dot pulse"></span>
            {{ statusText }}
          </div>
        </div>
      </div>

      <div class="card-footer">
        <div class="tips">
          <h3>使用提示</h3>
          <ul>
            <li><strong>GitHub 仓库：</strong>支持公开 GitHub 仓库；同一仓库二次分析会命中服务端内存缓存。</li>
            <li><strong>本地项目：</strong>输入项目的<strong>绝对路径</strong>，支持 Windows (D:\path) 和 Linux/Mac (/home/path) 格式。</li>
            <li>大型项目首次扫描可能较慢；排除 node_modules、.git、__pycache__ 等目录自动跳过。</li>
            <li>分析完成后可前往「可量化评测」查看成功率、首 token 延迟等指标。</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Link, Search, Loading, Folder } from '@element-plus/icons-vue'

const activeMode = ref('github')
const form = ref({ repo_url: '', local_path: '' })
const analyzing = ref(false)
const stepIndex = ref(0)
const progress = ref(0)
const indeterminate = ref(true)
const progressStatus = ref('')
const statusText = ref('等待启动…')
const lastResult = ref(null)
const lastError = ref(null)

const emit = defineEmits(['success'])

const errorHints = {
  timeout: '克隆或请求超时，请稍后重试或换较小的仓库。',
  permission: '权限不足（私有仓库或 Token 无效）。',
  quota: '额度或 API 速率受限，请稍后重试。',
  clone_failed: '克隆失败，请确认仓库地址且为公开仓库。',
  empty_repo: '未找到可索引的文本文件。',
  unknown: '未知错误，请查看控制台或后端日志。',
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
  let endpoint, payload, repoDisplayName

  if (activeMode.value === 'github') {
    const repoPath = normalizeRepoPath(form.value.repo_url)
    if (!repoPath) {
      ElMessage.warning('请输入正确的仓库地址，例如 owner/repo 或 https://github.com/owner/repo')
      return
    }
    endpoint = '/api/analyze'
    payload = { repo_url: repoPath }
    repoDisplayName = repoPath
  } else {
    const localPath = form.value.local_path.trim()
    if (!localPath) {
      ElMessage.warning('请输入本地项目目录的绝对路径')
      return
    }
    endpoint = '/api/analyze-local'
    payload = { local_path: localPath }
    repoDisplayName = localPath
  }

  lastError.value = null
  lastResult.value = null
  analyzing.value = true
  stepIndex.value = 1
  statusText.value = activeMode.value === 'github' ? '正在克隆或读取缓存，并解析文件…' : '正在扫描本地目录并解析文件…'
  indeterminate.value = true
  progress.value = 30
  progressStatus.value = ''

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 120000)

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    if (res.ok) {
      const data = await res.json()
      stepIndex.value = 2
      statusText.value = '索引完成，准备进入聊天…'
      progress.value = 100
      indeterminate.value = false
      progressStatus.value = 'success'

      lastResult.value = {
        kind: 'success',
        cache_hit: !!data.cache_hit,
        timings: data.timings_ms || null,
      }

      stepIndex.value = 3
      ElMessage.success(data.cache_hit ? '缓存命中，分析完成' : '分析完成')
      emit('success', data)
    } else {
      let payload = {}
      try {
        payload = await res.json()
      } catch {
        /* ignore */
      }
      const detail = payload.detail
      let code = 'unknown'
      let message = res.statusText || '分析失败'
      let hint = errorHints.unknown

      if (detail && typeof detail === 'object') {
        code = detail.code || code
        message = detail.message || message
        hint = detail.hint || errorHints[code] || hint
      } else if (typeof detail === 'string') {
        message = detail
      }

      stepIndex.value = 1
      progressStatus.value = 'exception'
      progress.value = 0
      indeterminate.value = false
      statusText.value = '分析失败'

      lastError.value = {
        title: `失败原因：${code}`,
        description: `${hint}\n${message}`,
      }
      ElMessage.error('分析未完成，请查看说明')
    }
  } catch (err) {
    clearTimeout(timeoutId)
    const isAbort = err.name === 'AbortError'
    const code = isAbort ? 'timeout' : 'unknown'
    stepIndex.value = 1
    progressStatus.value = 'exception'
    progress.value = 0
    indeterminate.value = false
    statusText.value = '分析失败'
    lastError.value = {
      title: `失败原因：${code}`,
      description: isAbort ? errorHints.timeout : err.message || errorHints.unknown,
    }
    ElMessage.error(isAbort ? '请求超时' : '网络或服务器错误')
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
  font-size: 15px;
  opacity: 0.9;
  margin: 0;
}

.card-body {
  padding: 32px;
}

/* Tabs 样式重写 */
.mode-tabs {
  margin-bottom: 24px;
}

.mode-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
  height: 48px;
  line-height: 48px;
}

.mode-tabs :deep(.el-tabs__item.is-active) {
  font-weight: 600;
}

.mode-content {
  padding: 8px 0;
}

.mode-desc {
  font-size: 14px;
  color: #606266;
  margin: 0 0 16px 0;
  line-height: 1.6;
}

.flow-steps {
  margin-bottom: 28px;
  margin-top: 16px;
}

.repo-form {
  margin-bottom: 16px;
}

.form-actions {
  margin-top: 16px;
  text-align: center;
}

.result-alert {
  margin-top: 16px;
}

.result-body {
  font-size: 14px;
  line-height: 1.6;
}

.cache-line,
.timing-line {
  margin: 6px 0 0;
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
