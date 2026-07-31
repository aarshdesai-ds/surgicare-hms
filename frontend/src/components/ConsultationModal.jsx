import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createEncounter } from '../lib/encounters'
import { createPrescription } from '../lib/prescriptions'

const emptyMed = () => ({ drug_name: '', strength: '', frequency: '', duration: '', quantity: '', instructions: '' })

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
  const [meds, setMeds] = useState([emptyMed()])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const setMed = (i, k, val) => setMeds((m) => m.map((row, j) => (j === i ? { ...row, [k]: val } : row)))
  const addMed = () => setMeds((m) => [...m, emptyMed()])
  const removeMed = (i) => setMeds((m) => (m.length > 1 ? m.filter((_, j) => j !== i) : m))

  async function save(complete) {
    const vitals = Object.fromEntries(
      Object.entries(v).filter(([, val]) => val.trim()),
    )
    const filledMeds = meds.filter((m) => m.drug_name.trim())
    const hasEncounter =
      complaints.trim() || diagnosis.trim() || notes.trim() || Object.keys(vitals).length > 0
    if (!hasEncounter && filledMeds.length === 0) {
      setError(t('consult.needSomething')); return
    }
    setBusy(true); setError('')
    try {
      let encounterId
      if (hasEncounter) {
        const enc = await createEncounter({
          patient_id: patientId,
          doctor_id: doctorId ? Number(doctorId) : undefined,
          queue_entry_id: queueEntryId,
          vitals: Object.keys(vitals).length ? vitals : undefined,
          complaints: complaints || undefined,
          diagnosis: diagnosis || undefined,
          notes: notes || undefined,
        })
        encounterId = enc.id
      }
      if (filledMeds.length) {
        await createPrescription({
          patient_id: patientId,
          doctor_id: doctorId ? Number(doctorId) : undefined,
          encounter_id: encounterId,
          items: filledMeds.map((m) => ({
            drug_name: m.drug_name,
            strength: m.strength || undefined,
            frequency: m.frequency || undefined,
            duration: m.duration || undefined,
            quantity: m.quantity || undefined,
            instructions: m.instructions || undefined,
          })),
        })
      }
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

          <div className="rx-section">
            <span className="field-label">{t('consult.medicines')}</span>
            {meds.map((m, i) => (
              <div className="rx-row" key={i}>
                <input placeholder={t('consult.drug')} value={m.drug_name} onChange={(e) => setMed(i, 'drug_name', e.target.value)} />
                <input placeholder={t('consult.strength')} value={m.strength} onChange={(e) => setMed(i, 'strength', e.target.value)} />
                <input placeholder={t('consult.frequency')} value={m.frequency} onChange={(e) => setMed(i, 'frequency', e.target.value)} />
                <input placeholder={t('consult.duration')} value={m.duration} onChange={(e) => setMed(i, 'duration', e.target.value)} />
                <input placeholder={t('consult.qty')} value={m.quantity} onChange={(e) => setMed(i, 'quantity', e.target.value)} />
                <input placeholder={t('consult.instructions')} value={m.instructions} onChange={(e) => setMed(i, 'instructions', e.target.value)} />
                <button type="button" className="link-danger" onClick={() => removeMed(i)}>×</button>
              </div>
            ))}
            <button type="button" className="btn-ghost sm" onClick={addMed}>{t('consult.addMedicine')}</button>
          </div>

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
