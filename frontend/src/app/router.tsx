import { type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  RouterProvider,
  createRootRoute,
  createRoute,
  createRouter,
  useParams,
  redirect,
} from "@tanstack/react-router";
import { SessionProvider, useSession } from "./session";
import { I18nProvider } from "../i18n";
import { Shell } from "../features/Shell";
import { LoginPage } from "../features/auth/LoginPage";
import { QuickPage } from "../features/generate/QuickPage";
import { ProPage } from "../features/generate/ProPage";
import { TasksPage } from "../features/tasks/TasksPage";
import { TaskDetail } from "../features/tasks/TaskDetail";
import { VideosLibraryPage } from "../features/library/VideosLibraryPage";
import { MaterialsLibraryPage } from "../features/library/MaterialsLibraryPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { ProvidersPage, MaterialPage, PresetsConfigPage } from "../features/config/ConfigPages";
import { PublishPage } from "../features/publish/PublishPage";
import { PublishHistoryPage } from "../features/publish/PublishHistoryPage";
import { SeriesPage } from "../features/series/SeriesPage";
import { initTheme } from "../theme/brandTheme";

// Apply the persisted brand theme before first paint so the shell never
// flashes un-themed defaults (Streamlit applies it at session start).
initTheme();

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

// Session gate + product chrome, shared by every app route. Mirrors the
// Streamlit three-column shell (left grouped menu / center page / right logs).
function Gate({ children }: { children: ReactNode }) {
  const { ready, authRequired, valid } = useSession();
  if (!ready) return <div className="loading">Loading…</div>;
  if (authRequired && !valid) return <LoginPage />;
  return <Shell>{children}</Shell>;
}

const rootRoute = createRootRoute({ component: () => <Outlet /> });

// Landing redirects to the quick route (快速成片), matching Main.py default page.
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/quick" });
  },
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: () => <LoginPage />,
});

const quickRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/quick",
  component: () => <Gate><QuickPage /></Gate>,
});

const proRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/pro",
  component: () => <Gate><ProPage /></Gate>,
});

const tasksRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs",
  component: () => <Gate><TasksPage /></Gate>,
});

function TaskDetailScreen() {
  const { taskId } = useParams({ from: "/jobs/$taskId" });
  return <Gate><TaskDetail taskId={taskId} /></Gate>;
}
const taskDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs/$taskId",
  component: TaskDetailScreen,
});

// Library pages: finished videos (state + disk history) and per-task artifacts.
const videosLibraryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/videos",
  component: () => <Gate><VideosLibraryPage /></Gate>,
});

const materialsLibraryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/materials",
  component: () => <Gate><MaterialsLibraryPage /></Gate>,
});

const publishHistoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/publish-history",
  component: () => <Gate><PublishHistoryPage /></Gate>,
});

const providersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/config/llm",
  component: () => <Gate><ProvidersPage /></Gate>,
});

const materialRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/config/material",
  component: () => <Gate><MaterialPage /></Gate>,
});

const autoPublishRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/config/publish",
  component: () => <Gate><PublishPage /></Gate>,
});

const presetsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/config/presets",
  component: () => <Gate><PresetsConfigPage /></Gate>,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: () => <Gate><SettingsPage /></Gate>,
});

const seriesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/series",
  component: () => <Gate><SeriesPage /></Gate>,
});

function SeriesDetailScreen() {
  const { sid } = useParams({ from: "/series/$sid" });
  return <Gate><SeriesPage sid={sid} /></Gate>;
}
const seriesDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/series/$sid",
  component: SeriesDetailScreen,
});

// Unknown deep links fall back to the quick route (the server SPA fallback
// already returns index.html for non-/api, non-/tasks GET 404s).
const catchAllRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/$",
  component: () => <Gate><QuickPage /></Gate>,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  quickRoute,
  proRoute,
  tasksRoute,
  taskDetailRoute,
  videosLibraryRoute,
  materialsLibraryRoute,
  publishHistoryRoute,
  providersRoute,
  materialRoute,
  autoPublishRoute,
  presetsRoute,
  settingsRoute,
  seriesRoute,
  seriesDetailRoute,
  catchAllRoute,
]);

const router = createRouter({ routeTree });

// Stable imperative API used by pages that predate/avoid per-route hooks;
// backed by the TanStack router instance so history stays typed the same.
export function navigate(to: string) {
  void router.navigate({ to: to as never });
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <SessionProvider>
          <RouterProvider router={router} />
        </SessionProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
