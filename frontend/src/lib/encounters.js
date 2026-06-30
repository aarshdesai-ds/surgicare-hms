import { apiRequest } from './api'

export function listEncounters(patientId) {
  return apiRequest(`/api/encounters?patient_id=${patientId}`)
}

export function createEncounter(data) {
  return apiRequest('/api/encounters', { method: 'POST', body: data })
}
