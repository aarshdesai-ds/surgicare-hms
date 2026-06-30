import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createEncounter } from '../lib/encounters'

/**
 * Record a consultation/visit note for a patient.
 * - patientId / patientLabel: who the note is for.
 * - doctors + presetDoctorId: doctor select (preset hides the dropdown).
 * - queueEntryId: links the note to an OPD queue visit (optional).
 * - onComplete: if provided, shows "Save & complete" which also runs it
 *   (e.g. mark the queue entry completed).
 */
export default function ConsultationModal({
  patientId, patientLabel, doctors = [], presetDoctorId,
  queueEntryId, onClose, onSaved, onComplete,
}) {
  const { t } = useTranslation()
  const [doctorId, setDoctorId] = useState(
    presetDoctorId ? String(presetDoctorId) : (doctors[0] ? String(doctors[0].id) : ''),
  )
  const [v, setV] = useState({ bp: '', pulse: '', temp: '', spo2: '', weight: '' })
  const [complaints, setComplaints] = useState('')
  const [diagnosis, setDiagnosis] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function save(complete) {
    const vitals = Object.fromEntries(
      Object.entries(v).filter(([, val]) => val.trim()),
    )
    if (!complaints.trim() && !diagnosis.trim() && !notes.trim() && Object.keys(vitals).length === 0) {
      setError(t('consult.needSomething')); return
    }
    setBusy(true); setError('')
    try {
      await createEncounter({
        patient_id: patientId,
        doctor_id: doctorId ? Number(doctorId) : undefined,
        queue_entry_id: queueEntryId,
        vitals: Object.keys(vitals).length ? vitals : undefined,
        complaints: complaints || undefined,
        diagnosis: diagnosis || undefined,
        notes: notes || undefined,
      })
      if (complete && onComplete) await onComplete()
      onSaved()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{t('consult.title')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="consult-patient">{patientLabel}</div>

          {!presetDoctorId && doctors.length > 0 && (
            <label className="field">
              <span>{t('consult.doctor')}</span>
              <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
                <option value="">—</option>
                {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
              </select>
            </label>
          )}

          <span className="field-label">{t('consult.vitals')}</span>
          <div className="vitals-grid">
            <VInput label={t('consult.bp')} value={v.bp} placeholder="120/80" onChange={(x) => setV({ ...v, bp: x })} />
            <VInput label={t('consult.pulse')} value={v.pulse} placeholder="/min" onChange={(x) => setV({ ...v, pulse: x })} />
            <VInput label={t('consult.temp')} value={v.temp} placeholder="°F" onChange={(x) => setV({ ...v, temp: x })} />
            <VInput label={t('consult.spo2')} value={v.spo2} placeholder="%" onChange={(x) => setV({ ...v, spo2: x })} />
            <VInput label={t('consult.weight')} value={v.weight} placeholder="kg" onChange={(x) => setV({ ...v, weight: x })} />
          </div>

          <label className="field">
            <span>{t('consult.complaints')}</span>
            <textarea rows={2} value={complaints} onChange={(e) => setComplaints(e.target.value)} />
          </label>
          <label className="field">
            <span>{t('consult.diagnosis')}</span>
            <textarea rows={2} value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} />
          </label>
          <label className="field">
            <span>{t('consult.notes')}</span>
            <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>

          {error && <div className="alert error">{error}</div>}
        </div>

        <div className="modal-foot">
          <button className="btn-ghost" onClick={onClose}>{t('common.cancel')}</button>
          {onComplete && (
            <button className="btn-ghost" disabled={busy} onClick={() => save(true)}>
              {t('consult.saveComplete')}
            </button>
          )}
          <button className="btn-primary inline" disabled={busy} onClick={() => save(false)}>
            {busy ? t('common.saving') : t('consult.save')}
          </button>
        </div>
      </div>
    </div>
  )
}

function VInput({ label, value, placeholder, onChange }) {
  return (
    <label className="vital">
      <span>{label}</span>
      <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}
