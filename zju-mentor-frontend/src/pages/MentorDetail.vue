<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Link } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import SiteFooter from '../components/SiteFooter.vue'
import SiteHomeLink from '../components/SiteHomeLink.vue'
import TeacherSearchPanel from '../components/TeacherSearchPanel.vue'
import { getVoterId, loadCommentVotes, saveCommentVotes } from '../utils/commentVotes'

const route = useRoute()

const metricDefinitions = [
  { key: 'ethics', shortLabel: '师德', label: '师德品行' },
  { key: 'academic', shortLabel: '学术', label: '学术能力与指导情况' },
  { key: 'wlb', shortLabel: 'WLB', label: 'WLB' },
  { key: 'funding', shortLabel: '经费', label: '经费与津贴' },
  { key: 'graduation', shortLabel: '毕业', label: '毕业友好程度' },
  { key: 'outcome', shortLabel: '出路', label: '出路去向' }
]

const mentor = ref({
  uid: '',
  name: '导师详情',
  title: '未标注职称',
  colleges: [],
  url: '',
  runAwayVotes: 0,
  totalVotes: 0
})

const mentorRadarMetrics = ref(
  metricDefinitions.map(metric => ({
    ...metric,
    value: 0,
    votes: 0
  }))
)

const reviews = ref([])
const links = ref([])
const activeTab = ref('reviews')
const isLoading = ref(true)
const errorMessage = ref('')
const isReviewDialogOpen = ref(false)
const isLinkDialogOpen = ref(false)
const isSubmittingReview = ref(false)
const isSubmittingLink = ref(false)
const votingCommentIds = ref({})
const commentVotes = ref(loadCommentVotes())

const reviewForm = reactive({
  scores: Object.fromEntries(metricDefinitions.map(metric => [metric.key, 0])),
  isRunAway: false,
  identity: '',
  content: ''
})

const linkForm = reactive({
  url: '',
  linkType: 'cc98',
  description: ''
})

const sliderMarks = {
  0: { label: '' },
  1: { label: '' },
  2: { label: '' },
  3: { label: '' },
  4: { label: '' },
  5: { label: '' }
}

const mentorRadarValues = computed(() => mentorRadarMetrics.value.map(item => item.value))

const runAwayRatio = computed(() => {
  if (!mentor.value.totalVotes) {
    return 0
  }

  return mentor.value.runAwayVotes / mentor.value.totalVotes
})

const runAwayBadgeStyle = computed(() => {
  const ratio = runAwayRatio.value
  const opacity = 0.14 + ratio * 0.78

  return {
    backgroundColor: `rgba(185, 28, 28, ${opacity})`,
    borderColor: `rgba(153, 27, 27, ${0.22 + ratio * 0.38})`
  }
})

const currentTeacherUid = computed(() => String(route.params.id ?? ''))

const radarChartRef = ref(null)
let radarChart = null

const formatDisplayDate = value => {
  if (!value) {
    return ''
  }

  return String(value).replace('T', ' ').slice(0, 16)
}

const resetReviewForm = () => {
  for (const metric of metricDefinitions) {
    reviewForm.scores[metric.key] = 0
  }
  reviewForm.isRunAway = false
  reviewForm.identity = ''
  reviewForm.content = ''
}

const resetLinkForm = () => {
  linkForm.url = ''
  linkForm.linkType = 'cc98'
  linkForm.description = ''
}

const applyMentorPayload = payload => {
  mentor.value = {
    uid: payload.uid || currentTeacherUid.value,
    name: payload.name || '导师详情',
    title: payload.workTitle || '未标注职称',
    colleges: payload.colleges ?? [],
    url: payload.profileUrl || '',
    runAwayVotes: payload.runAwayVotes ?? payload.summary?.runAwayVotes ?? 0,
    totalVotes: payload.totalVotes ?? payload.summary?.totalVotes ?? 0
  }

  const metricsFromApi = payload.summary?.metrics ?? []
  mentorRadarMetrics.value = metricDefinitions.map(metric => {
    const matched = metricsFromApi.find(item => item.key === metric.key)
    return {
      ...metric,
      value: matched?.value ?? 0,
      votes: matched?.votes ?? 0
    }
  })

  reviews.value = payload.reviews ?? []
  links.value = payload.links ?? []
}

