import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { listPatients } from '../lib/patients'

/**
 * Search-and-select a patient. `value` is the selected patient object (or null);
 * `onChange` receives the picked patient (or null to clear).
 * Not wrapped in a <label> by callers — it manages its own input.
 */
export default function PatientPicker({ value, onChange, placeholder }) {
  const { t } = useTranslation()
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

  if (value) {
    return (
      <div className="picker-selected">
        <span>
          {value.first_name} {value.last_name || ''} · <span className="mono">{value.uhid}</span>
        </span>
        <button type="button" className="btn-ghost sm" onClick={() => onChange(null)}>
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
        placeholder={placeholder}
        onFocus={() => results.length && setOpen(true)}
      />
      {open && results.length > 0 && (
        <ul className="picker-results">
          {results.map((p) => (
            <li
              key={p.id}
              onMouseDown={(e) => { e.preventDefault(); onChange(p); setOpen(false); setQ('') }}
            >
              {p.first_name} {p.last_name || ''} <span className="mono muted">{p.uhid}</span> · {p.phone}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
