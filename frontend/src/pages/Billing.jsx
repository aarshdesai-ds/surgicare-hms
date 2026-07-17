import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'
import PatientPicker from '../components/PatientPicker'
import { listInvoices, createInvoice, money, fmtDate } from '../lib/billing'

export default function Billing() {
  const { t } = useTranslation()
  const nav = useNavigate()
  const { role } = useAuth()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [newOpen, setNewOpen] = useState(false)

  function load() {
    setLoading(true); setError('')
    listInvoices()
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const canManageCatalog = role === 'admin' || role === 'billing'

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('billing.title')}</h1>
        <div className="header-actions">
          {canManageCatalog && (
            <button className="btn-ghost" onClick={() => nav('/billing/services')}>
              {t('billing.priceList')}
            </button>
          )}
          <button className="btn-primary inline" onClick={() => setNewOpen(true)}>
            + {t('billing.newInvoice')}
          </button>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="card table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t('billing.invoiceNo')}</th>
              <th>{t('billing.patient')}</th>
              <th>{t('billing.date')}</th>
              <th>{t('billing.status')}</th>
              <th className="ta-r">{t('billing.total')}</th>
              <th className="ta-r">{t('billing.due')}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="table-empty">{t('common.loading')}</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={6} className="table-empty">{t('billing.none')}</td></tr>
            ) : (
              items.map((i) => (
                <tr key={i.id} className="row-link" onClick={() => nav(`/billing/${i.id}`)}>
                  <td className="mono">{i.invoice_no || t('billing.draft')}</td>
                  <td>{i.patient_name} <span className="mono muted">{i.patient_uhid}</span></td>
                  <td>{fmtDate(i.created_at)}</td>
                  <td><span className={`badge b-${i.status}`}>{t(`billing.status_${i.status}`)}</span></td>
                  <td className="ta-r">{money(i.grand_total)}</td>
                  <td className="ta-r">{money(i.grand_total - i.amount_paid)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {newOpen && (
        <NewInvoiceModal t={t} onClose={() => setNewOpen(false)}
          onCreated={(inv) => nav(`/billing/${inv.id}`)} />
      )}
    </div>
  )
}

function NewInvoiceModal({ t, onClose, onCreated }) {
  const [patient, setPatient] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function create() {
    if (!patient) { setError(t('billing.pickPatient')); return }
    setBusy(true)
    try { onCreated(await createInvoice({ patient_id: patient.id })) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{t('billing.newInvoice')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="field">
            <span className="field-label">{t('billing.patient')}</span>
            <PatientPicker value={patient} onChange={setPatient} placeholder={t('queue.searchPatient')} />
          </div>
          {error && <div className="alert error">{error}</div>}
        </div>
        <div className="modal-foot">
          <button className="btn-ghost" onClick={onClose}>{t('common.cancel')}</button>
          <button className="btn-primary inline" disabled={busy} onClick={create}>
            {t('billing.createDraft')}
          </button>
        </div>
      </div>
    </div>
  )
}
