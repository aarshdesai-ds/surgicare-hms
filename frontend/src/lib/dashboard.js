import { apiGet } from './api'

export function getDashboard(day) {
  return apiGet(`/api/dashboard?day=${day}`)
}
