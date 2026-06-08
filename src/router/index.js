import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../spin3/stores/auth'
import Login from '../spin3/views/Login.vue'
import StatusGrid from '../spin3/views/StatusGrid.vue'
import HistoryTimeline from '../spin3/views/HistoryTimeline.vue'

import MainLayout from '../spin3/components/MainLayout.vue'

const routes = [
  { path: '/login', component: Login, name: 'Login' },
  { 
    path: '/spin3', 
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: 'status',
        component: StatusGrid,
        name: 'StatusGrid'
      },
      {
        path: 'history',
        component: HistoryTimeline,
        name: 'HistoryTimeline'
      },
      { path: '', redirect: 'status' }
    ]
  },
  { path: '/', redirect: '/spin3/status' }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next('/login')
  } else if (to.name === 'Login' && auth.isAuthenticated) {
    next('/spin3/status')
  } else {
    next()
  }
})

export default router
