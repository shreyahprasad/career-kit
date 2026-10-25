import type { ComponentType } from "react";

/**
 * A dashboard is a folder under src/plugins/ with a manifest. Adding one means adding a
 * folder and listing it in registry.ts; the shell does not change.
 * Its data loader is a FastAPI route in `api/`, never a direct file read.
 */
export interface PluginManifest {
  id: string; // route segment: #/<id>
  name: string;
  summary: string; // one line, shown on hover and in the command bar later
  Icon: ComponentType<{ className?: string }>;
  Page: ComponentType<{ path: string[] }>; // path = route segments after the id
  api?: string; // e.g. "/api/career/roles"
}
