// App chrome: the React counterpart of Streamlit's three-column shell
// (nav_col | page_col | log_col). The left sidebar is grouped like Main.py
// NAV_PAGES (creation / publish / config) and collapsible; the generation log
// column is replaced by a floating LogDock (collapsed by default, expands as
// a 3/4-width modal); the center hosts the active route page passed as children.
import { useEffect, useState, type ReactNode } from "react";
import { useSession } from "../app/session";
import { navigate } from "../app/router";
import { LANGUAGES, useI18n, type Lang } from "../i18n";
import { LogDock } from "../features/logs/LogRail";

type NavItem = { route: string; label: string; match: (p: string) => boolean };
type NavGroup = { label: string; items: NavItem[] };

const is =
  (prefix: string) =>
  (p: string) =>
    p === prefix || p.startsWith(prefix + "/");

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Nav Group Creation",
    items: [
      { route: "/quick", label: "Nav Quick Film", match: is("/quick") },
      { route: "/pro", label: "Nav Pro Drama", match: is("/pro") },
    ],
  },
  {
    label: "Nav Group Publish",
    items: [
      { route: "/jobs", label: "Task Manager", match: is("/jobs") },
      { route: "/videos", label: "Nav Videos Library", match: is("/videos") },
      { route: "/materials", label: "Nav Materials Library", match: is("/materials") },
      { route: "/publish-history", label: "Publish History Tab", match: is("/publish-history") },
    ],
  },
  {
    label: "Nav Group Config",
    items: [
      { route: "/config/llm", label: "Service Providers Tab", match: is("/config/llm") },
      { route: "/config/material", label: "Material API Tab", match: is("/config/material") },
      { route: "/config/publish", label: "Auto-Publish Settings", match: is("/config/publish") },
      { route: "/config/presets", label: "Preset Library", match: is("/config/presets") },
      { route: "/settings", label: "Settings", match: is("/settings") },
    ],
  },
];

const COLLAPSE_KEY = "cf_nav_collapsed";

export function Shell({ children }: { children: ReactNode }) {
  const { authRequired, logout } = useSession();
  const { t, lang, setLang } = useI18n();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const [pathname, setPathname] = useState(window.location.pathname);

  // Each route mounts its own Gate→Shell, so re-read the path on mount; the
  // popstate listener keeps back/forward in sync within a persistent mount.
  useEffect(() => {
    const sync = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", sync);
    sync();
    return () => {
      window.removeEventListener("popstate", sync);
    };
  }, []);

  function go(route: string) {
    navigate(route);
    setPathname(route);
  }

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <div className="shell">
      <aside className={`sidebar${collapsed ? " collapsed" : ""}`}>
        <div className="sidebar-top">
          {!collapsed && (
            <div className="brand cf-logo">
              <svg
                className="brand-mark"
                viewBox="0 0 24 24"
                width="20"
                height="20"
                aria-hidden="true"
              >
                <rect
                  x="2"
                  y="2"
                  width="20"
                  height="20"
                  rx="6"
                  fill="var(--cf-accent, var(--primary))"
                  opacity="0.9"
                />
                <path d="M9.5 7.5v9l8-4.5z" fill="var(--cf-mark-tri, #F5D0FE)" />
              </svg>
              <span>ChangoFilm</span>
            </div>
          )}
          <button
            className="btn ghost nav-toggle"
            onClick={toggleCollapsed}
            title={collapsed ? t("Expand Navigation") : t("Collapse Navigation")}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>
        <nav className="side-nav" data-testid="shell-nav">
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group.label}>
              {!collapsed && <div className="nav-group-label">{t(group.label)}</div>}
              {group.items.map((item) => (
                <button
                  key={item.route}
                  className={item.match(pathname) ? "nav-item active" : "nav-item"}
                  onClick={() => go(item.route)}
                  title={t(item.label)}
                >
                  {t(item.label)}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <div className="main-col">
        <div className="topbar">
          <div className="topbar-spacer" />
          <select
            className="lang-select"
            data-testid="lang-select"
            value={lang}
            onChange={(e) => setLang(e.target.value as Lang)}
          >
            {LANGUAGES.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
          {authRequired && (
            <button className="btn ghost" onClick={() => logout().then(() => navigate("/login"))}>
              {t("Sign out")}
            </button>
          )}
        </div>
        <main className="content">{children}</main>
      </div>

      <LogDock />
    </div>
  );
}
