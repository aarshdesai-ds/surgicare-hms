import { apiRequest } from './api'

export function listTheatres() {
  return apiRequest('/api/theatres')
}

export function listCases(day, theatreId, surgeonId) {
  const p = new URLSearchParams({ day })
  if (theatreId) p.set('theatre_id', theatreId)
  if (surgeonId) p.set('surgeon_id', surgeonId)
  return apiRequest(`/api/ot-cases?${p.toString()}`)
}

export function addCase(data) {
  return apiRequest('/api/ot-cases', { method: 'POST', body: data })
}

export function updateCaseStatus(id, status) {
  return apiRequest(`/api/ot-cases/${id}/status`, { method: 'PATCH', body: { status } })
}

export function moveCase(id, direction) {
  return apiRequest(`/api/ot-cases/${id}/move`, { method: 'PATCH', body: { direction } })
}
