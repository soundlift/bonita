<script setup lang="ts">
import { useRecordStore } from "@/stores/record.store"
import { useTaskStore } from "@/stores/task.store"
import { useI18n } from "vue-i18n"
import { VIcon } from "vuetify/components"

const recordStore = useRecordStore()
const taskStore = useTaskStore()
const { t } = useI18n() // 导入国际化工具函数

const searchQuery = ref("")
const taskIdQuery = ref("")
const activeTab = ref<'pending' | 'done'>('pending')
const scrapeLogDrawerOpen = ref(false)
const currentScrapeLogRecordId = ref<number | null>(null)
const searchTimeout = ref<number | null>(null)
const requestGeneration = ref(0)
const selected = ref<number[]>([])
const tagColorMap = {
  中文字幕: "#FF0000",
  破解: "#FFA500",
} as const

// localStorage 持久化
const STORAGE_KEY = "records-view-settings"
let settingsLoaded = false

// 刷新相关变量
const autoRefresh = ref(true) // 是否自动刷新
const refreshInterval = ref(10) // 刷新间隔（秒）
const refreshTimer = ref<number | null>(null) // 刷新定时器
const lastRefreshTime = ref<Date | null>(null) // 上次刷新时间
const hasNewData = ref(false) // 是否有新数据
const lastDataHash = ref("") // 上次数据的哈希值，用于检测变化

// 删除确认对话框
const deleteDialog = ref(false)
const forceDelete = ref(false)

// 重试确认对话框
const retryDialog = ref(false)

// 分页选项
const pageSizeOptions = [10, 25, 50, 100]

// 计算下次刷新时间的倒计时
const refreshCountdown = computed(() => {
  if (!autoRefresh.value || !lastRefreshTime.value) return 0

  const nextRefreshTime = new Date(
    lastRefreshTime.value.getTime() + refreshInterval.value * 1000,
  )
  const now = new Date()
  const remainingSeconds = Math.max(
    0,
    Math.floor((nextRefreshTime.getTime() - now.getTime()) / 1000),
  )

  return remainingSeconds
})

// 一个简单的函数来生成数据哈希，用于检测变化
const generateDataHash = (data: any[]) => {
  return JSON.stringify(
    data.map(
      (item) => `${item.transfer_record.id}_${item.transfer_record.updatetime}`,
    ),
  )
}

const getTagColor = (tag: string) => {
  return tagColorMap[tag.trim() as keyof typeof tagColorMap] || "#9DA8B5"
}

