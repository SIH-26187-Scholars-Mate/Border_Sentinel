// src/api/cameras.js
// Matches backend/app/schemas/camera.py + app/api/routes/cameras.py.
import { api } from './client'

export function listCameras() {
  return api.get('/cameras')
}

export function getCamera(id) {
  return api.get(`/cameras/${id}`)
}

export function createCamera({ name, location, latitude, longitude, stream_url, is_active = true }) {
  return api.post('/cameras', { name, location, latitude, longitude, stream_url, is_active })
}


export function updateCamera(id, data) {
  return api.patch(`/cameras/${id}`, data)
}

export function deleteCamera(id) {
  return api.delete(`/cameras/${id}`)
}

export function startCamera(id) { return api.post(`/cameras/${id}/start`) }
export function stopCamera(id) { return api.post(`/cameras/${id}/stop`) }
export function getCameraWorker(id) { return api.get(`/cameras/${id}/worker`) }

export function stopAllCameras() { return api.post(`/cameras/stop-all`) }
