import { apiRequest } from './api'

export function listPatients({ q = '', limit = 20, offset = 0 } = {}) {
  const params = new URLSearchParams({ q, limit, offset })
  return apiRequest(`/api/patients?${params.toString()}`)
}

export function getPatient(id) {
  return apiRequest(`/api/patients/${id}`)
}

export function createPatient(data, { force = false } = {}) {
  return apiRequest(`/api/patients?force=${force}`, { method: 'POST', body: data })
}

export function updatePatient(id, data) {
  return apiRequest(`/api/patients/${id}`, { method: 'PUT', body: data })
}
