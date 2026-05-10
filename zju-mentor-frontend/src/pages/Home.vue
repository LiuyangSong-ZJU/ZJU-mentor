<script setup>
import { onMounted, ref } from 'vue'
import SiteFooter from '../components/SiteFooter.vue'
import TeacherSearchPanel from '../components/TeacherSearchPanel.vue'

const portalStats = ref({
  isVisible: false,
  reviewedTeacherCount: 0,
  reviewCount: 0,
  linkCount: 0
})

const hasLoadedStats = ref(false)

onMounted(async () => {
  try {
    const response = await fetch('/api/stats')
    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`)
    }

    portalStats.value = await response.json()
    hasLoadedStats.value = true
  } catch {
    hasLoadedStats.value = false
  }
})
</script>

<template>
  <div class="min-h-screen bg-gradient-to-b from-slate-50 via-white to-rose-50/30 p-6 flex flex-col">
    <main class="flex-1 flex items-center justify-center">
      <div class="w-full max-w-2xl">
        <h1 class="mb-7 text-center text-5xl font-extrabold tracking-tight text-[#033e87] sm:text-6xl">
          浙大查导师
        </h1>

        <TeacherSearchPanel placeholder="搜索导师名字或关键词..." />

        <div class="mt-4 flex items-center justify-center gap-8 text-sm text-slate-500">
          <RouterLink to="/browse/unit" class="font-medium text-blue-600 hover:text-blue-700 hover:underline">按单位浏览</RouterLink>
          <RouterLink to="/browse/name" class="font-medium text-blue-600 hover:text-blue-700 hover:underline">按名字浏览</RouterLink>
        </div>

        <p v-if="hasLoadedStats && portalStats.isVisible" class="mt-7 text-center text-sm text-slate-500">
          共有 {{ portalStats.reviewedTeacherCount }} 个老师被提交 {{ portalStats.reviewCount }} 条评价 和 {{ portalStats.linkCount }} 条链接
        </p>

        <p class="mx-auto mt-12 max-w-xl rounded-2xl border border-slate-200/70 bg-white/70 px-5 py-4 text-center text-sm leading-7 text-slate-500 shadow-sm">
          本站评价来自用户投稿，不代表本站立场；相关信息仅供参考，请结合导师主页、学院公开信息、在读学生反馈等多渠道核实。
        </p>
      </div>
    </main>

    <SiteFooter />
  </div>
</template>
