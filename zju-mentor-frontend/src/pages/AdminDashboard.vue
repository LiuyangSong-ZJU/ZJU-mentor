<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import SiteFooter from '../components/SiteFooter.vue'
import { adminFetch, clearAdminToken } from '../utils/adminAuth'

const router = useRouter()

const searchText = ref('')
const sortBy = ref('reviews')
const teachers = ref([])
const feedbackItems = ref([])
const syncRuns = ref([])
const syncRunTotal = ref(0)
const syncStatusError = ref('')
const isLoading = ref(true)
const errorMessage = ref('')

const totalTeachers = computed(() => teachers.value.length)
const totalSyncRuns = computed(() => syncRunTotal.value)
const latestSyncRun = computed(() => syncRuns.value[0] || null)

const feedbackTypeLabel = item => item.feedbackType === 'error' ? '报告错误' : '反馈建议'
const syncStatusLabel = status => {
  if (status === 'success') {
    return '成功'
  }
  if (status === 'failed') {
    return '失败'
  }
  if (status === 'running') {
    return '运行中'
  }

  return status || '未知'
}

const formatDisplayDate = value => {
  if (!value) {
    return ''
  }

  return String(value).replace('T', ' ').slice(0, 16)
}

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

const loadFeedback = async () => {
  const response = await adminFetch('/api/admin/feedback')
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

  feedbackItems.value = payload.feedback ?? []
}

const loadSyncRuns = async () => {
  syncStatusError.value = ''

  try {
    const response = await adminFetch('/api/admin/sync/runs')
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

    syncRuns.value = payload.runs ?? []
    syncRunTotal.value = payload.total ?? syncRuns.value.length
  } catch (error) {
    syncStatusError.value = error.message || '加载同步状态失败。'
  }
}

const handleDeleteFeedback = async item => {
  try {
    await ElMessageBox.confirm('确认删除这条反馈吗？此操作不可撤销。', '删除反馈', {
      type: 'warning'
    })

    const response = await adminFetch(`/api/admin/feedback/${item.id}`, {
      method: 'DELETE'
    })
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

    feedbackItems.value = payload.feedback ?? []
    ElMessage.success('反馈已删除。')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除反馈失败。')
    }
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
  loadSyncRuns()
  loadFeedback().catch(error => {
    ElMessage.error(error.message || '加载反馈失败。')
  })
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
            <el-option label="按链接数" value="links" />
          </el-select>
          <el-button type="primary" size="large" @click="loadRankings">刷新排行</el-button>
        </div>
      </section>

      <section class="mb-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 class="text-lg font-bold text-slate-800">爬虫更新状态</h2>
            <p class="mt-1 text-xs text-slate-400">用于部署后快速确认自动/手动同步是否正常。</p>
          </div>
          <el-button @click="loadSyncRuns">刷新状态</el-button>
        </div>

        <div v-if="syncStatusError" class="mt-4 rounded-2xl border border-rose-100 bg-rose-50 p-4 text-sm text-rose-700">
          {{ syncStatusError }}
        </div>

        <div v-else class="mt-4 grid gap-3 md:grid-cols-3">
          <div class="rounded-2xl bg-slate-50 p-4">
            <div class="text-xs font-semibold text-slate-400">总更新次数</div>
            <div class="mt-2 text-2xl font-black text-slate-900">{{ totalSyncRuns }}</div>
          </div>

          <div class="rounded-2xl bg-slate-50 p-4">
            <div class="text-xs font-semibold text-slate-400">最近一次更新时间</div>
            <div class="mt-2 text-base font-bold text-slate-800">
              {{ latestSyncRun ? formatDisplayDate(latestSyncRun.finished_at || latestSyncRun.created_at) : '暂无记录' }}
            </div>
          </div>

          <div class="rounded-2xl bg-slate-50 p-4">
            <div class="text-xs font-semibold text-slate-400">最近一次状态</div>
            <div
              class="mt-2 inline-flex rounded px-2.5 py-1 text-sm font-bold"
              :class="{
                'bg-emerald-50 text-emerald-700': latestSyncRun?.status === 'success',
                'bg-rose-50 text-rose-700': latestSyncRun?.status === 'failed',
                'bg-amber-50 text-amber-700': latestSyncRun?.status === 'running',
                'bg-slate-100 text-slate-600': !latestSyncRun
              }"
            >
              {{ latestSyncRun ? syncStatusLabel(latestSyncRun.status) : '暂无记录' }}
            </div>
          </div>
        </div>

        <div v-if="latestSyncRun?.error_message" class="mt-4 rounded-2xl border border-rose-100 bg-rose-50 p-4 text-sm leading-relaxed text-rose-700">
          最近错误：{{ latestSyncRun.error_message }}
        </div>
      </section>

      <section class="mb-6 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <h2 class="text-lg font-bold text-slate-800">站点反馈（{{ feedbackItems.length }}）</h2>
            <p class="mt-1 text-xs text-slate-400">来自页脚的错误报告、反馈与建议。</p>
          </div>
          <el-button @click="loadFeedback">刷新反馈</el-button>
        </div>

        <div v-if="feedbackItems.length === 0" class="p-5 text-sm text-slate-500">
          暂无站点反馈。
        </div>

        <article
          v-for="item in feedbackItems"
          :key="item.id"
          class="border-b border-slate-100 p-5 last:border-b-0"
        >
          <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div class="flex flex-wrap items-center gap-3 text-sm text-slate-400">
              <span>#{{ item.id }}</span>
              <span
                class="rounded px-2 py-1 text-xs font-semibold"
                :class="item.feedbackType === 'error' ? 'bg-rose-50 text-rose-700' : 'bg-blue-50 text-blue-700'"
              >
                {{ feedbackTypeLabel(item) }}
              </span>
              <span>{{ formatDisplayDate(item.date) }}</span>
            </div>
            <el-button type="danger" plain @click="handleDeleteFeedback(item)">删除反馈</el-button>
          </div>

          <div class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
            {{ item.content }}
          </div>
        </article>
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
          <div class="grid grid-cols-[minmax(0,1.2fr)_110px_110px_110px_110px] gap-4 border-b border-slate-100 px-5 py-4 text-sm font-semibold text-slate-500">
            <div>老师</div>
            <div class="text-right">评论数</div>
            <div class="text-right">链接数</div>
            <div class="text-right">平均分</div>
            <div class="text-right">快跑数</div>
          </div>

          <button
            v-for="teacher in teachers"
            :key="teacher.uid"
            type="button"
            class="grid w-full grid-cols-[minmax(0,1.2fr)_110px_110px_110px_110px] gap-4 border-b border-slate-100 px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-slate-50"
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
            <div class="text-right text-base font-semibold text-slate-700">{{ teacher.linkCount }}</div>
            <div class="text-right text-base font-semibold text-slate-700">{{ teacher.averageScore.toFixed(1) }}</div>
            <div class="text-right text-base font-semibold text-rose-600">{{ teacher.runAwayVotes }}</div>
          </button>
        </div>
      </template>
    </main>

    <SiteFooter />
  </div>
</template>