const formatDateTime = (dateStr: string | null | undefined) => {
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

const formatFileSize = (bytes: number | null | undefined) => {
  if (bytes == null || bytes === undefined) return ""
  if (bytes < 1024) return bytes + " B"
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " K"
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " M"
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " G"
}

const allHeaders = [
  {
    title: t("pages.records.name"),
    align: "start" as "start" | "center" | "end",
    key: "transfer_record.srcname",
    width: 250,
    sortable: true,
    alwaysVisible: true,
  },
  {
    title: t("pages.records.status"),
    align: "center" as "start" | "center" | "end",
    key: "transfer_record.success",
    width: 100,
    sortable: false,
  },
  {
    title: t("pages.records.fileSize"),
    align: "center" as "start" | "center" | "end",
    key: "transfer_record.filesize",
    width: 100,
    sortable: true,
  },
  {
    title: t("pages.records.destPath"),
    align: "center" as "start" | "center" | "end",
    key: "transfer_record.destpath",
    width: 200,
    sortable: true,
  },
  {
    title: t("pages.records.season"),
    align: "center" as "start" | "center" | "end",
    key: "transfer_record.season",
    width: 100,
    sortable: true,
  },
  {
    title: t("pages.records.episode"),
    align: "center" as "start" | "center" | "end",
    key: "transfer_record.episode",
    width: 100,
    sortable: true,
  },
  {
    title: t("pages.records.number"),
    align: "center" as "start" | "center" | "end",
    key: "extra_info.number",
    width: 100,
    sortable: false,
  },
  {
    title: t("pages.records.tag"),
    align: "center" as "start" | "center" | "end",
    key: "extra_info.tag",
    width: 100,
    sortable: false,
  },
  {
    title: t("pages.records.createTime"),
    align: "center" as "start" | "center" | "end",
    key: "transfer_record.createtime",
    width: 120,
    sortable: true,
  },
  {
    title: t("pages.records.updateTime"),
    align: "center" as "start" | "center" | "end",
    key: "transfer_record.updatetime",
    width: 120,
    sortable: true,
  },
  {
    title: t("pages.records.deadTime"),
    align: "center" as "start" | "center" | "end",
    key: "transfer_record.deadtime",
    width: 120,
    sortable: true,
  },
]

// actions 列始终单独追加，不可配置
const actionsHeader = {
  title: t("common.actions"),
  key: "actions",
  sortable: false,
  width: 100,
  alwaysVisible: true,
}

// 可配置列的 key 列表（不含 actions）
const configurableKeys = allHeaders.map((h) => h.key)

// 用户可见的列 key
const visibleColumnKeys = ref<string[]>([...configurableKeys])

// 实际渲染的 headers：过滤可见列 + 始终追加 actions
const displayedHeaders = computed(() => {
  return [
    ...allHeaders.filter((h) => visibleColumnKeys.value.includes(h.key)),
    actionsHeader,
  ]
})

// 默认排序设置
const sortBy = ref([
  {
    key: "transfer_record.createtime",
    order: "desc" as const,
  },
])

// 处理分页变化
const handlePageChange = async (newPage: number) => {
  selected.value = [] // 页面切换时清空选中项
  await loadData(newPage, recordStore.itemsPerPage)
}

// 处理每页数量变化
const handleItemsPerPageChange = async (newItemsPerPage: number) => {
  // 这里不使用v-model双向绑定，而是手动更新并重新加载数据
  selected.value = [] // 清空选中项
  // 调用loadData，传递当前页和新的每页数量
  await loadData(1, newItemsPerPage)
}

const loadData = async (
  page = recordStore.currentPage,
  itemsPerPage = recordStore.itemsPerPage,
  isAutoRefresh = false,
) => {
  const gen = ++requestGeneration.value
  // 构建搜索参数
  const searchParams: {
    page: number
    itemsPerPage: number
    search?: string
    taskId?: number
    success?: boolean | null
    sortBy?: string
    sortDesc?: boolean
  } = {
    page,
    itemsPerPage,
  }

  // 如果有任务ID输入，则添加到搜索参数
  if (taskIdQuery.value.trim()) {
    const taskId = Number.parseInt(taskIdQuery.value.trim())
    if (!Number.isNaN(taskId)) {
      searchParams.taskId = taskId
    }
  }

  // 如果有搜索内容，则添加到搜索参数
  if (searchQuery.value.trim()) {
    searchParams.search = searchQuery.value.trim()
  }

  // 根据 activeTab 决定 success 参数：pending -> false (IS NOT TRUE), done -> true
  searchParams.success = activeTab.value === 'pending' ? false : true

  // 添加排序参数
  if (sortBy.value.length > 0) {
    const sortKey = sortBy.value[0].key
    // 只有 transfer_record 前缀的字段才可以排序
    if (sortKey.startsWith("transfer_record.")) {
      // 去掉 "transfer_record." 前缀，只传入字段名
      searchParams.sortBy = sortKey.replace("transfer_record.", "")
      searchParams.sortDesc = sortBy.value[0].order === "desc"
    }
  }
  await recordStore.getRecords(searchParams)
  if (gen !== requestGeneration.value) return // 陈旧响应，丢弃

  // 刷新后处理
  lastRefreshTime.value = new Date()

  // 如果是自动刷新，检查数据是否有变化
  if (isAutoRefresh) {
    const newDataHash = generateDataHash(recordStore.records)
    if (lastDataHash.value && newDataHash !== lastDataHash.value) {
      hasNewData.value = true
    }
    lastDataHash.value = newDataHash
  } else {
    // 如果是手动刷新，重置新数据标志
    hasNewData.value = false
    lastDataHash.value = generateDataHash(recordStore.records)
  }

  // 设置下一次自动刷新
  setupAutoRefresh()
}

// 设置自动刷新定时器
const setupAutoRefresh = () => {
  // 清除现有定时器
  if (refreshTimer.value) {
    clearTimeout(refreshTimer.value)
    refreshTimer.value = null
  }

  // 如果启用了自动刷新，设置新的定时器
  if (autoRefresh.value) {
    refreshTimer.value = setTimeout(() => {
      loadData(recordStore.currentPage, recordStore.itemsPerPage, true)
    }, refreshInterval.value * 1000) as unknown as number
  }
}

// 切换自动刷新状态
const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    // 启用自动刷新时，立即设置定时器
    setupAutoRefresh()
  } else {
    // 禁用自动刷新时，清除定时器
    if (refreshTimer.value) {
      clearTimeout(refreshTimer.value)
      refreshTimer.value = null
    }
  }
}

