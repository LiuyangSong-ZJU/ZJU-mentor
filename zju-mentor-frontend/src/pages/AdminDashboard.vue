<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import SiteFooter from '../components/SiteFooter.vue'
import { adminFetch, clearAdminToken } from '../utils/adminAuth'

const router = useRouter()

const searchText = ref('')
const sortBy = ref('reviews')
const teachers = ref([])
const isLoading = ref(true)
const errorMessage = ref('')

const totalTeachers = computed(() => teachers.value.length)

const loadRankings = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await adminFetch(`/api/admin/teachers?sort=${encodeURIComponent(sortBy.value)}&q=${encodeURIComponent(searchText.value.trim())}`)
    const payload = await response.json()
    if (response.status === 401) {
      clearAdminToken()
      router.replace({
        path: '/__admin__/login',
        query: { redirect: '/__admin__' }
      })
      return
    }

    if (!response.ok) {
      throw new Error(payload.message || `请求失败：${response.status}`)
    }

    teachers.value = payload.teachers ?? []
  } catch (error) {
    errorMessage.value = error.message || '加载老师排行失败。'
  } finally {
    isLoading.value = false
  }
}

const openTeacher = uid => {
  router.push(`/__admin__/teacher/${encodeURIComponent(uid)}`)
}

const logout = () => {
  clearAdminToken()
  router.replace('/__admin__/login')
}

onMounted(() => {
  loadRankings()
})
</script>

<template>
  <div class="flex min-h-screen flex-col bg-gradient-to-b from-slate-50 via-white to-slate-100 p-6">
    <main class="mx-auto w-full max-w-6xl flex-1">
      <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div class="text-sm font-semibold uppercase tracking-[0.22em] text-slate-400">Admin Console</div>
          <h1 class="mt-2 text-3xl font-black text-slate-900">后台管理</h1>
          <p class="mt-2 text-sm text-slate-500">按评论数、平均分或快跑数排序，进入老师页删除评论和链接。</p>
        </div>

        <el-button @click="logout">退出后台</el-button>
      </div>

      <section class="mb-6 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_120px]">
          <el-input
            v-model="searchText"
            size="large"
            placeholder="搜索老师、职称或单位"
            @keydown.enter.prevent="loadRankings"
          />
          <el-select v-model="sortBy" size="large">
            <el-option label="按评论数" value="reviews" />
            <el-option label="按平均分" value="score" />
            <el-option label="按快跑数" value="runaway" />
          </el-select>
          <el-button type="primary" size="large" @click="loadRankings">刷新排行</el-button>
        </div>
      </section>

      <div v-if="isLoading" class="rounded-2xl border border-slate-200 bg-white p-6 text-slate-500 shadow-sm">
        正在加载后台列表...
      </div>

      <div v-else-if="errorMessage" class="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 shadow-sm">
        {{ errorMessage }}
      </div>

      <template v-else>
        <div class="mb-4 text-sm text-slate-500">共 {{ totalTeachers }} 位老师</div>

        <div class="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div class="grid grid-cols-[minmax(0,1.2fr)_130px_130px_130px] gap-4 border-b border-slate-100 px-5 py-4 text-sm font-semibold text-slate-500">
            <div>老师</div>
            <div class="text-right">评论数</div>
            <div class="text-right">平均分</div>
            <div class="text-right">快跑数</div>
          </div>

          <button
            v-for="teacher in teachers"
            :key="teacher.uid"
            type="button"
            class="grid w-full grid-cols-[minmax(0,1.2fr)_130px_130px_130px] gap-4 border-b border-slate-100 px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-slate-50"
            @click="openTeacher(teacher.uid)"
          >
            <div class="min-w-0">
              <div class="truncate text-base font-semibold text-slate-800">{{ teacher.name }}</div>
              <div class="mt-1 text-sm text-slate-400">{{ teacher.workTitle || '未标注职称' }}</div>
              <div class="mt-1 truncate text-xs text-blue-600">
                {{ teacher.colleges.map(item => item.collegeName).join(' / ') || '未标注单位' }}
              </div>
            </div>
            <div class="text-right text-base font-semibold text-slate-700">{{ teacher.reviewCount }}</div>
            <div class="text-right text-base font-semibold text-slate-700">{{ teacher.averageScore.toFixed(1) }}</div>
            <div class="text-right text-base font-semibold text-rose-600">{{ teacher.runAwayVotes }}</div>
          </button>
        </div>
      </template>
    </main>

    <SiteFooter />
  </div>
</template>
