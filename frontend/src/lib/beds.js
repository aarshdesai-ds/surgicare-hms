import { apiGet, apiRequest } from './api'

export const listBeds = () => apiGet('/api/beds')
export const admitPatient = (d) => apiRequest('/api/admissions', { method: 'POST', body: d })
export const transferAdmission = (id, toBedId) =>
  apiRequest(`/api/admissions/${id}/transfer`, { method: 'POST', body: { to_bed_id: toBedId } })
export const dischargeAdmission = (id, summary) =>
  apiRequest(`/api/admissions/${id}/discharge`, { method: 'POST', body: { discharge_summary: summary } })
