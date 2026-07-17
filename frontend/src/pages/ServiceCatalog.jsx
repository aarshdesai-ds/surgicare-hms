import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'
import { listServices, createService, updateService } from '../lib/billing'

const CATS = ['consultation', 'procedure', 'bed', 'ot', 'lab', 'pharmacy', 'other']

export default function ServiceCatalog() {
  const { t } = useTranslation()
  const nav = useNavigate()
  const { role } = useAuth()
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)

  const load = useCallback(() => {
    listServices(false).then((r) => setItems(r.items)).catch((e) => setError(e.message))
  }, [])
  const canManage = role === 'admin' || role === 'billing'
  useEffect(() => { if (canManage) load() }, [canManage, load])

  if (role && !canManage) {
    return <div className="page"><div className="alert error">{t('billing.catalogAdminOnly')}</div></div>
  }

  async function save(id, patch) {
    try { await updateService(id, patch); load() } catch (e) { setError(e.message) }
  }

  return (
    <div className="page">
      <button className="btn-ghost back-link" onClick={() => nav('/billing')}>
        ‹ {t('billing.title')}
      </button>
      <div className="page-header">
        <h1 className="page-title">{t('billing.priceList')}</h1>
        <button className="btn-primary inline" onClick={() => setShowAdd(true)}>
          + {t('billing.addService')}
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="card table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t('billing.service')}</th>
              <th>{t('billing.category')}</th>
              <th className="ta-r">{t('billing.price')}</th>
              <th className="ta-r">{t('billing.gst')} %</th>
              <th>{t('staff.status')}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{t(`billing.cat_${s.category}`)}</td>
                <td className="ta-r"><NumInput value={s.unit_price} onSave={(v) => save(s.id, { unit_price: v })} /></td>
                <td className="ta-r"><NumInput value={s.gst_rate} onSave={(v) => save(s.id, { gst_rate: v })} /></td>
                <td>
                  <button className={`status-toggle ${s.is_active ? 'on' : 'off'}`}
                    onClick={() => save(s.id, { is_active: !s.is_active })}>
                    {s.is_active ? t('staff.active') : t('staff.inactive')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="muted staff-note">{t('billing.priceNote')}</p>

      {showAdd && (
        <AddServiceModal t={t} onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); load() }} />
      )}
    </div>
  )
}

function NumInput({ value, onSave }) {
  const [val, setVal] = useState(String(Number(value)))
  useEffect(() => { setVal(String(Number(value))) }, [value])
  function commit() {
    const v = Number(val)
    if (!Number.isNaN(v) && v !== Number(value)) onSave(v)
  }
  return (
    <input className="num-input" type="number" min="0" step="0.01" value={val}
      onChange={(e) => setVal(e.target.value)} onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }} />
  )
}

function AddServiceModal({ t, onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', category: 'other', unit_price: '0', gst_rate: '0' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  async function submit(e) {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      await createService({
        name: form.name, category: form.category,
        unit_price: Number(form.unit_price) || 0, gst_rate: Number(form.gst_rate) || 0,
      })
      onCreated()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <form className="modal" onMouseDown={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="modal-head">
          <h2>{t('billing.addService')}</h2>
          <button type="button" className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <label className="field">
            <span>{t('billing.service')}</span>
            <input value={form.name} onChange={(e) => set('name', e.target.value)} required />
          </label>
          <div className="form-grid">
            <label className="field">
              <span>{t('billing.category')}</span>
              <select value={form.category} onChange={(e) => set('category', e.target.value)}>
                {CATS.map((c) => <option key={c} value={c}>{t(`billing.cat_${c}`)}</option>)}
              </select>
            </label>
            <label className="field">
              <span>{t('billing.price')}</span>
              <input type="number" min="0" step="0.01" value={form.unit_price} onChange={(e) => set('unit_price', e.target.value)} />
            </label>
            <label className="field">
              <span>{t('billing.gst')} %</span>
              <input type="number" min="0" max="100" value={form.gst_rate} onChange={(e) => set('gst_rate', e.target.value)} />
            </label>
          </div>
          {error && <div className="alert error">{error}</div>}
        </div>
        <div className="modal-foot">
          <button type="button" className="btn-ghost" onClick={onClose}>{t('common.cancel')}</button>
          <button type="submit" className="btn-primary inline" disabled={busy}>
            {busy ? t('common.saving') : t('billing.addService')}
          </button>
        </div>
      </form>
    </div>
  )
}
