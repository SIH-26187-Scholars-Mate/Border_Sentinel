// src/api/alerts.js
// Matches backend/app/api/routes/alerts.py exactly.
// NOTE: the endpoint is /alerts/{id}/acknowledge, NOT /resolve.
import { api } from './client'

export function listAlerts(cameraId) {
  const query = cameraId ? `?camera_id=${cameraId}` : ''
  return api.get(`/alerts${query}`)
}

export function getAlert(id) {
  return api.get(`/alerts/${id}`)
}

export function acknowledgeAlert(id) {
  return api.patch(`/alerts/${id}/acknowledge`)
}
