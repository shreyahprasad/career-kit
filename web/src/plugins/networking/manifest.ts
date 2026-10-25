import type { PluginManifest } from "../types";
import { PeopleIcon } from "@shell/icons";
import { NetworkingPage } from "./NetworkingPage";

export const networking: PluginManifest = {
  id: "networking",
  name: "Networking",
  summary: "People you know, every talk, and who has gone quiet",
  Icon: PeopleIcon,
  Page: NetworkingPage,
  api: "/api/networking/people",
};
