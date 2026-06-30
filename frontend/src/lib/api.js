import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

/**
 * Call the FastAPI backend. When `auth` is true, attaches the current
 * Supabase access token as a Bearer header. Throws an Error with the
 * backend's error-envelope message on non-2xx responses.
 */
export async function apiRequest(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }

  if (auth) {
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  const payload = await res.json().catch(() => ({}))

  if (!res.ok) {
    const err = payload?.error || { code: 'ERROR', message: res.statusText }
    const error = new Error(err.message || 'Request failed')
    error.code = err.code
    error.fields = err.fields
    error.status = res.status
    throw error
  }
  return payload
}

export const apiGet = (path, opts) => apiRequest(path, { ...opts, method: 'GET' })
