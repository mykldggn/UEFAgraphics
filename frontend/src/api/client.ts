import { API_BASE } from '../utils/constants'

function buildUrl(path: string, params?: Record<string, string | number>): string {
  // API_BASE may be absolute (https://...) or relative (/api).
  // Use window.location.origin as base only for relative paths.
  const base = API_BASE.startsWith('http') ? API_BASE : `${window.location.origin}${API_BASE}`
  const url = new URL(path, base + '/')
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }
  return url.toString()
}

async function request<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const res = await fetch(buildUrl(path, params), { cache: 'no-store' })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

/** Return a full URL string for an infographic image (PNG). */
export function imgUrl(path: string, params?: Record<string, string | number>): string {
  return buildUrl(path, params)
}

export default request
