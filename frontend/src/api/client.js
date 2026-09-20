// src/api/client.js
// Every backend route lives under this base. Auth token is read from a
// getter function (set by AuthContext) rather than imported directly, to
// avoid a circular import between the client and the auth context.

export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

let getToken = () => null
let onUnauthorized = () => {}

export function registerAuthHooks({ getToken: g, onUnauthorized: h }) {
  getToken = g
  onUnauthorized = h
}

async function request(path, { method = 'GET', body, headers = {} } = {}) {
  const token = getToken()
  const finalHeaders = { 'Content-Type': 'application/json', ...headers }
  if (token) {
    finalHeaders.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${BACKEND_URL}${path}`, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    onUnauthorized()
    throw new ApiError(401, 'Unauthorized')
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || JSON.stringify(data)
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return null
  return res.json()
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  delete: (path) => request(path, { method: 'DELETE' }),
}
