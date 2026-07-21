<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount, nextTick } from "vue"
import { useI18n } from "vue-i18n"
import { useRecordStore } from "@/stores/record.store"

interface Props {
  modelValue: boolean
  recordId: number | null
}
const props = defineProps<Props>()
const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void
}>()

const { t } = useI18n()
const recordStore = useRecordStore()

const scrapeLog = ref<any>(null)
const loading = ref(false)
const error404 = ref(false)
const error = ref<string | null>(null)
const logsContainer = ref<HTMLElement | null>(null)
const pollTimer = ref<number | null>(null)
const fetchGeneration = ref(0)
const pollingInFlight = ref(false)

const isRunning = computed(
  () => scrapeLog.value?.status === "running",
)
const isTerminal = computed(
  () => ["success", "failed", "interrupted"].includes(scrapeLog.value?.status ?? ""),
)

const statusColor = computed(() => {
  const s = scrapeLog.value?.status
  if (s === "success") return "success"
  if (s === "failed") return "error"
  if (s === "interrupted") return "warning"
  return "info"
})

const statusText = computed(() => {
  const s = scrapeLog.value?.status
  if (!s) return ""
  return t(`pages.records.scrapeLog.${s}`)
})

const formattedStartedAt = computed(() => formatDateTime(scrapeLog.value?.started_at))
const formattedFinishedAt = computed(() => formatDateTime(scrapeLog.value?.finished_at))

const logLines = computed(() => {
  const text = scrapeLog.value?.log_text ?? ""
  if (!text) return []
  return text.split("\n").filter((l: string) => l.trim().length > 0)
})

function formatDateTime(dateStr: string | null | undefined) {
  if (!dateStr) return ""
  return new Date(dateStr).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
}

async function loadLatestLog() {
  if (props.recordId == null) return
  const gen = ++fetchGeneration.value
  loading.value = true
  error.value = null
  try {
    const log = await recordStore.fetchLatestScrapeLog(props.recordId)
    if (gen !== fetchGeneration.value) return // 陈旧响应
    if (!props.modelValue) return // drawer 已关闭
    scrapeLog.value = log
    error404.value = false
  } catch (err: any) {
    if (gen !== fetchGeneration.value) return
    if (err?.status === 404 || err?.statusCode === 404) {
      error404.value = true
      scrapeLog.value = null
    } else {
      console.error("Failed to load scrape log:", err)
      error404.value = false // 切换到非 404 错误时清除 404 状态
      error.value = t('pages.records.scrapeLog.loadError') || '加载日志失败'
    }
  } finally {
    if (gen === fetchGeneration.value) {
      loading.value = false
      await nextTick()
      scrollToBottom()
    }
  }
}

function scrollToBottom() {
  if (logsContainer.value) {
    logsContainer.value.scrollTop = logsContainer.value.scrollHeight
  }
}

function startPolling() {
  stopPolling()
  pollTimer.value = window.setInterval(async () => {
    if (isTerminal.value) {
      stopPolling()
      return
    }
    if (pollingInFlight.value) return // 上一次请求未完成，跳过
    pollingInFlight.value = true
    try {
      await loadLatestLog()
    } finally {
      pollingInFlight.value = false
    }
  }, 1000)
}