// 手动刷新数据
const manualRefresh = async () => {
  hasNewData.value = false
  await loadData(recordStore.currentPage, recordStore.itemsPerPage)
}

// 保存视图设置到 localStorage
const saveSettings = () => {
  try {
    const settings = {
      activeTab: activeTab.value,
      visibleColumnKeys: visibleColumnKeys.value,
      sortBy: sortBy.value,
      itemsPerPage: recordStore.itemsPerPage,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // 存储失败时静默忽略
  }
}

// 从 localStorage 恢复视图设置
const loadSettings = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const settings = JSON.parse(raw)
    // 迁移旧字段 successFilter -> activeTab (一次性，立即回写)
    if ('successFilter' in settings) {
      const old = settings.successFilter
      activeTab.value = old === true ? 'done' : 'pending'
      delete settings.successFilter
      saveSettings()
    } else if (typeof settings.activeTab === 'string' && (settings.activeTab === 'pending' || settings.activeTab === 'done')) {
      activeTab.value = settings.activeTab
    }
    if (Array.isArray(settings.visibleColumnKeys)) {
      // 只保留有效的 key，确保名称列始终在内
      const valid = settings.visibleColumnKeys.filter((k: string) =>
        configurableKeys.includes(k),
      )
      if (!valid.includes("transfer_record.srcname")) {
        valid.push("transfer_record.srcname")
      }
      visibleColumnKeys.value = valid
    }
    if (Array.isArray(settings.sortBy) && settings.sortBy.length > 0
        && typeof settings.sortBy[0]?.key === 'string'
        && typeof settings.sortBy[0]?.order === 'string') {
      sortBy.value = settings.sortBy
    }
    if (typeof settings.itemsPerPage === "number" && settings.itemsPerPage > 0) {
      recordStore.itemsPerPage = settings.itemsPerPage
    }
  } catch {
    // 解析失败时静默忽略，使用默认值
  }
}

async function initial() {
  await loadData()
}

const showSelectedRecord = (item: any) => {
  recordStore.showUpdateRecord(item)
}

const rerunThisRecord = (item: any) => {
  taskStore.runTaskByIdWithPath(
    item.transfer_record.task_id,
    item.transfer_record.srcpath,
  )
}

const handleDelete = () => {
  if (selected.value.length === 0) return
  deleteDialog.value = true
}

const confirmDelete = async () => {
  await recordStore.deleteRecords(selected.value, forceDelete.value)
  deleteDialog.value = false
  forceDelete.value = false
  selected.value = []
  // 重新加载以刷新列表（loadData 读取当前 activeTab/searchQuery/sortBy，上下文保持）
  await loadData(recordStore.currentPage, recordStore.itemsPerPage)
}

const handleRetry = () => {
  if (selected.value.length === 0) return
  retryDialog.value = true
}

const confirmRetry = async () => {
  await recordStore.retryRecords(selected.value)
  retryDialog.value = false
  selected.value = []
  await loadData(recordStore.currentPage, recordStore.itemsPerPage)
}

// 更新 watch 函数以实现搜索功能，添加防抖
watch([searchQuery, taskIdQuery, activeTab], () => {
  // 清除之前的定时器
  if (searchTimeout.value) {
    clearTimeout(searchTimeout.value)
  }

  // 设置新的定时器，300ms 后执行搜索
  searchTimeout.value = setTimeout(() => {
    selected.value = [] // 清空选中项
    loadData(1, recordStore.itemsPerPage) // 回到第一页，保持当前每页数量
  }, 300) as unknown as number
})

