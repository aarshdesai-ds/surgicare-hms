import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { listAppointments, listDoctors, updateAppointmentStatus } from '../lib/appointments'

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// Which actions are offered for each status (next-step transitions).
const ACTIONS = {
  booked: [['checked_in', 'checkIn', 'primary'], ['cancelled', 'cancel', 'ghost'], ['no_show', 'noShow', 'ghost']],
  checked_in: [['in_progress', 'start', 'primary'], ['cancelled', 'cancel', 'ghost']],
  in_progress: [['completed', 'complete', 'primary']],
  completed: [],
  cancelled: [],
  no_show: [],
}

export default function Appointments() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [doctors, setDoctors] = useState([])
  const [day, setDay] = useState(todayISO())
  const [doctorId, setDoctorId] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    listDoctors().then(setDoctors).catch(() => {})
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await listAppointments(day, doctorId || undefined)
      setItems(res.items)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [day, doctorId])

  useEffect(() => { load() }, [load])

  async function changeStatus(id, status) {
    try {
      await updateAppointmentStatus(id, status)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  function bookHref() {
    const p = new URLSearchParams({ date: day })
    if (doctorId) p.set('doctor_id', doctorId)
    navigate(`/appointments/new?${p.toString()}`)
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('appointments.title')}</h1>
        <button className="btn-primary inline" onClick={bookHref}>
          + {t('appointments.book')}
        </button>
      </div>

      <div className="appt-controls">
        <label className="control">
          <span>{t('appointments.date')}</span>
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className="control">
          <span>{t('appointments.doctor')}</span>
          <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
            <option value="">{t('appointments.allDoctors')}</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>{d.full_name}</option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="alert error">{error}</div>}

      {loading ? (
        <p className="muted">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <div className="card empty-day">{t('appointments.none')}</div>
      ) : (
        <div className="agenda">
          {items.map((a) => (
            <div key={a.id} className={`appt-card status-${a.status}`}>
              <div className="appt-time">
                <strong>{fmtTime(a.scheduled_at)}</strong>
                <span className="muted">{a.duration_min}m</span>
              </div>
              <div className="appt-body">
                <div className="appt-patient">
                  {a.patient_name} <span className="mono muted">{a.patient_uhid}</span>
                </div>
                <div className="appt-meta muted">
                  {a.doctor_name}{a.reason ? ` · ${a.reason}` : ''}
                </div>
              </div>
              <div className="appt-side">
                <span className={`badge s-${a.status}`}>{t(`appointments.status.${a.status}`)}</span>
                <div className="appt-actions">
                  {(ACTIONS[a.status] || []).map(([next, key, kind]) => (
                    <button
                      key={next}
                      className={kind === 'primary' ? 'btn-primary inline sm' : 'btn-ghost sm'}
                      onClick={() => changeStatus(a.id, next)}
                    >
                      {t(`appointments.actions.${key}`)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
