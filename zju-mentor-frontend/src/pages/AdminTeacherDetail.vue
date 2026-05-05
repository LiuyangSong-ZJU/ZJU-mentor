<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import SiteFooter from '../components/SiteFooter.vue'
import { adminFetch, clearAdminToken } from '../utils/adminAuth'

const route = useRoute()
const router = useRouter()

const teacher = ref(null)
const isLoading = ref(true)
const errorMessage = ref('')

const formatDisplayDate = value => {
  if (!value) {
    return ''
  }

  return String(value).replace('T', ' ').slice(0, 16)
}

const handleUnauthorized = () => {
  clearAdminToken()
  router.replace({
    path: '/__admin__/login',
    query: { redirect: route.fullPath }
  })
}

const loadTeacher = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await adminFetch(`/api/admin/teachers/${encodeURIComponent(String(route.params.id || ''))}`)
    const payload = await response.json()

    if (response.status === 401) {
      handleUnauthorized()
      return
    }

    if (!response.ok) {
      throw new Error(payload.message || `请求失败：${response.status}`)
    }

    teacher.value = payload
  } catch (error) {
    errorMessage.value = error.message || '加载老师管理页失败。'
  } finally {
    isLoading.value = false
  }
}

const deleteComment = async review => {
  await ElMessageBox.confirm('确认删除这条评论吗？此操作不可撤销。', '删除评论', {
    type: 'warning'
  })

  const response = await adminFetch(`/api/admin/comments/${review.id}`, {
    method: 'DELETE'
  })
  const payload = await response.json()

  if (response.status === 401) {
    handleUnauthorized()
    return
  }

  if (!response.ok) {
    throw new Error(payload.message || `请求失败：${response.status}`)
  }

  teacher.value = payload
  ElMessage.success('评论已删除。')
}

const deleteLink = async item => {
  await ElMessageBox.confirm('确认删除这条链接吗？此操作不可撤销。', '删除链接', {
    type: 'warning'
  })

  const response = await adminFetch(`/api/admin/links/${item.id}`, {
    method: 'DELETE'
  })
  const payload = await response.json()

  if (response.status === 401) {
    handleUnauthorized()
    return
  }

  if (!response.ok) {
    throw new Error(payload.message || `请求失败：${response.status}`)
  }

  teacher.value = payload
  ElMessage.success('链接已删除。')
}

const handleDeleteComment = async review => {
  try {
    await deleteComment(review)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除评论失败。')
    }
  }
}

const handleDeleteLink = async item => {
  try {
    await deleteLink(item)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除链接失败。')
    }
  }
}

onMounted(() => {
  loadTeacher()
})
</script>

<template>
  <div class="flex min-h-screen flex-col bg-gradient-to-b from-slate-50 via-white to-slate-100 p-6">
    <main class="mx-auto w-full max-w-5xl flex-1">
      <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <RouterLink to="/__admin__" class="text-sm font-semibold text-blue-600 hover:underline">
            返回后台列表
          </RouterLink>
          <h1 class="mt-3 text-3xl font-black text-slate-900">老师记录管理</h1>
        </div>
      </div>

      <div v-if="isLoading" class="rounded-2xl border border-slate-200 bg-white p-6 text-slate-500 shadow-sm">
        正在加载老师记录...
      </div>

      <div v-else-if="errorMessage" class="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 shadow-sm">
        {{ errorMessage }}
      </div>

      <template v-else-if="teacher">
        <section class="mb-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 class="text-3xl font-black text-slate-900">{{ teacher.name }}</h2>
          <div class="mt-2 text-lg text-slate-600">{{ teacher.workTitle || '未标注职称' }}</div>
          <div class="mt-2 text-sm text-blue-600">
            {{ teacher.colleges.map(item => item.collegeName).join(' / ') || '未标注单位' }}
          </div>
          <a :href="teacher.profileUrl" target="_blank" rel="noreferrer" class="mt-3 inline-block text-sm text-slate-500 hover:text-blue-600 hover:underline">
            {{ teacher.profileUrl }}
          </a>
        </section>

        <section class="mb-6 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div class="border-b border-slate-100 px-5 py-4 text-lg font-bold text-slate-800">
            评论记录（{{ teacher.reviews.length }}）
          </div>

          <div v-if="teacher.reviews.length === 0" class="p-6 text-sm text-slate-500">
            暂无评论记录。
          </div>

          <article v-for="review in teacher.reviews" :key="review.id" class="border-b border-slate-100 p-5 last:border-b-0">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div class="flex flex-wrap items-center gap-3 text-sm text-slate-400">
                <span>#{{ review.id }}</span>
                <span>{{ formatDisplayDate(review.date) }}</span>
                <span v-if="review.identity" class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-500">{{ review.identity }}</span>
                <span v-if="review.isRunAway" class="rounded bg-rose-50 px-2 py-1 text-xs font-bold text-rose-700">快跑</span>
              </div>

              <el-button type="danger" plain @click="handleDeleteComment(review)">删除评论</el-button>
            </div>

            <div v-if="review.scores.length > 0" class="mb-3 flex flex-wrap gap-2">
              <span
                v-for="score in review.scores"
                :key="`${review.id}-${score.key}`"
                class="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700"
              >
                {{ score.label }} {{ score.value.toFixed(1) }}
              </span>
            </div>

            <div class="text-sm leading-relaxed text-slate-700">
              {{ review.content || '该评价没有文字评论' }}
            </div>
          </article>
        </section>

        <section class="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div class="border-b border-slate-100 px-5 py-4 text-lg font-bold text-slate-800">
            链接记录（{{ teacher.links.length }}）
          </div>

          <div v-if="teacher.links.length === 0" class="p-6 text-sm text-slate-500">
            暂无链接记录。
          </div>

          <article v-for="item in teacher.links" :key="item.id" class="border-b border-slate-100 p-5 last:border-b-0">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div class="flex flex-wrap items-center gap-3 text-sm text-slate-400">
                <span>#{{ item.id }}</span>
                <span>{{ formatDisplayDate(item.date) }}</span>
                <span class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-500">
                  {{ item.linkType === 'other' ? '其他链接' : 'CC98' }}
                </span>
              </div>

              <el-button type="danger" plain @click="handleDeleteLink(item)">删除链接</el-button>
            </div>

            <a :href="item.url" target="_blank" rel="noreferrer" class="break-all text-sm font-semibold text-blue-600 hover:text-blue-700 hover:underline">
              {{ item.url }}
            </a>

            <div v-if="item.description" class="mt-2 text-sm text-slate-600">
              {{ item.description }}
            </div>
          </article>
        </section>
      </template>
    </main>

    <SiteFooter />
  </div>
</template>
