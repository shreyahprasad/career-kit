import type { PluginManifest } from "../types";
import { CareerIcon } from "@shell/icons";
import { CareerPage } from "./CareerPage";

export const career: PluginManifest = {
  id: "career",
  name: "Career",
  summary: "Roles you are looking at, where each one stands, and what happened",
  Icon: CareerIcon,
  Page: CareerPage,
  api: "/api/career/roles",
};
