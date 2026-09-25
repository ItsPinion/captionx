import { hc } from "hono/client";

import type { AppType } from "@captionx/api";
import { API_PORT } from "@captionx/shared";

/**
 * Base URL for the Hono RPC client.
 *
 * In the browser we always go through the same-origin Next.js rewrite
 * (`/api/* → http://127.0.0.1:${API_PORT}/*`), so the dashboard works no
 * matter which host it is served from (including the preview proxy).
 * On the server we call the API directly inside the sandbox.
 */
function apiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return `${window.location.origin}/api`;
  }
  return `http://127.0.0.1:${API_PORT}`;
}

export const apiClient = hc<AppType>(apiBaseUrl());
