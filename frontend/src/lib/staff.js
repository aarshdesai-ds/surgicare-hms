import { apiRequest } from './api'

export function listStaff() {
  return apiRequest('/api/staff')
}

export function updateStaff(id, data) {
  return apiRequest(`/api/staff/${id}`, { method: 'PATCH', body: data })
}

export function createStaff(data) {
  return apiRequest('/api/staff', { method: 'POST', body: data })
}
