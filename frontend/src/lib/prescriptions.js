import { apiGet, apiRequest } from './api'

export const createPrescription = (d) =>
  apiRequest('/api/prescriptions', { method: 'POST', body: d })
export const listPrescriptions = (patientId) =>
  apiGet(`/api/prescriptions?patient_id=${patientId}`)
export const getPrescription = (id) => apiGet(`/api/prescriptions/${id}`)
export const listOutbox = (status = 'pending') =>
  apiGet(`/api/pharmacy/outbox?status=${status}`)
export const markSent = (id) =>
  apiRequest(`/api/pharmacy/outbox/${id}/sent`, { method: 'POST' })
