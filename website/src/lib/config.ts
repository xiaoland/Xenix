export function configuredApiOrigin(): string {
  const value = import.meta.env.VITE_API_ORIGIN;
  return typeof value === "string" ? value.replace(/\/$/, "") : "";
}

export function apiUrl(path: string): string {
  const origin = configuredApiOrigin();
  return origin ? `${origin}${path}` : path;
}
