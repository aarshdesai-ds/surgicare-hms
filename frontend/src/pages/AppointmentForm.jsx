import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { createAppointment, listDoctors } from '../lib/appointments'
import { listPatients } from '../lib/patients'

const DURATIONS = [15, 30, 45, 60]

export default function AppointmentForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [sp] = useSearchParams()

  const [doctors, setDoctors] = useState([])
  const [patient, setPatient] = useState(null)
  const [doctorId, setDoctorId] = useState(sp.get('doctor_id') || '')
  const [date, setDate] = useState(sp.get('date') || '')
  const [timeStr, setTimeStr] = useState('10:00')
  const [duration, setDuration] = useState(15)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    listDoctors().then((d) => {
      setDoctors(d)
      if (!doctorId && d.length) setDoctorId(String(d[0].id))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (!patient) { setError(t('appointments.pickPatient')); return }
    setSaving(true)
    try {
      const scheduled_at = new Date(`${date}T${timeStr}`).toISOString()
      await createAppointment({
        patient_id: patient.id,
        doctor_id: Number(doctorId),
        scheduled_at,
        duration_min: Number(duration),
        reason: reason || undefined,
      })
      navigate(`/appointments?date=${date}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">{t('appointments.book')}</h1>
      {error && <div className="alert error">{error}</div>}

      <form className="card form-card" onSubmit={submit}>
        <div className="form-grid">
          <div className="field wide">
            <span>{t('appointments.patient')} <em className="req">*</em></span>
            <PatientPicker patient={patient} onPick={setPatient} t={t} />
          </div>

          <label className="field">
            <span>{t('appointments.doctor')} <em className="req">*</em></span>
            <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)} required>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>{d.full_name}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>{t('appointments.date')} <em className="req">*</em></span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </label>

          <label className="field">
            <span>{t('appointments.time')} <em className="req">*</em></span>
            <input type="time" value={timeStr} onChange={(e) => setTimeStr(e.target.value)} required />
          </label>

          <label className="field">
            <span>{t('appointments.duration')}</span>
            <select value={duration} onChange={(e) => setDuration(e.target.value)}>
              {DURATIONS.map((m) => (
                <option key={m} value={m}>{m} {t('appointments.minutes')}</option>
              ))}
            </select>
          </label>

          <label className="field wide">
            <span>{t('appointments.reason')}</span>
            <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
        </div>

        <div className="form-actions">
          <button className="btn-ghost" type="button" onClick={() => navigate(-1)}>
            {t('common.cancel')}
          </button>
          <button className="btn-primary inline" type="submit" disabled={saving}>
            {saving ? t('common.saving') : t('appointments.book')}
          </button>
        </div>
      </form>
    </div>
  )
}

function PatientPicker({ patient, onPick, t }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!q.trim()) { setResults([]); return }
    const id = setTimeout(async () => {
      try {
        const r = await listPatients({ q, limit: 8 })
        setResults(r.items)
        setOpen(true)
      } catch { /* ignore */ }
    }, 250)
    return () => clearTimeout(id)
  }, [q])

  if (patient) {
    return (
      <div className="picker-selected">
        <span>{patient.first_name} {patient.last_name || ''} · <span className="mono">{patient.uhid}</span></span>
        <button type="button" className="btn-ghost sm" onClick={() => onPick(null)}>
          {t('common.change')}
        </button>
      </div>
    )
  }

  return (
    <div className="picker">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t('appointments.searchPatient')}
        onFocus={() => results.length && setOpen(true)}
      />
      {open && results.length > 0 && (
        <ul className="picker-results">
          {results.map((p) => (
            <li
              key={p.id}
              onMouseDown={(e) => { e.preventDefault(); onPick(p); setOpen(false); setQ('') }}
            >
              {p.first_name} {p.last_name || ''} <span className="mono muted">{p.uhid}</span> · {p.phone}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
