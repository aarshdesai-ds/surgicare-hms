import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import PatientPicker from '../components/PatientPicker'
import ConsultationModal from '../components/ConsultationModal'
import { createPatient } from '../lib/patients'
import {
  listDoctors, listSessions, upsertSession,
  listQueue, addToQueue, updateQueueStatus,
} from '../lib/queue'

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const hhmm = (t) => (t ? t.slice(0, 5) : '')

// Available actions per status: [nextStatus, i18nKey, buttonKind]
const ACTIONS = {
  booked: [['waiting', 'checkIn', 'primary'], ['cancelled', 'cancel', 'ghost']],
  waiting: [['in_consultation', 'call', 'primary'], ['no_show', 'noShow', 'ghost'], ['cancelled', 'cancel', 'ghost']],
  in_consultation: [['completed', 'complete', 'primary']],
  completed: [],
  no_show: [],
}

// Unified status system: colour + icon + text (never colour alone).
const STATUS_META = {
  in_consultation: { icon: '▶', tone: 'active' },
  waiting: { icon: '⏳', tone: 'wait' },
  booked: { icon: '◷', tone: 'neutral' },
  completed: { icon: '✓', tone: 'ok' },
  no_show: { icon: '✕', tone: 'bad' },
}
// Sort order down the table: who's being seen, who's next, who's booked, then done.
const RANK = { in_consultation: 0, waiting: 1, booked: 2, completed: 3, no_show: 4 }
// Transitions that lose the patient from the active queue → confirm before doing.
const DESTRUCTIVE = new Set(['no_show', 'cancelled'])

// A waiting patient past this many minutes is flagged in the table.
const WAIT_ALERT_MIN = 30

