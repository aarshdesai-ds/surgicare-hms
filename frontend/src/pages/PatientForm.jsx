import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { createPatient, getPatient, updatePatient } from '../lib/patients'

const EMPTY = {
  first_name: '',
  last_name: '',
  dob: '',
  gender: '',
  phone: '',
  alt_phone: '',
  address: '',
  blood_group: '',
  abha_number: '',
  allergies: '',
}

// Strip empty-string fields so optional values are sent as omitted, not "".
function clean(form) {
  const out = {}
  for (const [k, v] of Object.entries(form)) {
    if (v !== '' && v !== null && v !== undefined) out[k] = v
  }
  return out
}

export default function PatientForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = Boolean(id)

  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [duplicates, setDuplicates] = useState(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(isEdit)

  useEffect(() => {
    if (!isEdit) return
    getPatient(id)
      .then((p) =>
        setForm({
          ...EMPTY,
          ...Object.fromEntries(
            Object.keys(EMPTY).map((k) => [k, p[k] ?? '']),
          ),
        }),
      )
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function submit(e, force = false) {
    e?.preventDefault()
    setError('')
    setFieldErrors({})
    setSaving(true)
    try {
      const payload = clean(form)
      if (isEdit) {
        await updatePatient(id, payload)
        navigate(`/patients/${id}`)
      } else {
        const created = await createPatient(payload, { force })
        navigate(`/patients/${created.id}`)
      }
    } catch (err) {
      if (err.code === 'DUPLICATE_PATIENT') {
        setDuplicates(err.fields?.duplicates || [])
      } else if (err.code === 'VALIDATION_ERROR' && err.fields) {
        setFieldErrors(err.fields)
        setError(t('patients.fixErrors'))
      } else {
        setError(err.message)
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="page"><p className="muted">{t('common.loading')}</p></div>

  return (
    <div className="page">
      <h1 className="page-title">
        {isEdit ? t('patients.editTitle') : t('patients.new')}
      </h1>

      {error && <div className="alert error">{error}</div>}

      {duplicates && (
        <div className="alert warn">
          <strong>{t('patients.duplicateWarning')}</strong>
          <ul className="dup-list">
            {duplicates.map((d) => (
              <li key={d.id}>
                <span className="mono">{d.uhid}</span> — {d.first_name} {d.last_name || ''} · {d.phone}
              </li>
            ))}
          </ul>
          <div className="dup-actions">
            <button className="btn-ghost" type="button" onClick={() => setDuplicates(null)}>
              {t('common.cancel')}
            </button>
            <button className="btn-primary inline" type="button" disabled={saving} onClick={(e) => submit(e, true)}>
              {t('patients.registerAnyway')}
            </button>
          </div>
        </div>
      )}

      <form className="card form-card" onSubmit={(e) => submit(e, false)}>
        <div className="form-grid">
          <Field label={t('patients.firstName')} required err={fieldErrors.first_name}>
            <input value={form.first_name} onChange={(e) => set('first_name', e.target.value)} required />
          </Field>
          <Field label={t('patients.lastName')} err={fieldErrors.last_name}>
            <input value={form.last_name} onChange={(e) => set('last_name', e.target.value)} />
          </Field>
          <Field label={t('patients.phone')} required err={fieldErrors.phone}>
            <input value={form.phone} onChange={(e) => set('phone', e.target.value)} placeholder="9876543210" required />
          </Field>
          <Field label={t('patients.altPhone')} err={fieldErrors.alt_phone}>
            <input value={form.alt_phone} onChange={(e) => set('alt_phone', e.target.value)} />
          </Field>
          <Field label={t('patients.dob')} err={fieldErrors.dob}>
            <input type="date" value={form.dob} onChange={(e) => set('dob', e.target.value)} />
          </Field>
          <Field label={t('patients.gender')} err={fieldErrors.gender}>
            <select value={form.gender} onChange={(e) => set('gender', e.target.value)}>
              <option value="">—</option>
              <option value="M">{t('patients.male')}</option>
              <option value="F">{t('patients.female')}</option>
              <option value="O">{t('patients.other')}</option>
            </select>
          </Field>
          <Field label={t('patients.bloodGroup')} err={fieldErrors.blood_group}>
            <input value={form.blood_group} onChange={(e) => set('blood_group', e.target.value)} placeholder="O+" />
          </Field>
          <Field label={t('patients.abha')} err={fieldErrors.abha_number}>
            <input value={form.abha_number} onChange={(e) => set('abha_number', e.target.value)} />
          </Field>
          <Field label={t('patients.address')} wide err={fieldErrors.address}>
            <textarea rows={2} value={form.address} onChange={(e) => set('address', e.target.value)} />
          </Field>
          <Field label={t('patients.allergies')} wide err={fieldErrors.allergies}>
            <textarea rows={2} value={form.allergies} onChange={(e) => set('allergies', e.target.value)} />
          </Field>
        </div>

        <div className="form-actions">
          <button className="btn-ghost" type="button" onClick={() => navigate(-1)}>
            {t('common.cancel')}
          </button>
          <button className="btn-primary inline" type="submit" disabled={saving}>
            {saving ? t('common.saving') : isEdit ? t('common.save') : t('patients.register')}
          </button>
        </div>
      </form>
    </div>
  )
}

function Field({ label, required, wide, err, children }) {
  return (
    <label className={`field${wide ? ' wide' : ''}`}>
      <span>
        {label} {required && <em className="req">*</em>}
      </span>
      {children}
      {err && <small className="field-err">{err}</small>}
    </label>
  )
}
