import type { PluginManifest } from "./types";
import { networking } from "./networking/manifest";
import { career } from "./career/manifest";

// Navigation order.
export const PLUGINS: PluginManifest[] = [career, networking];
