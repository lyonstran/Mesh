export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

interface ApiOptions extends RequestInit {
  /** Let the caller handle 401 instead of redirecting to /login (used by the auth guard). */
  allow401?: boolean
  json?: unknown
}

/** Fetch wrapper: always sends cookies and parses the `{error: {code, message}}` shape (PLAN.md §5). */
export async function api<T>(path: string, { allow401, json, ...init }: ApiOptions = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (json !== undefined) {
    headers.set('Content-Type', 'application/json')
    init.body = JSON.stringify(json)
  }
  const res = await fetch(path, { ...init, headers, credentials: 'include' })
  if (!res.ok) {
    if (res.status === 401 && !allow401 && window.location.pathname !== '/login') {
      window.location.assign('/login')
    }
    const body = await res.json().catch(() => null)
    const err = body?.error
    throw new ApiError(res.status, err?.code ?? 'HTTP_ERROR', err?.message ?? res.statusText)
  }
  return res.json() as Promise<T>
}

export const post = <T>(path: string, json?: unknown) => api<T>(path, { method: 'POST', json: json ?? {} })
