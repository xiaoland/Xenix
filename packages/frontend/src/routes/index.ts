import { RouteRecordRaw, createRouter, createWebHistory } from "vue-router";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "Home",
    component: () => import("../features/projects/pages/HomeView.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/auth",
    children: [
      {
        path: "signin",
        name: "SignIn",
        component: () => import("../features/auth/pages/SignInView.vue"),
      },
      {
        path: "signup",
        name: "SignUp",
        component: () => import("../features/auth/pages/SignUpView.vue"),
      },
    ],
  },
  {
    path: "/work-items/new",
    name: "WorkItemNew",
    component: () => import("../features/work-items/pages/WorkItemNewView.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/work-items/:id",
    name: "WorkItemDetail",
    component: () =>
      import("../features/work-items/pages/WorkItemDetailView.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/projects/:projectId/datasets",
    name: "ProjectDatasets",
    component: () => import("../features/datasets/pages/DatasetsView.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/projects/:projectId/datasets/:id",
    name: "DatasetDetail",
    component: () => import("../features/datasets/pages/DatasetDetailView.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/tasks",
    name: "Tasks",
    component: () => import("../features/tasks/pages/TasksView.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/admin/users",
    name: "UserManagement",
    component: () => import("../features/auth/pages/UsersView.vue"),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("auth_token");
  const userStr = localStorage.getItem("auth_user");
  let user = null;
  if (userStr) {
    try {
      user = JSON.parse(userStr);
    } catch (e) {
      // Invalid user data
    }
  }

  if (to.meta.requiresAuth && !token) {
    next("/auth/signin");
  } else if (to.meta.requiresAdmin && user?.role !== "admin") {
    next("/");
  } else {
    next();
  }
});

export default router;
