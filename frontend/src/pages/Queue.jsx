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

  const groups = {
    in_consultation: items.filter((i) => i.status === 'in_consultation'),
    waiting: items.filter((i) => i.status === 'waiting'),
    booked: items.filter((i) => i.status === 'booked'),
    done: items.filter((i) => ['completed', 'no_show'].includes(i.status)),
  }

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
        <div className="queue-groups">
          {['in_consultation', 'waiting', 'booked', 'done'].map((g) =>
            groups[g].length === 0 ? null : (
              <section className="queue-group" key={g}>
                <h3>{t(`queue.groups.${g}`)} <span className="count">{groups[g].length}</span></h3>
                {groups[g].map((e) => (
                  <QueueRow key={e.id} e={e} t={t} onAction={setStatus}
                    onConsult={setConsult} selectedDoctorId={Number(doctorId)} />
                ))}
              </section>
            ),
          )}
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
  const covered = selectedDoctorId && e.doctor_id !== selectedDoctorId
  return (
    <div className={`queue-row status-${e.status}`}>
      <div className={`token-chip ${e.token_no ? '' : 'empty'}`}>
        {e.token_no ? `#${e.token_no}` : '—'}
      </div>
      <div className="appt-body">
        <div className="appt-patient">
          {e.patient_name} <span className="mono muted">{e.patient_uhid}</span>
          {covered && <span className="badge s-spec under-chip">{e.doctor_name}</span>}
        </div>
        <div className="appt-meta muted">
          {e.patient_phone}{e.reason ? ` · ${e.reason}` : ''}
        </div>
      </div>
      <div className="appt-side">
        <span className={`badge s-${e.status}`}>{t(`queue.status.${e.status}`)}</span>
        <div className="appt-actions">
          {(e.status === 'waiting' || e.status === 'in_consultation') && (
            <button className="btn-ghost sm" onClick={() => onConsult(e)}>
              {t('consult.consult')}
            </button>
          )}
          {(ACTIONS[e.status] || []).map(([next, key, kind]) => (
            <button
              key={next}
              className={kind === 'primary' ? 'btn-primary inline sm' : 'btn-ghost sm'}
              onClick={() => onAction(e.id, next)}
            >
              {t(`queue.actions.${key}`)}
            </button>
          ))}
        </div>
      </div>
    </div>
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
        <div className="add-row">
          <div className="add-field">
            <span className="field-label">{t('queue.patient')}</span>
            <PatientPicker value={patient} onChange={setPatient} placeholder={t('queue.searchPatient')} />
          </div>
          <div className="add-field">
            <span className="field-label">{t('queue.reason')}</span>
            <input value={reason} onChange={(e) => setReason(e.target.value)} className="reason-input" />
          </div>
        </div>
      ) : (
        <>
          <span className="field-label">{t('queue.newPatient')}</span>
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
          <div className="add-field np-reason">
            <span className="field-label">{t('queue.reason')}</span>
            <input value={reason} onChange={(e) => setReason(e.target.value)} className="reason-input" />
          </div>
        </>
      )}

      <div className="add-actions">
        <button className="btn-ghost" onClick={reset}>{t('common.cancel')}</button>
        <button className="btn-ghost" disabled={busy} onClick={() => add(false)}>
          {t('queue.preBook')}
        </button>
        <button className="btn-primary inline" disabled={busy} onClick={() => add(true)}>
          {t('queue.walkIn')}
        </button>
      </div>
    </div>
  )
}
