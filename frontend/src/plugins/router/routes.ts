import blanklayout from "@/layouts/blank.vue"
import defaultlayout from "@/layouts/default.vue"
import DashboardPage from "@/pages/Dashboard.vue"
import LoginPage from "@/pages/Login.vue"
import LogsPage from "@/pages/Logs.vue"
import MediaitemPage from "@/pages/Mediaitem.vue"
import MetadataPage from "@/pages/Metadata.vue"
import RecordsPage from "@/pages/Records.vue"
import ScrapingConfigsPage from "@/pages/ScrapingConfigs.vue"
import SettingsPage from "@/pages/Settings.vue"
import TaskPage from "@/pages/Task.vue"
import ToolsPage from "@/pages/Tools.vue"
import errorpage from "@/pages/[...error].vue"

export const routes = [
  { path: "/", redirect: "/dashboard" },
  {
    path: "/",
    component: defaultlayout,
    children: [
      {
        path: "dashboard",
        meta: { requiresAuth: true },
        component: DashboardPage,
      },
      {
        path: "mediaitems",
        meta: { requiresAuth: true },
        component: MediaitemPage,
      },
      {
        path: "records",
        meta: { requiresAuth: true },
        component: RecordsPage,
      },
      {
        path: "metadata",
        meta: { requiresAuth: true },
        component: MetadataPage,
      },
      {
        path: "tools",
        meta: { requiresAuth: true },
        component: ToolsPage,
      },
    ],
  },
  {
    path: "/tasks",
    redirect: "/tasks/all",
    component: defaultlayout,
    children: [
      {
        path: "all",
        meta: { requiresAuth: true },
        component: TaskPage,
      },
    ],
  },
  {
    path: "/scraping",
    component: defaultlayout,
    children: [
      {
        path: "configs",
        meta: { requiresAuth: true },
        component: ScrapingConfigsPage,
      },
    ],
  },
  {
    path: "/settings",
    component: defaultlayout,
    children: [
      {
        path: "",
        meta: { requiresAuth: true },
        component: SettingsPage,
      },
      {
        path: "user",
        redirect: { path: "/settings", query: { tab: "security" } },
      },
      {
        path: "service",
        redirect: { path: "/settings", query: { tab: "service" } },
      },
      {
        path: "logs",
        meta: { requiresAuth: true },
        component: LogsPage,
      },
    ],
  },
  {
    path: "/",
    component: blanklayout,
    children: [
      {
        path: "login",
        component: LoginPage,
      },
      {
        path: "/:pathMatch(.*)*",
        component: errorpage,
      },
    ],
  },
]
