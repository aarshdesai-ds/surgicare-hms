import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'
import LanguageToggle from '../components/LanguageToggle'

export default function Login() {
  const { t } = useTranslation()
  const { signIn } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    const { error: signInError } = await signIn(email, password)
    setSubmitting(false)
    if (signInError) {
      // Show Supabase's actual message so failures are diagnosable.
      setError(signInError.message || t('login.error'))
      return
    }
    navigate('/', { replace: true })
  }

  return (
    <div className="auth-page">
      <div className="auth-toggle">
        <LanguageToggle />
      </div>

      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-brand">
          <span className="brand-mark big">✚</span>
          <h1>{t('app.title')}</h1>
          <p className="muted">{t('login.intro')}</p>
        </div>

        <label className="field">
          <span>{t('login.email')}</span>
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label className="field">
          <span>{t('login.password')}</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error && <div className="alert error">{error}</div>}

        <button className="btn-primary" type="submit" disabled={submitting}>
          {submitting ? t('login.submitting') : t('login.submit')}
        </button>
      </form>
    </div>
  )
}
