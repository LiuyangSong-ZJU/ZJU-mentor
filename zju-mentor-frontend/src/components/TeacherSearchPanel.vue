<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'

const props = defineProps({
  placeholder: {
    type: String,
    default: '搜索导师名字...'
  }
})

const searchText = ref('')
const suggestions = ref([])
const showSuggestionPanel = ref(false)
const hasSearched = ref(false)
const exactMatches = ref([])
const fuzzyMatches = ref([])
let suggestionTimer = null

const teacherLink = uid => `/mentor/${encodeURIComponent(uid)}`
const unitLink = collegeId => `/browse/unit/${collegeId}`

const secondaryMatches = computed(() => [
  ...exactMatches.value.slice(1),
  ...fuzzyMatches.value
])

const loadSuggestions = async keyword => {
  const q = keyword.trim()
  if (!q) {
    suggestions.value = []
    showSuggestionPanel.value = false
    return
  }

  try {
    const response = await fetch(`/api/teachers/suggest?q=${encodeURIComponent(q)}`)
    if (!response.ok) {
      throw new Error(`请求失败: ${response.status}`)
    }

    const payload = await response.json()
    suggestions.value = payload.suggestions ?? []
    showSuggestionPanel.value = suggestions.value.length > 0
  } catch (error) {
    suggestions.value = []
    showSuggestionPanel.value = false
  }
}

const doSearch = async () => {
  const q = searchText.value.trim()
  hasSearched.value = Boolean(q)
  showSuggestionPanel.value = false

  if (!q) {
    exactMatches.value = []
    fuzzyMatches.value = []
    return
  }

  try {
    const response = await fetch(`/api/teachers/search?q=${encodeURIComponent(q)}`)
    if (!response.ok) {
      throw new Error(`请求失败: ${response.status}`)
    }

    const payload = await response.json()
    exactMatches.value = payload.exactMatches ?? []
    fuzzyMatches.value = payload.fuzzyMatches ?? []
  } catch (error) {
    exactMatches.value = []
    fuzzyMatches.value = []
  }
}

const handleEnter = event => {
  if (event?.isComposing) {
    return
  }

  doSearch()
}

const pickSuggestion = teacher => {
  searchText.value = teacher.name
  doSearch()
}

watch(searchText, value => {
  if (suggestionTimer) {
    clearTimeout(suggestionTimer)
  }

  suggestionTimer = setTimeout(() => {
    loadSuggestions(value)
  }, 180)
})

onBeforeUnmount(() => {
  if (suggestionTimer) {
    clearTimeout(suggestionTimer)
  }
})
</script>

<template>
  <div class="w-full">
    <div class="relative">
      <div class="flex items-center justify-center gap-3">
        <el-input
          v-model="searchText"
          :placeholder="placeholder"
          class="flex-1 min-w-0"
          size="large"
          @keydown.enter.prevent="handleEnter"
          @focus="showSuggestionPanel = suggestions.length > 0"
          @blur="() => setTimeout(() => { showSuggestionPanel = false }, 120)"
        />
        <el-button type="primary" :icon="Search" size="large" @click="doSearch">搜索</el-button>
      </div>

      <div
        v-if="showSuggestionPanel"
        class="absolute left-0 right-0 z-40 mt-2 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
      >
        <button
          v-for="teacher in suggestions"
          :key="teacher.uid"
          type="button"
          class="flex w-full items-center justify-between border-b border-slate-100 px-4 py-3 text-left last:border-b-0 hover:bg-slate-50"
          @mousedown.prevent
          @click="pickSuggestion(teacher)"
        >
          <span class="font-medium text-slate-800">{{ teacher.name }}</span>
          <span class="text-xs text-slate-400">{{ teacher.workTitle }}</span>
        </button>
      </div>
    </div>

    <div v-if="hasSearched" class="mt-5">
      <div
        v-if="exactMatches.length > 0"
        class="mb-4 rounded-3xl border border-blue-100 bg-gradient-to-br from-blue-50 via-white to-sky-50 p-6 shadow-sm"
      >
        <div class="mb-2 text-xs font-semibold uppercase tracking-[0.24em] text-blue-700">精确匹配</div>
        <RouterLink :to="teacherLink(exactMatches[0].uid)" class="text-3xl font-black text-slate-900 hover:text-blue-700">
          {{ exactMatches[0].name }}
        </RouterLink>
        <div class="mt-2 text-base text-slate-500">{{ exactMatches[0].workTitle || '未标注职称' }}</div>
        <div class="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-500">
          <RouterLink
            v-for="college in exactMatches[0].colleges"
            :key="college.collegeId"
            :to="unitLink(college.collegeId)"
            class="rounded-full bg-white px-3 py-1 text-blue-600 shadow-sm ring-1 ring-blue-100 hover:underline"
          >
            {{ college.collegeName }}
          </RouterLink>
          <span v-if="exactMatches[0].colleges.length === 0" class="text-sm text-slate-400">未标注单位</span>
        </div>
      </div>

      <div
        v-if="secondaryMatches.length > 0"
        class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
      >
        <div class="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-500">
          {{ exactMatches.length > 0 ? '其他匹配结果' : '匹配结果' }}
        </div>

        <div class="divide-y divide-slate-100">
          <div
            v-for="teacher in secondaryMatches"
            :key="teacher.uid"
            class="px-4 py-3 transition-colors hover:bg-slate-50"
          >
            <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm text-slate-500">
              <RouterLink :to="teacherLink(teacher.uid)" class="text-base font-semibold text-slate-800 hover:text-blue-700 hover:underline">
                {{ teacher.name }}
              </RouterLink>

              <span v-if="teacher.workTitle" class="text-xs text-slate-400">{{ teacher.workTitle }}</span>

              <span class="text-slate-300">|</span>

              <template v-if="teacher.colleges.length > 0">
                <template
                  v-for="(college, index) in teacher.colleges"
                  :key="`${teacher.uid}-${college.collegeId}`"
                >
                  <RouterLink
                    :to="unitLink(college.collegeId)"
                    class="text-xs text-blue-600 hover:text-blue-700 hover:underline"
                  >
                    {{ college.collegeName }}
                  </RouterLink>
                  <span v-if="index !== teacher.colleges.length - 1" class="text-xs text-slate-300">/</span>
                </template>
              </template>

              <span v-else class="text-xs text-slate-400">未标注单位</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="exactMatches.length === 0 && fuzzyMatches.length === 0" class="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
        没有找到匹配的导师。
      </div>
    </div>
  </div>
</template>
