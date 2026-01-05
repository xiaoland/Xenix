import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/HomeView.vue'),
  },
  {
    path: '/auth',
    children: [
      {
        path: 'signin',
        name: 'SignIn',
        component: () => import('../views/auth/SignInView.vue'),
      },
      {
        path: 'signup',
        name: 'SignUp',
        component: () => import('../views/auth/SignUpView.vue'),
      },
    ],
  },
  {
    path: '/projects',
    name: 'Projects',
    component: () => import('../views/projects/ProjectsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/:id',
    name: 'ProjectDetail',
    component: () => import('../views/projects/ProjectDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/work-items/:id',
    name: 'WorkItemDetail',
    component: () => import('../views/work-items/WorkItemDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/projects/:projectId/datasets',
    name: 'ProjectDatasets',
    component: () => import('../views/datasets/DatasetsView.vue'),
    meta: { requiresAuth: true },
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

// Navigation guard for authentication
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token');
  
  if (to.meta.requiresAuth && !token) {
    next('/auth/signin');
  } else {
    next();
  }
});

export default router;
