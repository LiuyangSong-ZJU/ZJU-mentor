import { createRouter, createWebHistory } from 'vue-router'
import Home from '../pages/Home.vue'
import MentorDetail from '../pages/MentorDetail.vue'
import BrowseByUnit from '../pages/BrowseByUnit.vue'
import BrowseByName from '../pages/BrowseByName.vue'
import UnitTeachers from '../pages/UnitTeachers.vue'
import AdminLogin from '../pages/AdminLogin.vue'
import AdminDashboard from '../pages/AdminDashboard.vue'
import AdminTeacherDetail from '../pages/AdminTeacherDetail.vue'
import { getAdminToken } from '../utils/adminAuth'

const routes = [
  {
    path: '/',
    name: 'home',
    component: Home
  },
  {
    path: '/mentor/:id?',
    name: 'mentor-detail',
    component: MentorDetail
  },
  {
    path: '/browse/unit',
    name: 'browse-by-unit',
    component: BrowseByUnit
  },
  {
    path: '/browse/name',
    name: 'browse-by-name',
    component: BrowseByName
  },
  {
    path: '/browse/unit/:collegeId',
    name: 'unit-teachers',
    component: UnitTeachers
  },
  {
    path: '/__admin__/login',
    name: 'admin-login',
    component: AdminLogin
  },
  {
    path: '/__admin__',
    name: 'admin-dashboard',
    component: AdminDashboard,
    meta: { requiresAdmin: true }
  },
  {
    path: '/__admin__/teacher/:id',
    name: 'admin-teacher-detail',
    component: AdminTeacherDetail,
    meta: { requiresAdmin: true }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  if (to.meta.requiresAdmin && !getAdminToken()) {
    next({
      path: '/__admin__/login',
      query: { redirect: to.fullPath }
    })
    return
  }

  next()
})

export default router
