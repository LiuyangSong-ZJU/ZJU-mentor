<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const VISITOR_ID_KEY = 'zju-mentor-visitor-id'
const AUTHOR_QQ = '3488105113'
const CC98_POST_URL = 'https://www.cc98.org/topic/6497563/'

const isFeedbackDialogOpen = ref(false)
const isAboutDialogOpen = ref(false)
const isSubmittingFeedback = ref(false)
const todayVisits = ref(null)
const feedbackDialogTitle = ref('反馈与建议')
const feedbackForm = reactive({
  feedbackType: 'suggestion',
  content: ''
})

const openFeedbackDialog = (feedbackType, title) => {
  feedbackForm.feedbackType = feedbackType
  feedbackForm.content = ''
  feedbackDialogTitle.value = title
  isFeedbackDialogOpen.value = true
}

const submitFeedback = async () => {
  const content = feedbackForm.content.trim()
  if (!content) {
    ElMessage.error('请先填写内容。')
    return
  }

  isSubmittingFeedback.value = true
  try {
    const response = await fetch('/api/feedback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        feedbackType: feedbackForm.feedbackType,
        content
      })
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.message || `请求失败：${response.status}`)
    }

    isFeedbackDialogOpen.value = false
    ElMessage.success('已收到，感谢你帮这个站变好。')
  } catch (error) {
    ElMessage.error(error.message || '提交失败，请稍后再试。')
  } finally {
    isSubmittingFeedback.value = false
  }
}

const showAuthorContact = async () => {
  try {
    await ElMessageBox.alert(`QQ: ${AUTHOR_QQ}`, '联系作者', {
      confirmButtonText: '复制 QQ'
    })
    await navigator.clipboard.writeText(AUTHOR_QQ)
    ElMessage.success('已复制 QQ。')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.info(`QQ: ${AUTHOR_QQ}`)
    }
  }
}

const getVisitorId = () => {
  const existing = window.localStorage.getItem(VISITOR_ID_KEY)
  if (existing) {
    return existing
  }

  const visitorId = window.crypto?.randomUUID
    ? window.crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  window.localStorage.setItem(VISITOR_ID_KEY, visitorId)
  return visitorId
}

const loadTodayVisits = async () => {
  try {
    const response = await fetch('/api/visits/today', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        visitorId: getVisitorId()
      })
    })
    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`)
    }

    const payload = await response.json()
    todayVisits.value = payload.todayVisits ?? 0
  } catch {
    todayVisits.value = null
  }
}

onMounted(() => {
  loadTodayVisits()
})
</script>

<template>
  <footer class="mt-auto pt-8 pb-4 border-t border-slate-200">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between text-sm text-slate-500">
      <div class="flex flex-wrap items-center gap-x-8 gap-y-2">
        <span>今日访问人数：{{ todayVisits ?? '--' }}</span>
        <a
          href="https://github.com/LiuyangSong-ZJU/ZJU-mentor/releases/tag/data-latest"
          target="_blank"
          rel="noreferrer"
          class="font-medium text-slate-600 hover:text-blue-600 transition-colors"
        >
          下载全站数据
        </a>
      </div>
      <div class="flex flex-wrap items-center justify-center gap-8">
        <a href="#" class="hover:text-blue-600 transition-colors" @click.prevent="openFeedbackDialog('error', '报告错误（导师信息/网站 bug）')">报告错误（导师信息/网站bug）</a>
        <a href="#" class="hover:text-blue-600 transition-colors" @click.prevent="isAboutDialogOpen = true">关于本站</a>
        <a href="#" class="hover:text-blue-600 transition-colors" @click.prevent="showAuthorContact">联系作者</a>
        <span>
          <a href="#" class="hover:text-blue-600 transition-colors" @click.prevent="openFeedbackDialog('suggestion', '反馈与建议')">反馈与建议</a>
          <span>（欢迎加入讨论QQ群：1098994681）</span>
        </span>
      </div>
    </div>

    <el-dialog v-model="isFeedbackDialogOpen" :title="feedbackDialogTitle" width="560px">
      <div class="space-y-4">
        <p class="text-sm leading-relaxed text-slate-500">
          可以写导师信息错误、网站 bug、功能建议或其他想法。提交后会出现在后台管理页。
        </p>
        <el-input
          v-model="feedbackForm.content"
          type="textarea"
          :rows="7"
          maxlength="2000"
          show-word-limit
          placeholder="请写下你想报告或建议的内容。"
        />
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="isFeedbackDialogOpen = false">取消</el-button>
          <el-button type="primary" :loading="isSubmittingFeedback" @click="submitFeedback">提交</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="isAboutDialogOpen" title="关于本站" width="420px">
      <div class="space-y-5 text-sm">
        <div class="space-y-3">
          <a
            :href="CC98_POST_URL || '#'"
            :target="CC98_POST_URL ? '_blank' : undefined"
            :rel="CC98_POST_URL ? 'noreferrer' : undefined"
            class="block font-medium text-blue-600 hover:text-blue-700 hover:underline"
            @click="!CC98_POST_URL && $event.preventDefault()"
          >
            CC98帖子
          </a>
          <a
            href="https://github.com/LiuyangSong-ZJU/ZJU-mentor"
            target="_blank"
            rel="noreferrer"
            class="block font-medium text-blue-600 hover:text-blue-700 hover:underline"
          >
            Github 仓库
          </a>
        </div>

        <div class="rounded-2xl bg-slate-50/70 p-4 text-xs leading-6 text-slate-400">
          <div class="font-semibold text-slate-500">本站宗旨与特点：</div>
          <div>1. 评价数据与代码全开源</div>
          <div>2. 匿名评价</div>
          <div>3. 所有评价均为选填</div>
          <div>4. 可添加外链如 CC98 帖子链接</div>
        </div>
      </div>
    </el-dialog>
  </footer>
</template>