// 持久化视图设置（在 settings 加载完成后才激活）
watch(
  [activeTab, visibleColumnKeys, sortBy],
  () => {
    if (settingsLoaded) {
      saveSettings()
    }
  },
  { deep: true },
)

watch(
  () => recordStore.itemsPerPage,
  () => {
    if (settingsLoaded) {
      saveSettings()
    }
  },
)

const handleClearSearch = () => {
  searchQuery.value = ""
  taskIdQuery.value = ""
  // watcher 防抖会自动触发 loadData，无需直接调用
}

const openScrapeLogDrawer = (item: any) => {
  currentScrapeLogRecordId.value = item.transfer_record.id
  scrapeLogDrawerOpen.value = true
}

// 处理排序变化
const handleSortChange = (newSortBy: any) => {
  sortBy.value = newSortBy
  loadData(recordStore.currentPage, recordStore.itemsPerPage)
}

// 行属性（用于标记已删除行的样式）
const rowProps = ({ item }: { item: any }) => {
  const isDeleted = item.transfer_record.deleted || item.transfer_record.srcdeleted
  return isDeleted ? { class: 'deleted-row' } : {}
}

onBeforeUnmount(() => {
  // 清除搜索防抖定时器
  if (searchTimeout.value) {
    clearTimeout(searchTimeout.value)
    searchTimeout.value = null
  }
  // 使进行中的请求失效
  requestGeneration.value++
  if (refreshTimer.value) {
    clearTimeout(refreshTimer.value)
    refreshTimer.value = null
  }
})

onMounted(() => {
  loadSettings()
  settingsLoaded = true
  initial()
})
</script>

