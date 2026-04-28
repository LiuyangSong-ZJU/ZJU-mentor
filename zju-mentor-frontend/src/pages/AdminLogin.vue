<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import SiteFooter from '../components/SiteFooter.vue'
import { setAdminToken } from '../utils/adminAuth'

const route = useRoute()
const router = useRouter()

const token = ref('')
const isSubmitting = ref(false)

const submitLogin = async () => {
  if (!token.value.trim()) {
    ElMessage.error('请输入后台口令。')
    return
  }

  isSubmitting.value = true

  try {
    const response = await fetch('/api/admin/session', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        token: token.value.trim()
      })
    })

    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.message || `请求失败：${response.status}`)
    }

    setAdminToken(token.value.trim())
    router.replace(String(route.query.redirect || '/__admin__'))
  } catch (error) {
    ElMessage.error(error.message || '后台登录失败。')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen flex-col bg-gradient-to-b from-slate-50 via-white to-slate-100 p-6">
    <main class="mx-auto flex w-full max-w-md flex-1 items-center">
      <section class="w-full rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <div class="mb-6">
          <div class="text-sm font-semibold uppercase tracking-[0.22em] text-slate-400">Hidden Admin</div>
          <h1 class="mt-2 text-3xl font-black text-slate-900">后台入口</h1>
          <p class="mt-2 text-sm text-slate-500">输入后台口令后进入管理台。</p>
        </div>

        <div class="space-y-4">
          <el-input
            v-model="token"
            type="password"
            show-password
            size="large"
            placeholder="后台口令"
            @keydown.enter.prevent="submitLogin"
          />
          <el-button type="primary" size="large" class="w-full" :loading="isSubmitting" @click="submitLogin">
            进入后台
          </el-button>
        </div>
      </section>
    </main>

    <SiteFooter />
  </div>
</template>
