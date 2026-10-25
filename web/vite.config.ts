import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { readTheme, THEME } from "./scripts/palette.mjs";
import securityHeaders from "./security-headers.json" with { type: "json" };

/** The browser's bar color (index.html theme-color) is the theme's --bg, read at build time. */
const themeColor = () => ({
  name: "theme-color",
  transformIndexHtml: (html: string) => html.replace("%THEME_BG%", readTheme(THEME)["--bg"]),
});

export default defineConfig(({ mode }) => {
  // NETWORKING_WRITER, from the shell, points a branch test at its own writer and a copy of networking.db.
  const { NETWORKING_WRITER = "http://127.0.0.1:8120" } = loadEnv(mode, ".", "NETWORKING_");
  // CAREER_WRITER, likewise, for the career writer and a copy of career.db.
  const { CAREER_WRITER = "http://127.0.0.1:8140" } = loadEnv(mode, ".", "CAREER_");
  // API_SERVER points reads at a branch's API on the same copies, so a test change shows on the page.
  const { API_SERVER = "http://127.0.0.1:8100" } = loadEnv(mode, ".", "API_");
  // TAILNET_HOSTS, this Mac's tailnet names, from the same .env the servers read (writekit
  // identity.py): career-kit/.env, or CAREER_KIT_ENV from a worktree, which has none of its own.
  const { CAREER_KIT_ENV = "../.env" } = loadEnv(mode, ".", "CAREER_KIT_");
  const { TAILNET_HOSTS = "" } = loadEnv(mode, CAREER_KIT_ENV.replace(/[^/]*$/, ""), "TAILNET_");
  // WEB_PORT is where start.sh serves the built site (vite preview); the dev server is one above.
  const { WEB_PORT = "5180" } = loadEnv(mode, ".", "WEB_");
  const local = {
    // Local only. The phone reaches the site through `tailscale serve`, never a public bind.
    host: "127.0.0.1",
    strictPort: true,
    // The tailnet names, as the phone sends them through `tailscale serve`.
    allowedHosts: TAILNET_HOSTS.split(",").map((h) => h.trim().toLowerCase()).filter(Boolean),
    // No other origin may read or send through it, not even another page on this Mac: the
    // writers' X-Career-Kit-Write header only keeps other pages out while nothing answers CORS.
    cors: false,
    // Data comes from the read-only server in ../api. Networking and career changes go
    // to their writers in ../tools; listed first, they win.
    proxy: {
      "/api/networking/write": NETWORKING_WRITER,
      "/api/career/write": CAREER_WRITER,
      "/api": API_SERVER,
    },
  };
  return {
    plugins: [react(), tailwindcss(), themeColor()],
    // The pages import the shell as @shell/..., so an app that hosts them (with career-kit as a
    // git submodule) points @shell at its own shell. tsconfig.json paths says the same.
    resolve: { alias: { "@shell": "/src/shell" } },
    // pnpm dev, while changing the code.
    server: { ...local, port: Number(WEB_PORT) + 1 },
    // start.sh: the built site, with changes sent on to the writers like the dev server does.
    // The page's own headers, as the read API sends them (api/main.py): the dev server leaves them
    // off, since its hot reload runs inline scripts.
    preview: { ...local, port: Number(WEB_PORT), headers: securityHeaders },
  };
});
