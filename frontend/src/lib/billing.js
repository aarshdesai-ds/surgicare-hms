import { apiGet, apiRequest } from './api'

// --- catalog ---
export const listServices = (activeOnly = false) =>
  apiGet(`/api/services?active_only=${activeOnly}`)
export const createService = (d) => apiRequest('/api/services', { method: 'POST', body: d })
export const updateService = (id, d) =>
  apiRequest(`/api/services/${id}`, { method: 'PATCH', body: d })

// --- invoices ---
export const listInvoices = ({ patientId, limit = 20, offset = 0 } = {}) => {
  const p = new URLSearchParams({ limit, offset })
  if (patientId) p.set('patient_id', patientId)
  return apiGet(`/api/invoices?${p.toString()}`)
}
export const createInvoice = (d) => apiRequest('/api/invoices', { method: 'POST', body: d })
export const getInvoice = (id) => apiGet(`/api/invoices/${id}`)
export const addLineItem = (id, d) =>
  apiRequest(`/api/invoices/${id}/items`, { method: 'POST', body: d })
export const removeLineItem = (id, itemId) =>
  apiRequest(`/api/invoices/${id}/items/${itemId}`, { method: 'DELETE' })
export const setDiscount = (id, discount) =>
  apiRequest(`/api/invoices/${id}/discount`, { method: 'PATCH', body: { discount } })
export const finalizeInvoice = (id) =>
  apiRequest(`/api/invoices/${id}/finalize`, { method: 'POST' })
export const cancelInvoice = (id) =>
  apiRequest(`/api/invoices/${id}/cancel`, { method: 'POST' })
export const addPayment = (id, d) =>
  apiRequest(`/api/invoices/${id}/payments`, { method: 'POST', body: d })

// --- online payments (Razorpay payment links) ---
export const getPaymentsConfig = () => apiGet('/api/payments/config')
export const createPaymentLink = (id, amount) =>
  apiRequest(`/api/invoices/${id}/payment-link`, {
    method: 'POST', body: amount ? { amount } : undefined,
  })
export const getPaymentLink = (id) => apiGet(`/api/invoices/${id}/payment-link`)
export const syncPaymentLink = (id) =>
  apiRequest(`/api/invoices/${id}/payment-link/sync`, { method: 'POST' })

// --- shared formatting ---
export const money = (n) =>
  '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
