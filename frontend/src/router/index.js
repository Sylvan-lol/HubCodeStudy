import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import BenchmarkView from '../views/BenchmarkView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/benchmark', name: 'benchmark', component: BenchmarkView },
  ],
})

export default router
