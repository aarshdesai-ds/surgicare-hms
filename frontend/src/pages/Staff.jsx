import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'
import { listStaff, updateStaff, createStaff } from '../lib/staff'

const ROLES = ['admin', 'doctor', 'reception', 'billing', 'nurse']

export default function Staff() {
  const { t } = useTranslation()
  const { role: myRole, user } = useAuth()

  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)

  const load = useCallback(() => {
    setLoading(true); setError('')
    listStaff()
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (myRole === 'admin') load()
  }, [myRole, load])

  if (myRole && myRole !== 'admin') {
    return <div className="page"><div className="alert error">{t('staff.adminOnly')}</div></div>
  }

  async function change(id, patch) {
    try { await updateStaff(id, patch); load() } catch (e) { setError(e.message) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('staff.title')}</h1>
        <button className="btn-primary inline" onClick={() => setShowCreate(true)}>
          + {t('staff.add')}
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="card table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t('staff.name')}</th>
              <th>{t('staff.email')}</th>
              <th>{t('staff.role')}</th>
              <th>{t('staff.status')}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="table-empty">{t('common.loading')}</td></tr>
            ) : (
              items.map((s) => {
                const isSelf = s.id === user?.id
                return (
                  <tr key={s.id}>
                    <td>
                      <NameCell s={s} t={t} onSave={change} />
                      {isSelf && <span className="badge s-spec">{t('staff.you')}</span>}
                    </td>
                    <td>{s.email || '—'}</td>
                    <td>
                      <select
                        value={s.role} disabled={isSelf}
                        onChange={(e) => change(s.id, { role: e.target.value })}
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>{t(`staff.roles.${r}`)}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <button
                        className={`status-toggle ${s.is_active ? 'on' : 'off'}`}
                        disabled={isSelf}
                        onClick={() => change(s.id, { is_active: !s.is_active })}
                      >
                        {s.is_active ? t('staff.active') : t('staff.inactive')}
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      <p className="muted staff-note">{t('staff.note')}</p>

      {showCreate && (
        <StaffCreateModal
          t={t}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load() }}
        />
      )}
    </div>
  )
}

function NameCell({ s, t, onSave }) {
  const [val, setVal] = useState(s.full_name || '')
  useEffect(() => { setVal(s.full_name || '') }, [s.full_name])

  function commit() {
    const v = val.trim()
    if (v !== (s.full_name || '')) onSave(s.id, { full_name: v })
  }

  return (
    <input
      className="name-input"
      value={val}
      placeholder={t('staff.namePlaceholder')}
      onChange={(e) => setVal(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
    />
  )
}

function StaffCreateModal({ t, onClose, onCreated }) {
  const [form, setForm] = useState({
    email: '', password: '', full_name: '', phone: '', role: 'reception',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [showPw, setShowPw] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  async function submit(e) {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      await createStaff({
        email: form.email,
        password: form.password,
        full_name: form.full_name || undefined,
        phone: form.phone || undefined,
        role: form.role,
      })
      onCreated()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <form className="modal" onMouseDown={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="modal-head">
          <h2>{t('staff.createTitle')}</h2>
          <button type="button" className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <label className="field">
            <span>{t('staff.email')}</span>
            <input type="email" value={form.email} onChange={(e) => set('email', e.target.value)} required />
          </label>
          <label className="field">
            <span>{t('staff.password')}</span>
            <div className="password-field">
              <input
                type={showPw ? 'text' : 'password'}
                value={form.password} minLength={6}
                autoComplete="new-password"
                onChange={(e) => set('password', e.target.value)} required
              />
              <button type="button" className="pw-toggle"
                onClick={() => setShowPw((v) => !v)}>
                {showPw ? t('staff.hide') : t('staff.show')}
              </button>
            </div>
          </label>
          <div className="form-grid">
            <label className="field">
              <span>{t('staff.fullName')}</span>
              <input value={form.full_name} onChange={(e) => set('full_name', e.target.value)} />
            </label>
            <label className="field">
              <span>{t('staff.phone')}</span>
              <input value={form.phone} onChange={(e) => set('phone', e.target.value)} />
            </label>
          </div>
          <label className="field">
            <span>{t('staff.role')}</span>
            <select value={form.role} onChange={(e) => set('role', e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{t(`staff.roles.${r}`)}</option>)}
            </select>
          </label>
          {error && <div className="alert error">{error}</div>}
        </div>
        <div className="modal-foot">
          <button type="button" className="btn-ghost" onClick={onClose}>{t('common.cancel')}</button>
          <button type="submit" className="btn-primary inline" disabled={busy}>
            {busy ? t('common.saving') : t('staff.create')}
          </button>
        </div>
      </form>
    </div>
  )
}