function ageFromDob(dob) {
  if (!dob) return null
  const b = new Date(dob)
  if (Number.isNaN(b.getTime())) return null
  const now = new Date()
  let a = now.getFullYear() - b.getFullYear()
  const m = now.getMonth() - b.getMonth()
  if (m < 0 || (m === 0 && now.getDate() < b.getDate())) a--
  return a >= 0 ? a : null
}
function ageSex(dob, gender) {
  const a = ageFromDob(dob)
  const g = gender ? gender[0].toUpperCase() : ''
  if (a == null && !g) return '—'
  return [a != null ? a : '—', g || '—'].join(' / ')
}
function waitMinutes(checkedInAt) {
  if (!checkedInAt) return null
  const mins = Math.floor((Date.now() - new Date(checkedInAt).getTime()) / 60000)
  return mins >= 0 ? mins : null
}
function fmtTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function Queue() {
  const { t } = useTranslation()
  const [doctors, setDoctors] = useState([])
  const [doctorId, setDoctorId] = useState('')
  const [day, setDay] = useState(todayISO())
  const [session, setSession] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [consult, setConsult] = useState(null)

  useEffect(() => {
    listDoctors()
      .then((d) => {
        setDoctors(d)
        if (d.length) setDoctorId(String(d[0].id))
        else setLoading(false)
      })
      .catch((e) => { setError(e.message); setLoading(false) })
  }, [])

  const load = useCallback(async () => {
    if (!doctorId) { setLoading(false); return }
    setLoading(true)
    setError('')
    try {
      const [s, q] = await Promise.all([
        listSessions(day, doctorId),
        listQueue(day, doctorId),
      ])
      setSession(s.items[0] || null)
      setItems(q.items)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [day, doctorId])

  useEffect(() => { load() }, [load])

  async function setStatus(id, status) {
    try {
      await updateQueueStatus(id, status)
      load()
    } catch (e) { setError(e.message) }
  }

  const sorted = [...items].sort((a, b) => {
    const r = (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9)
    if (r) return r
    return (a.token_no ?? 9999) - (b.token_no ?? 9999)
  })

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('queue.title')}</h1>
      </div>

      <div className="appt-controls">
        <label className="control">
          <span>{t('queue.date')}</span>
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className="control">
          <span>{t('queue.doctor')}</span>
          <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
            {doctors.map((d) => {
              const covers = d.covers_for_doctor_id
                && doctors.find((x) => x.id === d.covers_for_doctor_id)
              return (
                <option key={d.id} value={d.id}>
                  {d.full_name}{covers ? ` (covers ${covers.full_name})` : ''}
                </option>
              )
            })}
          </select>
        </label>
      </div>

      <SessionBar
        session={session} doctorId={doctorId} day={day} t={t}
        onSaved={load} onError={setError}
      />

      <AddPanel doctorId={doctorId} day={day} t={t} onAdded={load} onError={setError} />

      {error && <div className="alert error">{error}</div>}

      {loading ? (
        <p className="muted">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <div className="card empty-day">{t('queue.empty')}</div>
      ) : (
        <div className="card table-card queue-table-card">
          <table className="data-table queue-table">
            <thead>
              <tr>
                <th>{t('queue.col.token')}</th>
                <th>{t('queue.col.name')}</th>
                <th>{t('queue.col.ageSex')}</th>
                <th>{t('queue.col.arrival')}</th>
                <th>{t('queue.col.wait')}</th>
                <th>{t('queue.col.doctor')}</th>
                <th>{t('queue.col.status')}</th>
                <th className="col-action">{t('queue.col.action')}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((e) => (
                <QueueRow key={e.id} e={e} t={t} onAction={setStatus}
                  onConsult={setConsult} selectedDoctorId={Number(doctorId)} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {consult && (
        <ConsultationModal
          patientId={consult.patient_id}
          patientLabel={`${consult.patient_name} · ${consult.patient_uhid}`}
          presetDoctorId={consult.doctor_id}
          queueEntryId={consult.id}
          onClose={() => setConsult(null)}
          onSaved={() => { setConsult(null); load() }}
          onComplete={() => updateQueueStatus(consult.id, 'completed')}
        />
      )}
    </div>
  )
}

function QueueRow({ e, t, onAction, onConsult, selectedDoctorId }) {
  const [confirm, setConfirm] = useState(null) // next status awaiting confirmation
  const covered = selectedDoctorId && e.doctor_id !== selectedDoctorId
  const meta = STATUS_META[e.status] || { icon: '•', tone: 'neutral' }
  const wait = e.status === 'waiting' ? waitMinutes(e.checked_in_at) : null
  const overdue = wait != null && wait >= WAIT_ALERT_MIN
  const arrival = e.checked_in_at ? fmtTime(e.checked_in_at) : null

  return (
    <tr className={`queue-tr status-${e.status}${overdue ? ' row-alert' : ''}`}>
      <td className={`q-token${e.token_no ? '' : ' empty'}`}>
        {e.token_no ? `#${e.token_no}` : '—'}
      </td>
      <td>
        <div className="q-name">{e.patient_name}</div>
        <div className="q-sub muted">
          <span className="mono">{e.patient_uhid}</span>
          {e.reason ? <span> · {e.reason}</span> : null}
        </div>
      </td>
      <td className="q-agesex">{ageSex(e.patient_dob, e.patient_gender)}</td>
      <td className="q-arrival">{arrival || <span className="muted">{t('queue.notArrived')}</span>}</td>
      <td className={`q-wait${overdue ? ' overdue' : ''}`}>
        {wait != null ? `${wait} ${t('dashboard.minShort')}` : '—'}
      </td>
      <td className="q-doctor">
        {covered ? <span className="q-cover">{e.doctor_name}</span> : e.doctor_name}
      </td>
      <td>
        <span className={`q-status tone-${meta.tone}`}>
          <span className="q-status-ico" aria-hidden="true">{meta.icon}</span>
          {t(`queue.status.${e.status}`)}
        </span>
      </td>
      <td className="col-action">
        {confirm ? (
          <div className="q-confirm">
            <span className="q-confirm-q">{t(`queue.confirm.${confirm}`)}</span>
            <button
              className="btn-primary inline sm danger"
              onClick={() => { onAction(e.id, confirm); setConfirm(null) }}
            >
              {t('queue.confirm.yes')}
            </button>
            <button className="btn-ghost sm" onClick={() => setConfirm(null)}>
              {t('queue.confirm.no')}
            </button>
          </div>
        ) : (
          <div className="q-actions">
            {(e.status === 'waiting' || e.status === 'in_consultation') && (
              <button className="btn-ghost sm" onClick={() => onConsult(e)}>
                {t('consult.consult')}
              </button>
            )}
            {(ACTIONS[e.status] || []).map(([next, key, kind]) => (
              <button
                key={next}
                className={kind === 'primary' ? 'btn-primary inline sm' : 'btn-ghost sm'}
                onClick={() =>
                  DESTRUCTIVE.has(next) ? setConfirm(next) : onAction(e.id, next)
                }
              >
                {t(`queue.actions.${key}`)}
              </button>
            ))}
          </div>
        )}
      </td>
    </tr>
  )
}

function SessionBar({ session, doctorId, day, t, onSaved, onError }) {
  const [editing, setEditing] = useState(false)
  const [start, setStart] = useState('10:00')
  const [end, setEnd] = useState('13:00')

  useEffect(() => {
    if (session) { setStart(hhmm(session.start_time)); setEnd(hhmm(session.end_time)) }
    setEditing(false)
  }, [session])

  async function save() {
    try {
      await upsertSession({
        doctor_id: Number(doctorId), session_date: day,
        start_time: start, end_time: end,
      })
      setEditing(false)
      onSaved()
    } catch (e) { onError(e.message) }
  }

  if (editing) {
    return (
      <div className="session-bar editing">
        <span className="session-label">{t('queue.opdHours')}</span>
        <input type="time" value={start} onChange={(e) => setStart(e.target.value)} />
        <span>–</span>
        <input type="time" value={end} onChange={(e) => setEnd(e.target.value)} />
        <button className="btn-primary inline sm" onClick={save}>{t('common.save')}</button>
        <button className="btn-ghost sm" onClick={() => setEditing(false)}>{t('common.cancel')}</button>
      </div>
    )
  }

  return (
    <div className="session-bar">
      <span className="session-label">{t('queue.opdHours')}</span>
      {session ? (
        <strong className="session-time">{hhmm(session.start_time)} – {hhmm(session.end_time)}</strong>
      ) : (
        <span className="muted">{t('queue.noSession')}</span>
      )}
      <button className="btn-ghost sm" onClick={() => setEditing(true)}>
        {session ? t('common.edit') : t('queue.setHours')}
      </button>
    </div>
  )
}

const EMPTY_NP = { first_name: '', last_name: '', phone: '', gender: '' }

function AddPanel({ doctorId, day, t, onAdded, onError }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('returning') // 'returning' | 'new'
  const [patient, setPatient] = useState(null)
  const [np, setNp] = useState(EMPTY_NP)
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  function reset() {
    setOpen(false); setMode('returning'); setPatient(null)
    setNp(EMPTY_NP); setReason(''); setNote('')
  }

  // Returns a patient id to queue, creating a new profile if in 'new' mode.
  async function resolvePatientId() {
    if (mode === 'returning') {
      if (!patient) { onError(t('queue.pickPatient')); return null }
      return patient.id
    }
    if (!np.first_name.trim() || !np.phone.trim()) {
      onError(t('queue.nameRequired')); return null
    }
    try {
      const created = await createPatient({
        first_name: np.first_name,
        last_name: np.last_name || undefined,
        phone: np.phone,
        gender: np.gender || undefined,
      })
      return created.id
    } catch (err) {
      // Phone already on file → switch to that existing patient, no duplicate.
      if (err.code === 'DUPLICATE_PATIENT' && err.fields?.duplicates?.length) {
        setMode('returning')
        setPatient(err.fields.duplicates[0])
        setNote(t('queue.existingFound'))
        return null
      }
      onError(err.message)
      return null
    }
  }

  async function add(checkIn) {
    setBusy(true); setNote('')
    try {
      const pid = await resolvePatientId()
      if (!pid) return
      await addToQueue({
        doctor_id: Number(doctorId), patient_id: pid,
        queue_date: day, reason: reason || undefined, check_in: checkIn,
      })
      reset(); onAdded()
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }

  if (!open) {
    return (
      <button className="btn-primary inline add-toggle" onClick={() => setOpen(true)}>
        + {t('queue.addPatient')}
      </button>
    )
  }

  return (
    <div className="card add-panel">
      {/* Step 1 — who is the patient */}
      <section className="add-section">
        <h4 className="add-step">{t('queue.sec.patient')}</h4>
        <div className="mode-toggle">
          <button className={mode === 'returning' ? 'active' : ''} onClick={() => setMode('returning')}>
            {t('queue.returning')}
          </button>
          <button className={mode === 'new' ? 'active' : ''} onClick={() => { setMode('new'); setNote('') }}>
            {t('queue.new')}
          </button>
        </div>

        {note && <div className="alert info">{note}</div>}

        {mode === 'returning' ? (
          <PatientPicker value={patient} onChange={setPatient} placeholder={t('queue.searchPatient')} />
        ) : (
          <div className="np-grid">
            <input placeholder={t('patients.firstName')} value={np.first_name}
              onChange={(e) => setNp({ ...np, first_name: e.target.value })} />
            <input placeholder={t('patients.lastName')} value={np.last_name}
              onChange={(e) => setNp({ ...np, last_name: e.target.value })} />
            <input placeholder={t('patients.phone')} value={np.phone}
              onChange={(e) => setNp({ ...np, phone: e.target.value })} />
            <select value={np.gender} onChange={(e) => setNp({ ...np, gender: e.target.value })}>
              <option value="">{t('patients.gender')}</option>
              <option value="M">{t('patients.male')}</option>
              <option value="F">{t('patients.female')}</option>
              <option value="O">{t('patients.other')}</option>
            </select>
          </div>
        )}
      </section>

      {/* Step 2 — why they're here */}
      <section className="add-section">
        <h4 className="add-step">{t('queue.sec.visit')}</h4>
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="reason-input"
          placeholder={t('queue.reason')}
        />
      </section>

      {/* Step 3 — put them in the queue */}
      <section className="add-section">
        <h4 className="add-step">{t('queue.sec.action')}</h4>
        <div className="add-actions">
          <button className="btn-ghost quiet" onClick={reset}>{t('common.cancel')}</button>
          <button className="btn-ghost" disabled={busy} onClick={() => add(false)}>
            {t('queue.preBook')}
          </button>
          <button className="btn-primary inline" disabled={busy} onClick={() => add(true)}>
            {t('queue.walkIn')}
          </button>
        </div>
      </section>
    </div>
  )
}
