import { PLUGINS } from "../plugins/registry";
import { href, useRoute } from "./router";
import { UndoBar } from "./UndoBar";

// Layout: left rail on the Mac and iPad, bottom tab bar on the phone. The undo bar, after a
// delete, sits under the page.

export function App() {
  const [id, ...rest] = useRoute();
  const active = PLUGINS.find((p) => p.id === id) ?? PLUGINS[0];
  const Page = active.Page;

  return (
    <div className="flex h-full flex-col md:flex-row">
      <nav
        aria-label="Dashboards"
        className="hidden w-[var(--nav-rail)] shrink-0 flex-col gap-[var(--gap-block)] border-r border-line px-4 py-[var(--page-margin)] md:flex"
      >
        <div className="px-3 font-mono text-small font-medium tracking-[0.04em] text-fg">career-kit</div>
        <ul className="flex flex-col gap-1">
          {PLUGINS.map(({ id, name, summary, Icon }) => {
            const on = id === active.id;
            return (
              <li key={id}>
                <a
                  href={href(id)}
                  title={summary}
                  aria-current={on ? "page" : undefined}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 transition-colors ${
                    on ? "bg-surface text-fg" : "text-muted hover:bg-surface/60 hover:text-fg"
                  }`}
                >
                  <Icon className={`size-5 ${on ? "text-accent" : ""}`} />
                  <span>{name}</span>
                </a>
              </li>
            );
          })}
        </ul>
        <div className="label mt-auto px-3">this Mac · local</div>
      </nav>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Page path={rest} />
        </main>
        <UndoBar />
      </div>

      <nav
        aria-label="Dashboards"
        className={`flex shrink-0 border-t border-line bg-bg pb-[env(safe-area-inset-bottom,0px)] md:hidden`}
      >
        {PLUGINS.map(({ id, name, Icon }) => {
          const on = id === active.id;
          return (
            <a
              key={id}
              href={href(id)}
              aria-current={on ? "page" : undefined}
              className={`flex flex-1 flex-col items-center gap-1 pt-2.5 pb-2 text-label ${
                on ? "text-fg" : "text-muted"
              }`}
            >
              <Icon className={`size-5 ${on ? "text-accent" : ""}`} />
              {name}
            </a>
          );
        })}
      </nav>
    </div>
  );
}