const renderRadarChart = () => {
  if (!radarChartRef.value) {
    return
  }

  if (!radarChart) {
    radarChart = echarts.init(radarChartRef.value)
  }

  radarChart.setOption(
    {
      animation: false,
      radar: {
        indicator: mentorRadarMetrics.value.map(item => ({ name: item.shortLabel, max: 5 })),
        center: ['50%', '50%'],
        radius: '68%',
        splitArea: { show: false },
        axisName: { color: '#374151', fontSize: 10, padding: [2, 2] }
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: mentorRadarValues.value,
              name: '综合评分',
              areaStyle: { color: 'rgba(59, 130, 246, 0.18)' },
              lineStyle: { color: '#2563eb', width: 2 },
              itemStyle: { color: '#2563eb' }
            }
          ]
        }
      ]
    },
    true
  )
}

const resizeRadarChart = () => {
  if (radarChart) {
    radarChart.resize()
  }
}

const loadMentorByUid = async uid => {
  if (!uid) {
    errorMessage.value = '缺少导师 ID。'
    isLoading.value = false
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await fetch(`/api/teachers/${encodeURIComponent(uid)}`)
    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`)
    }

    const payload = await response.json()
    applyMentorPayload(payload)
    await nextTick()
    renderRadarChart()
  } catch (error) {
    errorMessage.value = '加载导师详情失败。请先启动本地 API 服务。'
  } finally {
    isLoading.value = false
  }
}

const openReviewDialog = () => {
  resetReviewForm()
  isReviewDialogOpen.value = true
}

const openLinkDialog = () => {
  resetLinkForm()
  isLinkDialogOpen.value = true
}

const submitReview = async () => {
  if (!currentTeacherUid.value) {
    return
  }

  const trimmedContent = reviewForm.content.trim()
  if (!trimmedContent) {
    ElMessage.error('请先填写评论内容。')
    return
  }

  isSubmittingReview.value = true

  try {
    const response = await fetch(`/api/teachers/${encodeURIComponent(currentTeacherUid.value)}/comments`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        scores: reviewForm.scores,
        isRunAway: reviewForm.isRunAway,
        identity: reviewForm.identity,
        content: trimmedContent
      })
    })

    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.message || `请求失败：${response.status}`)
    }

    applyMentorPayload(payload)
    isReviewDialogOpen.value = false
    activeTab.value = 'reviews'
    ElMessage.success('评价已添加。')
    await nextTick()
    renderRadarChart()
  } catch (error) {
    ElMessage.error(error.message || '提交评价失败。')
  } finally {
    isSubmittingReview.value = false
  }
}

const submitLink = async () => {
  if (!currentTeacherUid.value) {
    return
  }

  const trimmedUrl = linkForm.url.trim()
  if (!trimmedUrl) {
    ElMessage.error('请先填写链接。')
    return
  }

  isSubmittingLink.value = true

  try {
    const response = await fetch(`/api/teachers/${encodeURIComponent(currentTeacherUid.value)}/links`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: trimmedUrl,
        linkType: linkForm.linkType || 'cc98',
        description: linkForm.description.trim()
      })
    })

    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.message || `请求失败：${response.status}`)
    }

    applyMentorPayload(payload)
    isLinkDialogOpen.value = false
    activeTab.value = 'links'
    ElMessage.success('链接已添加。')
  } catch (error) {
    ElMessage.error(error.message || '提交链接失败。')
  } finally {
    isSubmittingLink.value = false
  }
}

const isVotingComment = commentId => Boolean(votingCommentIds.value[commentId])

const submitCommentVote = async (review, voteType) => {
  if (!review?.id || isVotingComment(review.id)) {
    return
  }

  const previousVote = commentVotes.value[review.id]
  votingCommentIds.value = { ...votingCommentIds.value, [review.id]: true }

  try {
    const response = await fetch(`/api/comments/${review.id}/vote`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        voterId: getVoterId(),
        voteType
      })
    })

    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.message || `请求失败：${response.status}`)
    }

    const nextVotes = { ...commentVotes.value }
    if (previousVote === voteType) {
      delete nextVotes[review.id]
    } else {
      nextVotes[review.id] = voteType
    }
    commentVotes.value = nextVotes
    saveCommentVotes(nextVotes)

    applyMentorPayload(payload)
  } catch (error) {
    ElMessage.error(error.message || '投票失败。')
  } finally {
    const nextVoting = { ...votingCommentIds.value }
    delete nextVoting[review.id]
    votingCommentIds.value = nextVoting
  }
}

onMounted(() => {
  renderRadarChart()
  window.addEventListener('resize', resizeRadarChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeRadarChart)

  if (radarChart) {
    radarChart.dispose()
    radarChart = null
  }
})

watch(
  () => route.params.id,
  id => {
    loadMentorByUid(id ? String(id) : '')
  },
  { immediate: true }
)

watch(mentorRadarMetrics, () => {
  renderRadarChart()
}, { deep: true })

watch(radarChartRef, value => {
  if (value) {
    nextTick(() => {
      renderRadarChart()
      resizeRadarChart()
    })
  }
})
</script>

<template>
  <div class="mx-auto flex min-h-screen max-w-6xl flex-col bg-gradient-to-b from-slate-50 via-white to-rose-50/30 p-6 font-sans">
    <SiteHomeLink />

    <div class="mb-8 flex w-full justify-center">
      <div class="w-full max-w-2xl">
        <TeacherSearchPanel placeholder="键入导师名字搜索..." />
      </div>
    </div>

    <main class="flex-1">
      <div v-if="isLoading" class="rounded-2xl border border-slate-200 bg-white p-6 text-slate-500 shadow-sm">
        正在加载导师详情...
      </div>

      <div v-else-if="errorMessage" class="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 shadow-sm">
        {{ errorMessage }}
      </div>

      <template v-else>
        <div class="mentor-hero mb-8 rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-[0_12px_40px_rgba(15,23,42,0.08)] backdrop-blur">
          <div class="flex min-w-0 flex-col">
            <div class="mb-2 flex flex-wrap items-center gap-x-4 gap-y-2">
              <h1 class="text-3xl font-bold text-slate-800">{{ mentor.name }}</h1>
              <span class="rounded-md border px-3 py-1 text-sm font-bold text-white shadow-sm" :style="runAwayBadgeStyle">
                {{ mentor.runAwayVotes }} / {{ mentor.totalVotes }} 人认为 快跑！
              </span>
            </div>

            <p class="mb-1 text-lg text-slate-600">
              <template v-if="mentor.colleges.length > 0">
                <template v-for="(college, index) in mentor.colleges" :key="college.collegeId">
                  <RouterLink
                    :to="`/browse/unit/${college.collegeId}`"
                    class="font-medium text-blue-700 hover:text-blue-800 hover:underline"
                  >
                    {{ college.collegeName }}
                  </RouterLink>
                  <span v-if="index !== mentor.colleges.length - 1" class="mx-2 text-slate-300">/</span>
                </template>
                <span class="mx-2 text-slate-300">|</span>
              </template>
              <span>{{ mentor.title }}</span>
            </p>

            <div class="mb-5 flex items-baseline gap-2 text-sm text-slate-500">
              <span class="shrink-0 whitespace-nowrap">教师主页：</span>
              <a
                :href="mentor.url"
                class="min-w-0 truncate text-blue-500 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                {{ mentor.url || '未提供链接' }}
              </a>
            </div>

            <div class="mentor-action-stack mt-auto">
              <el-button type="primary" :icon="Edit" size="large" class="mentor-action-button !ml-0 !mr-0 justify-center px-8" @click="openReviewDialog">
                写评价
              </el-button>
              <el-button size="large" :icon="Link" class="mentor-action-button !ml-0 !mr-0 justify-center px-8" @click="openLinkDialog">
                添加 CC98 或其他链接
              </el-button>
            </div>
          </div>

          <div class="mentor-radar-wrap">
            <div ref="radarChartRef" class="mentor-radar"></div>
          </div>

          <div class="mentor-metrics-card min-w-0 rounded-2xl border border-slate-200 bg-slate-50/90 p-4">
            <div
              v-for="metric in mentorRadarMetrics"
              :key="metric.key"
              class="mentor-metric-row"
            >
              <span class="mentor-metric-label">{{ metric.label }}</span>
              <div class="mentor-metric-bar">
                <div
                  class="mentor-metric-fill"
                  :style="{ width: (metric.value / 5) * 100 + '%' }"
                ></div>
              </div>
              <div class="mentor-metric-value">
                <span class="mentor-metric-score">{{ metric.value.toFixed(1) }}/5.0</span>
                <span class="mentor-metric-votes">{{ metric.votes }}人</span>
              </div>
            </div>
          </div>
        </div>

        <div class="mb-4 flex justify-center">
          <div class="flex items-center gap-3 text-lg font-medium text-slate-500">
            <button
              class="transition-colors"
              :class="activeTab === 'reviews' ? 'text-slate-900' : 'hover:text-slate-900'"
              @click="activeTab = 'reviews'"
            >
              评价 ({{ reviews.length }})
            </button>
            <span class="text-slate-300">|</span>
            <button
              class="transition-colors"
              :class="activeTab === 'links' ? 'text-slate-900' : 'hover:text-slate-900'"
              @click="activeTab = 'links'"
            >
              CC98 或其他链接 ({{ links.length }})
            </button>
          </div>
        </div>

        <div v-if="activeTab === 'reviews'" class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div v-if="reviews.length === 0" class="p-6 text-sm text-slate-500">
            还没有评价，欢迎添加第一条。
          </div>

          <div v-else class="divide-y divide-slate-100">
            <article v-for="review in reviews" :key="review.id" class="p-5">
              <div class="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-slate-400">
                <span>{{ formatDisplayDate(review.date) }}</span>
                <span v-if="review.identity" class="rounded-sm bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
                  {{ review.identity }}
                </span>
                <span v-if="review.isRunAway" class="rounded-sm border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-bold text-rose-700">
                  快跑
                </span>
              </div>

              <div v-if="review.scores.length > 0" class="review-score-list mb-4">
                <div
                  v-for="score in review.scores"
                  :key="`${review.id}-${score.key}`"
                  class="review-score-pill"
                >
                  <div
                    class="review-score-fill"
                    :style="{ width: (score.value / 5) * 100 + '%' }"
                  ></div>
                  <span class="review-score-label">{{ score.label }}</span>
                  <span class="review-score-value">{{ score.value.toFixed(1) }}</span>
                </div>
              </div>

              <div class="flex items-start justify-between gap-8">
                <div class="flex-1 text-slate-800 leading-relaxed">
                  {{ review.content }}
                </div>

                <div class="flex flex-shrink-0 gap-3">
                  <el-button
                    size="default"
                    :type="commentVotes[review.id] === 'up' ? 'primary' : 'default'"
                    :loading="isVotingComment(review.id)"
                    class="w-20 font-bold"
                    @click="submitCommentVote(review, 'up')"
                  >
                    👍 {{ review.upvotes }}
                  </el-button>
                  <el-button
                    size="default"
                    :type="commentVotes[review.id] === 'down' ? 'danger' : 'default'"
                    :loading="isVotingComment(review.id)"
                    class="w-20 font-bold"
                    @click="submitCommentVote(review, 'down')"
                  >
                    👎 {{ review.downvotes }}
                  </el-button>
                </div>
              </div>
            </article>
          </div>
        </div>

        <div v-else class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div v-if="links.length === 0" class="p-6 text-sm text-slate-500">
            还没有相关链接，欢迎添加第一条。
          </div>

          <div v-else class="divide-y divide-slate-100">
            <article v-for="item in links" :key="item.id" class="p-5">
              <div class="mb-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-slate-400">
                <span>{{ formatDisplayDate(item.date) }}</span>
                <span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
                  {{ item.linkType === 'other' ? '其他链接' : 'CC98' }}
                </span>
              </div>

              <a :href="item.url" target="_blank" rel="noreferrer" class="break-all text-base font-semibold text-blue-600 hover:text-blue-700 hover:underline">
                {{ item.url }}
              </a>

              <p v-if="item.description" class="mt-2 text-sm leading-relaxed text-slate-600">
                {{ item.description }}
              </p>
            </article>
          </div>
        </div>
      </template>
    </main>

    <SiteFooter />

    <el-dialog v-model="isReviewDialogOpen" title="写评价" width="720px">
      <div class="space-y-6">
        <section>
          <div class="mb-4 text-sm font-medium text-slate-500">评分（每个都为可选，0.0 为不评价）</div>

          <div class="space-y-3">
            <div
              v-for="metric in metricDefinitions"
              :key="`form-${metric.key}`"
              class="review-form-row"
            >
              <div class="review-form-label">{{ metric.label }}</div>
              <el-slider
                v-model="reviewForm.scores[metric.key]"
                class="review-score-slider"
                :min="0"
                :max="5"
                :step="0.1"
                :marks="sliderMarks"
                :show-tooltip="false"
                show-stops
              />
              <el-input-number
                v-model="reviewForm.scores[metric.key]"
                :min="0"
                :max="5"
                :step="0.1"
                :precision="1"
                :controls="false"
                class="review-score-input"
              />
            </div>
          </div>

          <div class="mt-5">
            <el-button
              :type="reviewForm.isRunAway ? 'danger' : 'default'"
              :plain="!reviewForm.isRunAway"
              class="runaway-flag-button"
              @click="reviewForm.isRunAway = !reviewForm.isRunAway"
            >
              {{ reviewForm.isRunAway ? '已选择：快跑' : '点此标记：快跑' }}
            </el-button>
          </div>
        </section>

        <section class="space-y-4 border-t border-slate-100 pt-5">
          <div>
            <div class="mb-3 text-sm font-medium text-slate-500">身份（可以不选）</div>
            <div class="flex flex-wrap items-center gap-3">
              <el-radio-group v-model="reviewForm.identity">
                <el-radio-button label="本组成员" />
                <el-radio-button label="非本组成员" />
              </el-radio-group>
              <button type="button" class="text-sm text-slate-400 hover:text-slate-600" @click="reviewForm.identity = ''">
                清空选择
              </button>
            </div>
          </div>

          <div>
            <div class="mb-3 text-sm font-medium text-slate-500">评论</div>
            <el-input
              v-model="reviewForm.content"
              type="textarea"
              :rows="6"
              maxlength="2000"
              show-word-limit
              placeholder="写下你对这位导师的真实体验。"
            />
          </div>
        </section>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="isReviewDialogOpen = false">取消</el-button>
          <el-button type="primary" :loading="isSubmittingReview" @click="submitReview">提交评价</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="isLinkDialogOpen" title="添加 CC98 或其他链接" width="640px">
      <div class="space-y-5">
        <div>
          <div class="mb-3 text-sm font-medium text-slate-500">链接（必选）</div>
          <el-input v-model="linkForm.url" placeholder="https://..." />
        </div>

        <div>
          <div class="mb-3 text-sm font-medium text-slate-500">CC98 / 其他链接</div>
          <el-radio-group v-model="linkForm.linkType">
            <el-radio-button label="cc98">CC98</el-radio-button>
            <el-radio-button label="other">其他链接</el-radio-button>
          </el-radio-group>
        </div>

        <div>
          <div class="mb-3 text-sm font-medium text-slate-500">描述或留言（可选）</div>
          <el-input
            v-model="linkForm.description"
            type="textarea"
            :rows="4"
            maxlength="1000"
            show-word-limit
            placeholder="可以补充帖子内容、上下文或提醒。"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="isLinkDialogOpen = false">取消</el-button>
          <el-button type="primary" :loading="isSubmittingLink" @click="submitLink">添加链接</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.mentor-hero {
  display: grid;
  gap: 24px;
}

.mentor-action-stack {
  display: flex;
  width: 224px;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
}

.mentor-action-stack :deep(.el-button + .el-button) {
  margin-left: 0;
}

.mentor-action-stack :deep(.el-button) {
  margin-right: 0;
}

.mentor-action-button {
  width: 100%;
}

.mentor-radar-wrap {
  display: flex;
  width: 100%;
  align-items: flex-start;
  justify-content: center;
  padding-top: 4px;
}

.mentor-radar {
  height: 220px;
  width: 220px;
}

.mentor-metrics-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mentor-metric-row {
  display: grid;
  align-items: center;
  gap: 12px;
  grid-template-columns: 156px minmax(0, 1fr) 124px;
}

.mentor-metric-label {
  white-space: nowrap;
  font-size: 15px;
  font-weight: 600;
  line-height: 1;
  color: #334155;
}

.mentor-metric-bar {
  height: 14px;
  overflow: hidden;
  border-radius: 9999px;
  background: #dbe2ee;
}

.mentor-metric-fill {
  height: 100%;
  border-radius: 9999px;
  background: #253046;
}

.mentor-metric-value {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  white-space: nowrap;
  line-height: 1;
}

.mentor-metric-score {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

.mentor-metric-votes {
  font-size: 12px;
  color: #94a3b8;
}

.review-score-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.review-score-pill {
  position: relative;
  display: flex;
  height: 26px;
  width: 110px;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  border-radius: 9999px;
  border: 1px solid #bfdbfe;
  background: white;
  padding: 0 8px;
  font-size: 12px;
}

.review-score-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: #dbeafe;
}

.review-score-label {
  position: relative;
  z-index: 1;
  color: #475569;
}

.review-score-value {
  position: relative;
  z-index: 1;
  font-weight: 700;
  color: #1d4ed8;
}

.review-form-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.review-form-label {
  width: 112px;
  flex: 0 0 112px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.review-score-slider {
  min-width: 0;
  flex: 1 1 auto;
}

.review-score-slider :deep(.el-slider__runway) {
  margin: 10px 0;
}

.review-score-slider :deep(.el-slider__marks-text) {
  display: none;
}

.review-score-slider :deep(.el-slider__stop) {
  width: 6px;
  height: 6px;
  border: 0;
  background-color: #cbd5e1;
}

.review-score-slider :deep(.el-slider__button-wrapper) {
  top: -16px;
}

.review-score-slider :deep(.el-slider__button) {
  width: 16px;
  height: 16px;
}

.review-score-input {
  flex: 0 0 64px;
  width: 64px;
}

.review-score-input :deep(.el-input__wrapper) {
  padding-left: 6px;
  padding-right: 6px;
}

.review-score-input :deep(.el-input__inner) {
  text-align: center;
}

.runaway-flag-button {
  border-radius: 6px;
}

@media (min-width: 1024px) {
  .mentor-hero {
    grid-template-columns: minmax(0, 1.05fr) 240px minmax(360px, 1.45fr);
    align-items: start;
  }
}

@media (max-width: 767px) {
  .mentor-metric-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .mentor-metric-value {
    justify-content: flex-start;
  }

  .review-form-row {
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .mentor-action-stack {
    width: 100%;
    max-width: 224px;
  }
}
</style>
