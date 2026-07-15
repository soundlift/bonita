<script lang="ts" setup>
import AccountSettingsSecurity from "@/views/settings/AccountSettingsSecurity.vue"
import ServiceSettingsPanel from "@/views/settings/ServiceSettingsPanel.vue"
import ParseBlacklistPanel from "@/views/settings/ParseBlacklistPanel.vue"
import { useI18n } from "vue-i18n"
import { ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const validTabs = ["security", "service", "parse"] as const
type TabValue = (typeof validTabs)[number]

const queryTab = route.query.tab as string
const initialTab = validTabs.includes(queryTab as TabValue) ? queryTab : "security"

const activeTab = ref<string>(initialTab)

// tab 切换时更新 URL query（不产生历史记录）
watch(activeTab, (newTab) => {
  if (newTab !== route.query.tab) {
    router.replace({ query: { ...route.query, tab: newTab } })
  }
})

// 外部路由变化时同步（如浏览器前进后退）
watch(
  () => route.query.tab,
  (newTab) => {
    if (typeof newTab === "string" && validTabs.includes(newTab as TabValue)) {
      activeTab.value = newTab
    }
  },
)

// tabs
const tabs = [
  {
    title: t("pages.settings.tabs.security"),
    icon: "bx-lock-open",
    tab: "security",
  },
  {
    title: t("pages.settings.tabs.service"),
    icon: "bxs-server",
    tab: "service",
  },
  {
    title: t("pages.settings.tabs.parse"),
    icon: "bxs-magic-wand",
    tab: "parse",
  },
]
</script>

<template>
  <div>
    <p class="text-xl mb-6">
      {{ t('pages.settings.title') }}
    </p>

    <VTabs v-model="activeTab" show-arrows class="v-tabs-pill">
      <VTab v-for="item in tabs" :key="item.tab" :value="item.tab">
        <VIcon size="20" start :icon="item.icon" />
        {{ item.title }}
      </VTab>
    </VTabs>

    <VWindow v-model="activeTab" class="mt-5 disable-tab-transition">
      <!-- 安全 -->
      <VWindowItem value="security">
        <AccountSettingsSecurity />
      </VWindowItem>

      <!-- 服务 -->
      <VWindowItem value="service">
        <ServiceSettingsPanel />
      </VWindowItem>

      <!-- 番号解析 -->
      <VWindowItem value="parse">
        <ParseBlacklistPanel />
      </VWindowItem>
    </VWindow>
  </div>
</template>
