<template>
  <div class="benchmark-page">
    <el-card class="intro-card" shadow="hover">
      <p class="lead">
        面试时可说清：<strong>不是「我感觉更好了」，而是指标在变好。</strong> 以下为当前进程内累计数据（刷新页面会归零；适合演示与压测对比）。
      </p>
    </el-card>

    <el-card v-loading="loading" class="table-card" shadow="hover">
      <template #header>
        <span>实时评测指标</span>
        <el-button type="primary" link class="refresh" @click="load" :loading="loading">刷新</el-button>
      </template>
      <el-table :data="tableRows" stripe border style="width: 100%">
        <el-table-column prop="name" label="指标" min-width="160" />
        <el-table-column prop="value" label="数值" min-width="120" />
        <el-table-column prop="meaning" label="含义 / 口径" min-width="280" />
      </el-table>
      <p v-if="error" class="error">{{ error }}</p>
      <p class="hint">接口：<code>/api/metrics</code>（经 Vite 代理到后端）。多跑几次分析与对话后命中率与延迟更有参考价值。</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const loading = ref(false)
const error = ref('')
const metrics = ref(null)

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/metrics')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    metrics.value = data.metrics || {}
  } catch (e) {
    error.value = e.message || '无法拉取指标，请确认后端已启动。'
    metrics.value = null
  } finally {
    loading.value = false
  }
}

const tableRows = computed(() => {
  const m = metrics.value || {}
  const pct = (x) => (x == null ? '—' : `${(Number(x) * 100).toFixed(2)}%`)
  return [
    {
      name: 'Analyze 成功率',
      value: pct(m.analyze_success_rate),
      meaning: `成功 ${m.analyze_success ?? 0} / 尝试 ${m.analyze_attempts ?? 0}（失败 ${m.analyze_failures ?? 0}）`,
    },
    {
      name: '首 token 延迟（均值）',
      value: m.first_token_latency_avg_ms != null ? `${m.first_token_latency_avg_ms} ms` : '—',
      meaning: `流式回答首包耗时，样本数 ${m.first_token_samples ?? 0}`,
    },
    {
      name: '证据命中率',
      value: pct(m.evidence_hit_rate),
      meaning: `检索到上下文的对话占比（有 BM25 命中片段即计命中），${m.chat_evidence_hits ?? 0}/${m.chat_total ?? 0}`,
    },
    {
      name: '回答有效率',
      value: pct(m.answer_effectiveness_rate),
      meaning: `非空且长度与措辞正常的助手回复占比，${m.chat_effective_answers ?? 0}/${m.chat_total ?? 0}`,
    },
    {
      name: '分析缓存命中（次）',
      value: String(m.analyze_cache_hits ?? 0),
      meaning: `同一仓库二次分析走内存缓存；命中率（相对成功分析）${pct(m.analyze_cache_hit_rate)}`,
    },
  ]
})

onMounted(load)
</script>

<style scoped>
.benchmark-page {
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.lead {
  margin: 0;
  font-size: 15px;
  color: #303133;
  line-height: 1.6;
}

.table-card :deep(.el-card__header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.refresh {
  font-size: 14px;
}

.hint {
  margin: 16px 0 0;
  font-size: 13px;
  color: #909399;
}

.error {
  margin-top: 12px;
  color: #f56c6c;
  font-size: 14px;
}
</style>
