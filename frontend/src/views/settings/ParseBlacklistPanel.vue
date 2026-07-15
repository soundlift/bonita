<script setup lang="ts">
import { useSettingStore } from "@/stores/setting.store"
import { useI18n } from "vue-i18n"
import { ref, onMounted } from "vue"
import type { ParseBlacklistItem } from "@/client/types.gen"

const settingStore = useSettingStore()
const { t } = useI18n()

// 本地编辑副本（保存前不直接写 store）
const editList = ref<ParseBlacklistItem[]>([])

// 新增规则临时表单
const newMode = ref("literal")
const newValue = ref("")
const showAddForm = ref(false)

// 预览
const previewInput = ref("")
const previewResult = ref<{ cleaned_filename: string; parsed_number: string | null } | null>(null)
const previewLoading = ref(false)

const loadBlacklist = async () => {
  await settingStore.fetchParseBlacklist()
  editList.value = JSON.parse(JSON.stringify(settingStore.parseBlacklist))
}

const addRule = () => {
  if (!newValue.value.trim()) return
  editList.value.push({
    id: Date.now().toString(),
    mode: newMode.value,
    value: newValue.value.trim(),
    enabled: true,
  })
  newValue.value = ""
  newMode.value = "literal"
  showAddForm.value = false
}

const removeRule = (index: number) => {
  editList.value.splice(index, 1)
}

const toggleRule = (item: ParseBlacklistItem) => {
  item.enabled = !item.enabled
}

const saveBlacklist = async () => {
  await settingStore.updateParseBlacklist(editList.value)
}

const doPreview = async () => {
  if (!previewInput.value.trim()) return
  previewLoading.value = true
  try {
    const result = await settingStore.previewParse(previewInput.value, editList.value)
    previewResult.value = result
  } finally {
    previewLoading.value = false
  }
}

onMounted(() => {
  loadBlacklist()
})
</script>

<template>
  <VRow>
    <VCol cols="12" md="8">
      <!-- 说明 -->
      <VCard class="mb-6">
        <VCardTitle>{{ t('pages.settings.parseBlacklist.title') }}</VCardTitle>
        <VCardText>
          <p class="text-body-2 text-grey">{{ t('pages.settings.parseBlacklist.description') }}</p>
        </VCardText>
      </VCard>

      <!-- 黑名单列表 -->
      <VCard class="mb-6">
        <VCardTitle class="d-flex align-center justify-space-between">
          <span>{{ t('pages.settings.parseBlacklist.ruleList') }}</span>
          <VBtn color="primary" size="small" prepend-icon="mdi-plus" @click="showAddForm = !showAddForm">
            {{ t('pages.settings.parseBlacklist.addRule') }}
          </VBtn>
        </VCardTitle>
        <VCardText>
          <!-- 新增表单 -->
          <VRow v-if="showAddForm" class="mb-4">
            <VCol cols="12" md="4">
              <VSelect
                v-model="newMode"
                :items="[
                  { title: t('pages.settings.parseBlacklist.literal'), value: 'literal' },
                  { title: t('pages.settings.parseBlacklist.regex'), value: 'regex' },
                ]"
                :label="t('pages.settings.parseBlacklist.mode')"
                density="compact"
                hide-details
              />
            </VCol>
            <VCol cols="12" md="6">
              <VTextField
                v-model="newValue"
                :label="t('pages.settings.parseBlacklist.value')"
                density="compact"
                hide-details
                @keyup.enter="addRule"
              />
            </VCol>
            <VCol cols="12" md="2">
              <VBtn color="success" size="small" block @click="addRule">
                {{ t('pages.settings.parseBlacklist.confirmAdd') }}
              </VBtn>
            </VCol>
          </VRow>

          <!-- 规则列表 -->
          <div v-if="editList.length === 0" class="text-center text-grey py-4">
            {{ t('pages.settings.parseBlacklist.empty') }}
          </div>
          <VTable v-else density="compact">
            <thead>
              <tr>
                <th>{{ t('pages.settings.parseBlacklist.mode') }}</th>
                <th>{{ t('pages.settings.parseBlacklist.value') }}</th>
                <th class="text-center">{{ t('pages.settings.parseBlacklist.enabled') }}</th>
                <th class="text-center">{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in editList" :key="item.id">
                <td>
                  <VChip :color="item.mode === 'regex' ? 'info' : 'default'" size="small">
                    {{ item.mode === 'regex' ? t('pages.settings.parseBlacklist.regex') : t('pages.settings.parseBlacklist.literal') }}
                  </VChip>
                </td>
                <td class="font-monospace">{{ item.value }}</td>
                <td class="text-center">
                  <VSwitch
                    :model-value="item.enabled"
                    @update:model-value="toggleRule(item)"
                    color="success"
                    density="compact"
                    hide-details
                    inset
                  />
                </td>
                <td class="text-center">
                  <VBtn icon="mdi-delete" size="x-small" variant="text" color="error" @click="removeRule(idx)" />
                </td>
              </tr>
            </tbody>
          </VTable>
        </VCardText>
        <VCardActions v-if="editList.length > 0">
          <VSpacer />
          <VBtn color="primary" @click="saveBlacklist">
            {{ t('pages.settings.parseBlacklist.save') }}
          </VBtn>
        </VCardActions>
      </VCard>

      <!-- 预览 -->
      <VCard>
        <VCardTitle>{{ t('pages.settings.parseBlacklist.preview') }}</VCardTitle>
        <VCardText>
          <VTextField
            v-model="previewInput"
            :placeholder="t('pages.settings.parseBlacklist.previewPlaceholder')"
            density="compact"
            hide-details
            class="mb-3"
            append-inner-icon="mdi-magnify"
            @click:append-inner="doPreview"
            @keyup.enter="doPreview"
          />
          <div v-if="previewResult" class="mt-2">
            <div class="text-body-2 mb-1">
              <span class="text-grey">{{ t('pages.settings.parseBlacklist.cleanedResult') }}:</span>
              <span class="font-monospace ml-2">{{ previewResult.cleaned_filename || '(empty)' }}</span>
            </div>
            <div class="text-body-2">
              <span class="text-grey">{{ t('pages.settings.parseBlacklist.parsedResult') }}:</span>
              <span class="font-weight-bold ml-2" :class="previewResult.parsed_number ? 'text-success' : 'text-error'">
                {{ previewResult.parsed_number || t('pages.settings.parseBlacklist.parseFailed') }}
              </span>
            </div>
          </div>
        </VCardText>
      </VCard>
    </VCol>
  </VRow>
</template>
