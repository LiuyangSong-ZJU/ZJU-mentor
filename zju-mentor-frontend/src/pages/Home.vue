<script setup>
import SiteFooter from '../components/SiteFooter.vue'
import TeacherSearchPanel from '../components/TeacherSearchPanel.vue'
</script>

<template>
  <div class="min-h-screen bg-gradient-to-b from-slate-50 via-white to-rose-50/30 p-6 flex flex-col">
    <main class="flex-1 flex items-center justify-center">
      <div class="w-full max-w-2xl">
        <h1 class="mb-7 text-center text-5xl font-extrabold tracking-tight text-blue-700 sm:text-6xl">
          浙大查导师
        </h1>

        <TeacherSearchPanel placeholder="搜索导师名字或关键词..." />

        <div class="mt-4 flex items-center justify-center gap-8 text-sm text-slate-500">
          <RouterLink to="/browse/unit" class="font-medium text-blue-600 hover:text-blue-700 hover:underline">按单位浏览</RouterLink>
          <RouterLink to="/browse/name" class="font-medium text-blue-600 hover:text-blue-700 hover:underline">按名字浏览</RouterLink>
        </div>
      </div>
    </main>

    <SiteFooter />
  </div>
</template>