<template>
  <p class="text-xl mb-6">
    {{ t('pages.records.title') }}
  </p>
  <VCard>
    <v-tabs v-model="activeTab" color="primary" density="comfortable">
      <v-tab value="pending">
        <v-icon start>mdi-alert-circle-outline</v-icon>
        {{ t('pages.records.tabs.pending') }}
      </v-tab>
      <v-tab value="done">
        <v-icon start>mdi-check-circle-outline</v-icon>
        {{ t('pages.records.tabs.done') }}
      </v-tab>
    </v-tabs>
    <v-divider />
    <div class="search-toolbar px-4 py-4">
      <div class="d-flex align-center justify-space-between flex-wrap gap-4">
        <div class="search-fields d-flex gap-4 align-center flex-grow-1 flex-wrap">
          <v-text-field v-model="searchQuery" :placeholder="t('pages.records.search')" hide-details density="comfortable"
            class="search-input" prepend-inner-icon="mdi-magnify" clearable
            @click:clear="searchQuery = ''; loadData(1, recordStore.itemsPerPage)" />

          <v-text-field v-model="taskIdQuery" :placeholder="t('pages.records.filterTaskId')" hide-details density="comfortable"
            class="task-id-input" prepend-inner-icon="mdi-pound" clearable type="number"
            @click:clear="taskIdQuery = ''; loadData(1, recordStore.itemsPerPage)" />
        </div>
        
        <div class="d-flex align-center gap-2">
          <!-- 列选择 -->
          <v-menu :close-on-content-click="false" location="bottom end">
            <template v-slot:activator="{ props }">
              <v-btn v-bind="props" size="small" variant="tonal" color="secondary"
                prepend-icon="mdi-view-column">
                {{ t('pages.records.columnSettings') }}
              </v-btn>
            </template>
            <v-list density="compact" class="py-1" min-width="180">
              <v-list-item v-for="header in allHeaders" :key="header.key" class="px-2">
                <v-checkbox v-model="visibleColumnKeys" :value="header.key" :label="header.title"
                  :disabled="header.alwaysVisible" hide-details density="compact" color="primary" />
              </v-list-item>
            </v-list>
          </v-menu>
          <!-- 刷新状态和控件 -->
          <div class="refresh-controls d-flex align-center">
            <v-tooltip :text="autoRefresh ? t('pages.records.refreshOn') : t('pages.records.refreshOff')">
              <template v-slot:activator="{ props }">
                <v-btn icon v-bind="props" :color="autoRefresh ? 'success' : 'grey'" @click="toggleAutoRefresh" size="small">
                  <v-icon>{{ autoRefresh ? 'mdi-sync' : 'mdi-sync-off' }}</v-icon>
                </v-btn>
              </template>
            </v-tooltip>
            
            <v-tooltip :text="t('pages.records.manualRefresh')">
              <template v-slot:activator="{ props }">
                <v-btn icon v-bind="props" color="primary" @click="manualRefresh" size="small" class="ml-1" 
                  :disabled="recordStore.loading" :loading="recordStore.loading">
                  <v-icon>mdi-refresh</v-icon>
                </v-btn>
              </template>
            </v-tooltip>
            
            <v-chip v-if="hasNewData" color="warning" size="small" class="ml-2" @click="manualRefresh">
              <v-icon start size="x-small" class="mr-1">mdi-alert</v-icon>
              {{ t('pages.records.newData') }}
            </v-chip>
            
            <div v-if="autoRefresh && lastRefreshTime && !hasNewData" class="refresh-counter text-grey text-caption ml-2">
              {{ t('pages.records.nextRefresh', { seconds: refreshCountdown }) }}
            </div>
          </div>
          
          <v-btn color="warning" :disabled="selected.length === 0" prepend-icon="mdi-refresh" @click="handleRetry"
            size="default" class="retry-btn">
            {{ t('pages.records.retrySelected', { count: selected.length }) }}
          </v-btn>

          <v-btn color="error" :disabled="selected.length === 0" prepend-icon="mdi-delete" @click="handleDelete"
            size="default" class="delete-btn">
            {{ t('pages.records.deleteSelected', { count: selected.length }) }}
          </v-btn>
        </div>
      </div>

      <div class="search-filters mt-2 mb-1 d-flex flex-wrap align-center gap-2" v-if="searchQuery || taskIdQuery">
        <v-chip v-if="searchQuery" color="primary" size="default" variant="elevated" class="search-chip">
          <v-icon start size="small" class="mr-1">mdi-magnify</v-icon>
          {{ t('pages.records.nameFilter') }}: {{ searchQuery }}
          <template v-slot:append>
            <v-icon size="small" @click="searchQuery = ''; loadData(1, recordStore.itemsPerPage)">mdi-close</v-icon>
          </template>
        </v-chip>

        <v-chip v-if="taskIdQuery" color="info" size="default" variant="elevated" class="search-chip">
          <v-icon start size="small" class="mr-1">mdi-pound</v-icon>
          {{ t('pages.records.taskIdFilter') }}: {{ taskIdQuery }}
          <template v-slot:append>
            <v-icon size="small" @click="taskIdQuery = ''; loadData(1, recordStore.itemsPerPage)">mdi-close</v-icon>
          </template>
        </v-chip>

        <v-btn v-if="searchQuery || taskIdQuery" icon="mdi-close-circle" size="small" color="error" variant="text"
          @click="handleClearSearch" class="ml-1 clear-all-btn">
          <v-tooltip activator="parent" location="top">{{ t('pages.records.clearFilters') }}</v-tooltip>
        </v-btn>
      </div>
    </div>

    <v-data-table v-model="selected" :headers="displayedHeaders" :items="recordStore.records" item-value="transfer_record.id"
      show-select :loading="recordStore.loading" :sort-by="sortBy" height="auto" :items-per-page="-1"
      :row-props="rowProps"
      @update:sort-by="handleSortChange">
      <!-- 名称列 -->
      <template v-slot:item.transfer_record.srcname="{ item }">
        <v-tooltip :text="item.transfer_record.srcpath">
          <template v-slot:activator="{ props }">
            <span v-bind="props" class="text-truncate d-inline-block" style="max-width: 230px">
              {{ item.transfer_record.srcname }}
            </span>
          </template>
        </v-tooltip>
      </template>

      <!-- 状态列 -->
      <template v-slot:item.transfer_record.success="{ item }">
        <!-- 成功 -->
        <v-chip
          v-if="item.transfer_record.success === true"
          color="success"
          variant="flat"
          size="small"
          class="status-chip">
          <v-icon icon="bx-check" size="small" />
        </v-chip>
        <!-- 失败 -->
        <v-chip
          v-else-if="item.transfer_record.success === false"
          color="error"
          variant="flat"
          size="small"
          class="status-chip">
          <v-icon icon="bx-x" size="small" />
        </v-chip>
        <!-- 中断 (null) -->
        <v-tooltip v-else :text="t('pages.records.interruptedStatus')">
          <template v-slot:activator="{ props }">
            <v-chip
              v-bind="props"
              color="grey"
              variant="flat"
              size="small"
              class="status-chip">
              <v-icon icon="mdi-alert" size="small" />
            </v-chip>
          </template>
        </v-tooltip>
      </template>

      <!-- 文件大小列 -->
      <template v-slot:item.transfer_record.filesize="{ item }">
        <span class="text-no-wrap">{{ formatFileSize(item.transfer_record.filesize) }}</span>
      </template>

      <!-- 目标路径列 -->
      <template v-slot:item.transfer_record.destpath="{ item }">
        <v-tooltip :text="item.transfer_record.destpath || ''">
          <template v-slot:activator="{ props }">
            <span v-bind="props" class="text-truncate d-inline-block" style="max-width: 180px"
              :class="{ 'text-decoration-line-through': item.transfer_record.deleted }">
              {{ item.transfer_record.destpath || '' }}
            </span>
          </template>
        </v-tooltip>
      </template>

      <!-- 季列 -->
      <template v-slot:item.transfer_record.season="{ item }">
        {{ item.transfer_record.season === -1 ? '' : item.transfer_record.season }}
      </template>

      <!-- 集列 -->
      <template v-slot:item.transfer_record.episode="{ item }">
        {{ item.transfer_record.episode === -1 ? '' : item.transfer_record.episode }}
      </template>

      <!-- 编号列 -->
      <template v-slot:item.extra_info.number="{ item }">
        {{ item.extra_info?.number || '' }}
      </template>

      <!-- 标签列 -->
      <template v-slot:item.extra_info.tag="{ item }">
        <div v-if="item.extra_info?.tag" class="d-flex gap-1 flex-wrap">
          <v-chip v-for="tag in item.extra_info.tag.split(',')" :key="tag" :color="getTagColor(tag)" variant="flat"
            class="tag-chip" size="small">
            {{ tag.trim() }}
          </v-chip>
        </div>
      </template>

      <!-- 创建时间列 -->
      <template v-slot:item.transfer_record.createtime="{ item }">
        {{ formatDateTime(item.transfer_record.createtime) }}
      </template>

      <!-- 更新时间列 -->
      <template v-slot:item.transfer_record.updatetime="{ item }">
        {{ formatDateTime(item.transfer_record.updatetime) }}
      </template>

      <!-- 截止时间列 -->
      <template v-slot:item.transfer_record.deadtime="{ item }">
        {{ formatDateTime(item.transfer_record.deadtime) }}
      </template>

      <!-- 操作列 -->
      <template v-slot:item.actions="{ item }">
        <div class="d-flex align-center gap-2">
          <VBtn size="small" variant="text" @click="openScrapeLogDrawer(item)">
            <VIcon icon="mdi-file-document-outline" start />
            {{ t('pages.records.viewScrapeLog') }}
          </VBtn>
          <VBtn type="submit" size="small" @click="showSelectedRecord(item)">
            <VIcon icon="bx-edit-alt" />
          </VBtn>
          <VBtn type="submit" size="small" @click="rerunThisRecord(item)">
            <VIcon icon="bx-refresh" />
          </VBtn>
        </div>
      </template>

      <!-- 自定义底部分页 -->
      <template v-slot:bottom>
        <div class="d-flex align-center justify-end px-4 py-3 w-100">
          <div class="d-flex align-center me-4">
            <span class="text-caption text-grey me-2">{{ t('pages.records.itemsPerPage') }}</span>
            <v-select :model-value="recordStore.itemsPerPage" :items="pageSizeOptions" density="compact"
              style="width: 80px" hide-details variant="plain" @update:model-value="handleItemsPerPageChange" />
            <div class="ms-4 text-caption text-grey">
              {{ t('pages.records.totalRecords', { count: recordStore.totalRecords }) }}
            </div>
          </div>

          <v-pagination v-model="recordStore.currentPage"
            :length="Math.ceil(recordStore.totalRecords / recordStore.itemsPerPage)"
            @update:model-value="handlePageChange" :total-visible="5" :show-first-last-page="false" />
        </div>
      </template>
    </v-data-table>
  </VCard>

  <RecordDetailDialog />

  <!-- 删除确认对话框 -->
  <VDialog v-model="deleteDialog" max-width="500">
    <VCard>
      <VCardTitle class="text-h5">
        {{ t('pages.records.deleteDialog.title') }}
      </VCardTitle>
      <VCardText>
        {{ t('pages.records.deleteDialog.message', { count: selected.length }) }}
        <VCheckbox v-model="forceDelete" :label="t('pages.records.deleteDialog.forceDelete')" class="mt-4" />
      </VCardText>
      <VCardActions>
        <VSpacer />
        <VBtn color="primary" variant="text" @click="deleteDialog = false">
          {{ t('pages.records.deleteDialog.cancel') }}
        </VBtn>
        <VBtn color="error" @click="confirmDelete">
          {{ t('pages.records.deleteDialog.confirm') }}
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>

  <!-- 重试确认对话框 -->
  <VDialog v-model="retryDialog" max-width="500">
    <VCard>
      <VCardTitle class="text-h5">
        {{ t('pages.records.retryDialog.title') }}
      </VCardTitle>
      <VCardText>
        {{ t('pages.records.retryDialog.message', { count: selected.length }) }}
      </VCardText>
      <VCardActions>
        <VSpacer />
        <VBtn color="primary" variant="text" @click="retryDialog = false">
          {{ t('pages.records.retryDialog.cancel') }}
        </VBtn>
        <VBtn color="warning" @click="confirmRetry">
          {{ t('pages.records.retryDialog.confirm') }}
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>

  <ScrapeLogDrawer v-model="scrapeLogDrawerOpen" :record-id="currentScrapeLogRecordId" />
