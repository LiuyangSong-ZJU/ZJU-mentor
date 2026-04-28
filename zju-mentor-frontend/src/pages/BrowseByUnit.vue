<script setup>
import { onMounted, ref } from 'vue'
import SiteFooter from '../components/SiteFooter.vue'
import PageTopBar from '../components/PageTopBar.vue'
import TeacherSearchPanel from '../components/TeacherSearchPanel.vue'

const unitGroups = ref([])
const isLoading = ref(true)
const errorMessage = ref('')
const showSearchPanel = ref(false)

const loadUnitGroups = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await fetch('/api/units')

    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`)
    }

    const payload = await response.json()
    unitGroups.value = payload.groups ?? []
  } catch (error) {
    errorMessage.value = '加载单位列表失败。请先启动本地 API 服务。'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadUnitGroups()
})
</script>

<template>
  <div class="min-h-screen bg-gradient-to-b from-slate-50 via-white to-rose-50/30 p-6 flex flex-col">
    <PageTopBar @search-click="showSearchPanel = !showSearchPanel" />

    <div v-if="showSearchPanel" class="mx-auto mb-5 w-full max-w-5xl">
      <TeacherSearchPanel placeholder="搜索导师名字..." />
    </div>

    <main class="mx-auto w-full max-w-5xl flex-1">
      <h1 class="mb-6 text-3xl font-bold text-slate-800">按单位浏览</h1>

      <div v-if="isLoading" class="rounded-2xl border border-slate-200 bg-white p-6 text-slate-500 shadow-sm">
        正在加载单位列表...
      </div>

      <div v-else-if="errorMessage" class="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 shadow-sm">
        {{ errorMessage }}
      </div>

      <div v-else class="flex flex-col gap-5">
        <section
          v-for="group in unitGroups"
          :key="group.bigUnitName"
          class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h2 class="mb-3 text-xl font-semibold text-slate-800">{{ group.bigUnitName }}</h2>

          <div class="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <RouterLink
              v-for="college in group.colleges"
              :key="college.collegeId"
              :to="`/browse/unit/${college.collegeId}`"
              class="text-blue-600 hover:text-blue-700 hover:underline"
            >
              {{ college.collegeName }}
            </RouterLink>
          </div>
        </section>
      </div>
    </main>

    <SiteFooter />
  </div>
</template>