function stopPolling() {
  if (pollTimer.value !== null) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

function closeDrawer() {
  emit("update:modelValue", false)
}

// React to drawer open + recordId changes
watch(
  () => [props.modelValue, props.recordId] as const,
  async ([open, _rid]) => {
    if (open && _rid != null) {
      await loadLatestLog()
      // await 之后需重新检查抽屉是否仍打开、recordId 是否仍一致
      if (!props.modelValue || props.recordId !== _rid) return
      if (!isTerminal.value) {
        startPolling() // 即使 404 也启动轮询，任务创建日志后自动出现
      }
    } else if (!open) {
      stopPolling()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <v-navigation-drawer
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    location="right"
    width="650"
    temporary
    floating
  >
    <div class="drawer-header d-flex align-center pa-4">
      <h3 class="text-h6 flex-grow-1">
        {{ t('pages.records.scrapeLog.title') }}
      </h3>
      <v-btn
        icon="mdi-close"
        variant="text"
        size="small"
        @click="closeDrawer"
      />
    </div>

    <v-divider />

    <!-- Loading state -->
    <div v-if="loading && !scrapeLog" class="pa-4 text-center text-grey">
      <v-progress-circular indeterminate size="32" />
    </div>

    <!-- 404 / empty state -->
    <div v-else-if="error404" class="pa-8 text-center text-grey">
      <v-icon size="48" color="grey-lighten-1" class="mb-3">
        mdi-file-document-outline
      </v-icon>
      <div>{{ t('pages.records.noScrapeLog') }}</div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="pa-4 text-center">
      <v-icon size="48" color="error" class="mb-3">mdi-alert-circle-outline</v-icon>
      <div class="text-error mb-3">{{ error }}</div>
      <v-btn size="small" variant="outlined" color="primary" @click="loadLatestLog">
        {{ t('common.retry') || '重试' }}
      </v-btn>
    </div>

    <!-- Log content -->
    <div v-else-if="scrapeLog" class="drawer-body">
      <!-- Metadata header -->
      <div class="meta-section pa-4">
        <div class="d-flex align-center mb-2">
          <span class="meta-label">{{ t('pages.records.scrapeLog.status') }}:</span>
          <v-chip
            :color="statusColor"
            size="small"
            variant="flat"
            class="ml-2"
          >
            <v-icon
              v-if="isRunning"
              size="x-small"
              class="mr-1"
              icon="mdi-loading"
              :class="{ 'spin': isRunning }"
            />
            {{ statusText }}
          </v-chip>
        </div>
        <div v-if="scrapeLog.celery_task_id" class="meta-row">
          <span class="meta-label">{{ t('pages.records.scrapeLog.celeryTaskId') }}:</span>
          <code class="meta-value text-caption">{{ scrapeLog.celery_task_id }}</code>
        </div>
        <div class="meta-row">
          <span class="meta-label">{{ t('pages.records.scrapeLog.startedAt') }}:</span>
          <span class="meta-value">{{ formattedStartedAt }}</span>
        </div>
        <div v-if="formattedFinishedAt" class="meta-row">
          <span class="meta-label">{{ t('pages.records.scrapeLog.finishedAt') }}:</span>
          <span class="meta-value">{{ formattedFinishedAt }}</span>
        </div>
        <div v-if="scrapeLog.error_msg" class="error-box mt-2 pa-2">
          <div class="text-caption font-weight-bold mb-1">
            {{ t('pages.records.scrapeLog.error') }}:
          </div>
          <div class="text-caption">{{ scrapeLog.error_msg }}</div>
        </div>
      </div>

      <v-divider />

      <!-- Log text -->
      <div class="log-section">
        <div class="log-section-header pa-2 text-caption text-grey">
          {{ logLines.length }} lines
        </div>
        <div
          v-if="logLines.length === 0"
          class="pa-4 text-center text-grey"
        >
          {{ t('pages.records.scrapeLog.empty') }}
        </div>
        <div
          v-else
          ref="logsContainer"
          class="logs-container"
        >
          <div
            v-for="(line, idx) in logLines"
            :key="idx"
            class="log-line"
            :class="{
              'log-error': line.includes('ERROR') || line.includes('✗'),
              'log-warning': line.includes('WARNING') || line.includes('⊘'),
            }"
          >
            {{ line }}
          </div>
        </div>
      </div>
    </div>
  </v-navigation-drawer>
</template>

<style scoped>
.drawer-header {
  background-color: rgba(var(--v-theme-primary), 0.05);
}

.drawer-body {
  display: flex;
  flex-direction: column;
  height: calc(100% - 65px);
}

.meta-section {
  background-color: rgba(var(--v-theme-surface-variant), 0.3);
}

.meta-row {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  font-size: 13px;
}

.meta-label {
  color: rgba(var(--v-theme-on-surface), 0.6);
  margin-right: 8px;
  min-width: 100px;
}

.meta-value {
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.error-box {
  background-color: rgba(var(--v-theme-error), 0.1);
  border-left: 3px solid rgb(var(--v-theme-error));
  border-radius: 4px;
}

.log-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.log-section-header {
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  padding-left: 12px;
}

.logs-container {
  flex: 1;
  overflow-y: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  padding: 8px 12px;
  background-color: rgba(var(--v-theme-surface), 0.5);
}

.log-line {
  white-space: pre-wrap;
  word-break: break-word;
  padding: 1px 0;
  color: rgba(var(--v-theme-on-surface), 0.85);
}

.log-line.log-error {
  color: rgb(var(--v-theme-error));
}

.log-line.log-warning {
  color: rgb(var(--v-theme-warning));
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
