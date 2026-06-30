import { apiRequest } from './api'

export function listDoctors() {
  return apiRequest('/api/doctors')
}

export function listAppointments(day, doctorId) {
  const params = new URLSearchParams({ day })
  if (doctorId) params.set('doctor_id', doctorId)
  return apiRequest(`/api/appointments?${params.toString()}`)
}

export function createAppointment(data) {
  return apiRequest('/api/appointments', { method: 'POST', body: data })
}

export function updateAppointmentStatus(id, status) {
  return apiRequest(`/api/appointments/${id}/status`, {
    method: 'PATCH',
    body: { status },
  })
}
