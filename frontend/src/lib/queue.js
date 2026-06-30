import { apiRequest } from './api'

export function listDoctors() {
  return apiRequest('/api/doctors')
}

export function listSessions(day, doctorId) {
  const p = new URLSearchParams({ day })
  if (doctorId) p.set('doctor_id', doctorId)
  return apiRequest(`/api/opd-sessions?${p.toString()}`)
}

export function upsertSession(data) {
  return apiRequest('/api/opd-sessions', { method: 'PUT', body: data })
}

export function listQueue(day, doctorId) {
  const p = new URLSearchParams({ day })
  if (doctorId) p.set('doctor_id', doctorId)
  return apiRequest(`/api/queue?${p.toString()}`)
}

export function addToQueue(data) {
  return apiRequest('/api/queue', { method: 'POST', body: data })
}

export function updateQueueStatus(id, status) {
  return apiRequest(`/api/queue/${id}/status`, { method: 'PATCH', body: { status } })
}
