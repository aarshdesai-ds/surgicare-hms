import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { listOutbox, markSent } from '../lib/prescriptions'

function fmtDateTime(iso) {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

export default function Pharmacy() {
  const { t } = useTranslation()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copiedId, setCopiedId] = useState(null)

  const load = useCallback(() => {
    setLoading(true); setError('')
    listOutbox('pending').then((r) => setItems(r.items)).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }, [])
  useEffect(() => { load() }, [load])

  async function copy(o) {
    try {
      await navigator.clipboard.writeText(JSON.stringify(o.payload, null, 2))
      setCopiedId(o.id); setTimeout(() => setCopiedId(null), 1500)
    } catch { /* clipboard may be blocked */ }
  }
  async function send(o) {
    try { await markSent(o.id); load() } catch (e) { setError(e.message) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('pharmacy.title')}</h1>
        {!loading && <span className="occupancy-pill">{t('pharmacy.pending', { n: items.length })}</span>}
      </div>

      <p className="muted staff-note">{t('pharmacy.hint')}</p>
      {error && <div className="alert error">{error}</div>}

      {loading ? (
        <p className="muted">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <div className="card empty-day">{t('pharmacy.none')}</div>
      ) : (
        <div className="rx-outbox">
          {items.map((o) => (
            <div className="card rx-outbox-card" key={o.id}>
              <div className="rx-outbox-head">
                <div>
                  <strong>{o.patient_name}</strong> <span className="mono muted">{o.patient_uhid}</span>
                  <div className="bed-meta">
                    {o.doctor_name || '—'} · {fmtDateTime(o.created_at)}
                  </div>
                </div>
                <div className="rx-outbox-actions">
                  <button className="btn-ghost sm" onClick={() => copy(o)}>
                    {copiedId === o.id ? t('pharmacy.copied') : t('pharmacy.copyJson')}
                  </button>
                  <button className="btn-primary inline sm" onClick={() => send(o)}>
                    {t('pharmacy.markSent')}
                  </button>
                </div>
              </div>
              <ul className="rx-list">
                {(o.payload.items || []).map((it, i) => (
                  <li key={i}>
                    <strong>{it.drug_name}</strong>
                    {it.strength ? ` ${it.strength}` : ''}
                    {it.frequency ? ` · ${it.frequency}` : ''}
                    {it.duration ? ` · ${it.duration}` : ''}
                    {it.quantity ? ` · ${t('rx.qty')} ${it.quantity}` : ''}
                    {it.instructions ? ` — ${it.instructions}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
