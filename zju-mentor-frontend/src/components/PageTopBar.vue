<script setup>
import { Search } from '@element-plus/icons-vue'

const emit = defineEmits(['search-click'])
</script>

<template>
  <div class="mb-6 flex items-center justify-between">
    <RouterLink
      to="/"
      class="text-sm font-semibold text-blue-700 transition-colors hover:text-blue-800 hover:underline"
    >
      门户
    </RouterLink>

    <button
      type="button"
      class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-600 transition-colors hover:border-slate-400 hover:text-slate-900"
      @click="emit('search-click')"
      aria-label="打开搜索"
      title="搜索导师"
    >
      <el-icon :size="17">
        <Search />
      </el-icon>
    </button>
  </div>
</template>