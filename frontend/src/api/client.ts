export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

/** Fetch wrapper: always sends cookies and parses the `{error: {code, message}}` shape (PLAN.md §5). */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(path, { ...init, headers, credentials: 'include' })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const err = body?.error
    // TODO(M1): on 401, redirect to /login.
    throw new ApiError(res.status, err?.code ?? 'HTTP_ERROR', err?.message ?? res.statusText)
  }
  return res.json() as Promise<T>
}
