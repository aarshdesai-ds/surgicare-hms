import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { listPatients } from '../lib/patients'

const PAGE_SIZE = 20

export default function Patients() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [q, setQ] = useState('')
  const [data, setData] = useState({ items: [], total: 0 })
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async (query, off) => {
    setLoading(true)
    setError('')
    try {
      const res = await listPatients({ q: query, limit: PAGE_SIZE, offset: off })
      setData(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Debounce the search input.
  useEffect(() => {
    const id = setTimeout(() => {
      setOffset(0)
      load(q, 0)
    }, 300)
    return () => clearTimeout(id)
  }, [q, load])

  function changePage(newOffset) {
    setOffset(newOffset)
    load(q, newOffset)
  }

  const start = data.total === 0 ? 0 : offset + 1
  const end = Math.min(offset + PAGE_SIZE, data.total)

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{t('patients.title')}</h1>
        <button className="btn-primary inline" onClick={() => navigate('/patients/new')}>
          + {t('patients.new')}
        </button>
      </div>

      <input
        className="search-input"
        placeholder={t('patients.searchPlaceholder')}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoFocus
      />

      {error && <div className="alert error">{error}</div>}

      <div className="card table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t('patients.uhid')}</th>
              <th>{t('patients.name')}</th>
              <th>{t('patients.phone')}</th>
              <th>{t('patients.gender')}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="table-empty">{t('common.loading')}</td></tr>
            ) : data.items.length === 0 ? (
              <tr><td colSpan={4} className="table-empty">{t('patients.none')}</td></tr>
            ) : (
              data.items.map((p) => (
                <tr key={p.id} className="row-link" onClick={() => navigate(`/patients/${p.id}`)}>
                  <td className="mono">{p.uhid}</td>
                  <td>{p.first_name} {p.last_name || ''}</td>
                  <td>{p.phone}</td>
                  <td>{p.gender || '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {data.total > PAGE_SIZE && (
        <div className="pagination">
          <button className="btn-ghost" disabled={offset === 0} onClick={() => changePage(offset - PAGE_SIZE)}>
            ‹ {t('common.prev')}
          </button>
          <span className="muted">{start}–{end} {t('common.of')} {data.total}</span>
          <button className="btn-ghost" disabled={end >= data.total} onClick={() => changePage(offset + PAGE_SIZE)}>
            {t('common.next')} ›
          </button>
        </div>
      )}
    </div>
  )
}
