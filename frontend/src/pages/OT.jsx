import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import PatientPicker from '../components/PatientPicker'
import { listDoctors } from '../lib/queue'
import { listTheatres, listCases, addCase, updateCaseStatus, moveCase } from '../lib/ot'

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Procedure suggestions depend on the selected surgeon's specialty (free-text,
// so anything can still be typed). Common minor procedures apply to both.
const PROCEDURES_BY_SPECIALTY = {
  orthopedics: [
    'Closed reduction', 'ORIF (fracture fixation)', 'K-wire fixation',
    'POP / plaster application', 'Arthroscopy', 'Implant removal', 'Debridement',
  ],
  obgyn: [
    'Normal delivery', 'Cesarean section (LSCS)', 'D&C', 'Hysterectomy',
    'Tubal ligation', 'Ovarian cystectomy', 'Cervical encerclage',
  ],
}
const COMMON_PROCEDURES = ['Incision & drainage', 'Suturing', 'Biopsy']

const ACTIONS = {
  scheduled: [['in_progress', 'start', 'primary'], ['cancelled', 'cancel', 'ghost']],
  in_progress: [['completed', 'complete', 'primary']],
  completed: [],
  cancelled: [],
}

export default function OT() {
  const { t } = useTranslation()
  const [theatres, setTheatres] = useState([])
  const [doctors, setDoctors] = useState([])
  const [theatreId, setTheatreId] = useState('')
  const [surgeonId, setSurgeonId] = useState('')
  const [day, setDay] = useState(todayISO())
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    listTheatres()
      .then((th) => {
        setTheatres(th)
        if (th.length) setTheatreId(String(th[0].id))
        else setLoading(false)
      })
      .catch((e) => { setError(e.message); setLoading(false) })
    listDoctors().then(setDoctors).catch(() => {})
  }, [])

  const load = useCallback(async () => {
    if (!theatreId) { setLoading(false); return }
    setLoading(true); setError('')
    try {
      const res = await listCases(day, theatreId, surgeonId || undefined)
      setItems(res.items)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [day, theatreId, surgeonId])

  useEffect(() => { load() }, [load])

  async function act(fn) {
    try { await fn(); load() } catch (e) { setError(e.message) }
  }

  const currentTheatre = theatres.find((x) => String(x.id) === theatreId)

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('ot.title')}</h1>
      </div>

      <div className="appt-controls">
        <label className="control">
          <span>{t('ot.date')}</span>
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className="control">
          <span>{t('ot.theatre')}</span>
          <select value={theatreId} onChange={(e) => setTheatreId(e.target.value)}>
            {theatres.map((th) => (
              <option key={th.id} value={th.id}>{th.name}</option>
            ))}
          </select>
          {currentTheatre?.obgyn_only && (
            <small className="control-hint">{t('ot.obgynOnly')}</small>
          )}
        </label>
        <label className="control">
          <span>{t('ot.surgeon')}</span>
          <select value={surgeonId} onChange={(e) => setSurgeonId(e.target.value)}>
            <option value="">{t('ot.allSurgeons')}</option>
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

      <AddCase theatreId={theatreId} day={day} t={t} doctors={doctors}
        obgynOnly={currentTheatre?.obgyn_only} onAdded={load} onError={setError} />

      {error && <div className="alert error">{error}</div>}

      {loading ? (
        <p className="muted">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <div className="card empty-day">{t('ot.empty')}</div>
      ) : (
        <div className="ot-list">
          {items.map((c, idx) => (
            <div key={c.id} className={`ot-case status-${c.status}`}>
              <div className="case-num">{idx + 1}</div>
              <div className="appt-body">
                <div className="appt-patient">
                  {c.procedure} <span className="badge s-spec">{c.surgeon_name}</span>
                </div>
                <div className="appt-meta muted">
                  {c.patient_name} <span className="mono">{c.patient_uhid}</span>
                  {c.notes ? ` · ${c.notes}` : ''}
                </div>
              </div>
              <div className="appt-side">
                <span className={`badge s-${c.status}`}>{t(`ot.status.${c.status}`)}</span>
                <div className="appt-actions">
                  {(c.status === 'scheduled' || c.status === 'in_progress') && (
                    <div className="ot-move">
                      <button className="btn-ghost sm icon" title={t('ot.actions.up')}
                        disabled={idx === 0} onClick={() => act(() => moveCase(c.id, 'up'))}>▲</button>
                      <button className="btn-ghost sm icon" title={t('ot.actions.down')}
                        disabled={idx === items.length - 1} onClick={() => act(() => moveCase(c.id, 'down'))}>▼</button>
                    </div>
                  )}
                  {(ACTIONS[c.status] || []).map(([next, key, kind]) => (
                    <button key={next}
                      className={kind === 'primary' ? 'btn-primary inline sm' : 'btn-ghost sm'}
                      onClick={() => act(() => updateCaseStatus(c.id, next))}>
                      {t(`ot.actions.${key}`)}
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

function AddCase({ theatreId, day, t, doctors, obgynOnly, onAdded, onError }) {
  const [open, setOpen] = useState(false)
  const [patient, setPatient] = useState(null)
  const [surgeonId, setSurgeonId] = useState('')
  const [procedure, setProcedure] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)

  // Labor Room only allows OB-GYN surgeons.
  const eligible = obgynOnly ? doctors.filter((d) => d.specialty === 'obgyn') : doctors

  // Procedure suggestions follow the selected surgeon's specialty.
  const surgeon = doctors.find((d) => String(d.id) === surgeonId)
  const procedures = [
    ...(PROCEDURES_BY_SPECIALTY[surgeon?.specialty] || []),
    ...COMMON_PROCEDURES,
  ]

  useEffect(() => {
    // Default/reset the surgeon to an eligible one for this theatre.
    if (eligible.length && !eligible.some((d) => String(d.id) === surgeonId)) {
      setSurgeonId(String(eligible[0].id))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eligible, surgeonId])

  function reset() {
    setOpen(false); setPatient(null); setProcedure(''); setNotes('')
  }

  async function submit() {
    if (!patient || !procedure.trim()) { onError(t('ot.caseRequired')); return }
    setBusy(true)
    try {
      await addCase({
        theatre_id: Number(theatreId), case_date: day, patient_id: patient.id,
        surgeon_id: Number(surgeonId), procedure, notes: notes || undefined,
      })
      reset(); onAdded()
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }

  if (!open) {
    return (
      <button className="btn-primary inline add-toggle" onClick={() => setOpen(true)}>
        + {t('ot.addCase')}
      </button>
    )
  }

  return (
    <div className="card add-panel">
      <datalist id="ot-procedures">
        {procedures.map((p) => <option key={p} value={p} />)}
      </datalist>
      <div className="ot-add-grid">
        <div className="add-field">
          <span className="field-label">{t('ot.patient')}</span>
          <PatientPicker value={patient} onChange={setPatient} placeholder={t('queue.searchPatient')} />
        </div>
        <div className="add-field">
          <span className="field-label">{t('ot.surgeon')}</span>
          <select value={surgeonId} onChange={(e) => setSurgeonId(e.target.value)}>
            {eligible.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
          </select>
        </div>
        <div className="add-field">
          <span className="field-label">{t('ot.procedure')}</span>
          <input list="ot-procedures" value={procedure} className="reason-input"
            placeholder={t('ot.procedurePlaceholder')}
            onChange={(e) => setProcedure(e.target.value)} />
        </div>
        <div className="add-field">
          <span className="field-label">{t('ot.notes')}</span>
          <input value={notes} className="reason-input" onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
      <div className="add-actions">
        <button className="btn-ghost" onClick={reset}>{t('common.cancel')}</button>
        <button className="btn-primary inline" disabled={busy} onClick={submit}>
          {t('ot.addCase')}
        </button>
      </div>
    </div>
  )
}