</template>

<style scoped>
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tag-chip {
  font-size: 12px;
  height: 20px;
  padding: 0 4px;
  min-width: 0;
  min-height: 0;
}

.v-chip.tag-chip .v-chip__content {
  padding: 0;
  line-height: 20px;
}

.status-chip {
  min-width: 32px;
  width: 32px;
  height: 24px;
  justify-content: center;
}

.max-w-xs {
  max-width: 300px;
}

.deleted-row {
  color: #9e9e9e;
  opacity: 0.85;
}

.max-w-taskid {
  max-width: 150px;
}

.search-toolbar {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.v-tabs {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.search-fields {
  flex-wrap: wrap;
  min-width: 0;
}

.search-input {
  max-width: 350px;
  min-width: 250px;
}

.task-id-input {
  max-width: 180px;
  min-width: 150px;
}

.status-select {
  max-width: 140px;
  min-width: 120px;
}

.delete-btn {
  white-space: nowrap;
}

.retry-btn {
  white-space: nowrap;
}

.search-filters {
  min-height: 36px;
}

.search-chip {
  height: 32px;
  font-size: 14px;
}

.clear-all-btn {
  margin-left: 4px;
}

@media (max-width: 768px) {
  .search-input, .task-id-input, .status-select {
    min-width: 0;
    width: 100%;
  }
  
  .delete-btn {
    margin-top: 8px;
    width: 100%;
  }
}

/* ... existing responsive adjustments ... */

.refresh-controls {
  white-space: nowrap;
}

.refresh-counter {
  min-width: 100px;
}

@media (max-width: 768px) {
  /* ... existing responsive styles ... */
  
  .refresh-controls {
    width: 100%;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  
  .refresh-counter {
    text-align: right;
  }
}
</style>
