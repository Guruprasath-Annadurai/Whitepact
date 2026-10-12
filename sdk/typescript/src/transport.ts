/** Refuse credentials in URLs and bearer transport over remote plaintext HTTP. */
export function validateBaseUrl(baseUrl: string, apiKey: string): void {
  const message = "SDK base URL must use HTTPS or explicit loopback HTTP for bearer credentials";
  let url: URL;
  try { url = new URL(baseUrl); } catch { throw new Error(message); }
  if (url.username || url.password || !url.hostname || !["http:", "https:"].includes(url.protocol)) {
    throw new Error(message);
  }
  if (!apiKey || url.protocol === "https:") return;
  if (url.hostname === "localhost" || url.hostname === "[::1]" || /^127\.\d+\.\d+\.\d+$/.test(url.hostname)) return;
  throw new Error(message);
}
