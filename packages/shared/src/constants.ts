/** Default port the Hono API listens on. */
export const API_PORT = 4000;

/** Port the Next.js dashboard listens on. */
export const WEB_PORT = 3000;

/**
 * Path prefix the dashboard uses to reach the API through the Next.js
 * rewrite (`/api/* → http://127.0.0.1:${API_PORT}/*`).
 */
export const API_PROXY_PREFIX = "/api";

/** Dashboard header copy. */
export const APP_NAME = "Image–Caption Extraction";
export const APP_SUBTITLE = "NCERT PDF Automation";
