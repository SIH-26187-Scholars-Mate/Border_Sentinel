// src/api/auth.js
// Matches backend/app/api/routes/auth.py exactly:
//   POST  /auth/login  {email, password} -> {access_token, token_type}
//   GET   /auth/me                       -> {id, email, role, full_name}
//   PATCH /auth/me     {full_name}       -> {id, email, role, full_name}
import { api } from './client'

export function login(email, password) {
  return api.post('/auth/login', { email, password })
}

export function fetchMe() {
  return api.get('/auth/me')
}

export function updateMe(full_name) {
  return api.patch('/auth/me', { full_name })
}
