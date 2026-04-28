<script setup>
import { computed, onMounted, ref } from 'vue'
import SiteFooter from '../components/SiteFooter.vue'
import PageTopBar from '../components/PageTopBar.vue'
import TeacherSearchPanel from '../components/TeacherSearchPanel.vue'

const sections = ref([])
const isLoading = ref(true)
const errorMessage = ref('')
const showSearchPanel = ref(true)

const navLetters = Array.from('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

const sectionId = letter => (letter === '#' ? 'section-hash' : `section-${letter}`)

const loadNameSections = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await fetch('/api/teachers/by-name')

    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`)
    }

    const payload = await response.json()
    sections.value = payload.sections ?? []
  } catch (error) {
    errorMessage.value = '加载导师名单失败。请先启动本地 API 服务。'
  } finally {
    isLoading.value = false
  }
}

const availableLetters = computed(() => new Set(sections.value.map(section => section.letter)))

onMounted(() => {
  loadNameSections()
})
</script>

<template>
  <div class="min-h-screen bg-gradient-to-b from-slate-50 via-white to-rose-50/30 p-6 flex flex-col">
    <PageTopBar @search-click="showSearchPanel = !showSearchPanel" />

    <main class="mx-auto w-full max-w-6xl flex-1">
      <div class="mb-6 flex flex-col gap-4">
        <h1 class="text-3xl font-bold text-slate-800">按名字浏览</h1>

        <div v-if="showSearchPanel" class="w-full max-w-3xl">
          <TeacherSearchPanel placeholder="搜索导师名字..." />
        </div>
      </div>

      <div v-if="isLoading" class="rounded-2xl border border-slate-200 bg-white p-6 text-slate-500 shadow-sm">
        正在加载导师名单...
      </div>

      <div v-else-if="errorMessage" class="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 shadow-sm">
        {{ errorMessage }}
      </div>

      <div v-else class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_44px]">
        <div class="flex flex-col gap-5">
          <section
            v-for="section in sections"
            :id="sectionId(section.letter)"
            :key="section.letter"
            class="rounded-2xl border border-slate-200 bg-white shadow-sm"
          >
            <div class="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
              <div class="text-3xl font-black text-blue-700">{{ section.letter }}</div>
              <div class="h-px flex-1 bg-slate-200"></div>
            </div>

            <div class="divide-y divide-slate-100">
              <div
                v-for="teacher in section.teachers"
                :key="teacher.uid"
                class="px-5 py-3"
              >
                <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm text-slate-500">
                  <RouterLink :to="`/mentor/${encodeURIComponent(teacher.uid)}`" class="text-base font-semibold text-slate-800 hover:text-blue-700 hover:underline">
                    {{ teacher.name }}
                  </RouterLink>

                  <span v-if="teacher.workTitle" class="text-xs text-slate-400">{{ teacher.workTitle }}</span>

                  <span class="text-slate-300">|</span>

                  <template
                    v-for="(college, index) in teacher.colleges"
                    :key="college.collegeId"
                  >
                    <RouterLink
                      :to="`/browse/unit/${college.collegeId}`"
                      class="text-xs text-blue-600 hover:text-blue-700 hover:underline"
                    >
                      {{ college.collegeName }}
                    </RouterLink>
                    <span v-if="index !== teacher.colleges.length - 1" class="text-xs text-slate-300">/</span>
                  </template>
                  <span
                    v-if="teacher.colleges.length === 0"
                    class="text-xs text-slate-400"
                  >
                    未标注单位
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>

        <aside class="hidden lg:sticky lg:top-24 lg:flex lg:h-fit lg:flex-col lg:items-center lg:gap-1 lg:rounded-xl lg:border lg:border-slate-200 lg:bg-white lg:px-1.5 lg:py-2 lg:shadow-sm">
          <a
            v-for="letter in navLetters"
            :key="letter"
            :href="`#${sectionId(letter)}`"
            class="text-[11px] font-medium leading-none transition-colors"
            :class="availableLetters.has(letter) ? 'text-slate-600 hover:text-blue-700' : 'pointer-events-none text-slate-300'"
          >
            {{ letter }}
          </a>
          <a
            v-if="availableLetters.has('#')"
            :href="`#${sectionId('#')}`"
            class="pt-1 text-[11px] font-medium leading-none text-slate-600 transition-colors hover:text-blue-700"
          >
            #
          </a>
        </aside>
      </div>
    </main>

    <SiteFooter />
  </div>
</template>
