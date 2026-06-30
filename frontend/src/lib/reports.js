import { apiGet } from './api'

export function getDayReport(day) {
  return apiGet(`/api/reports/day?day=${day}`)
}
