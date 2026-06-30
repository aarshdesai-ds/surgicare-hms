import { NavLink, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'
import LanguageToggle from './LanguageToggle'

// Sidebar items. Only Dashboard is live in the MVP shell; the rest are
// placeholders that arrive in their roadmap weeks (patients, appts, etc.).
const NAV = [
  { to: '/', key: 'nav.dashboard', icon: '▣', end: true },
  { to: '/patients', key: 'nav.patients', icon: '👤' },
  { to: '/queue', key: 'nav.queue', icon: '📋' },
  { to: '/billing', key: 'nav.billing', icon: '🧾', disabled: true },
  { to: '/beds', key: 'nav.beds', icon: '🛏', disabled: true },
  { to: '/ot', key: 'nav.ot', icon: '⚕' },
]

export default function Layout() {
  const { t } = useTranslation()
  const { user, signOut } = useAuth()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">✚</span>
          <div>
            <div className="brand-title">{t('app.title')}</div>
            <div className="brand-sub">{t('app.subtitle')}</div>
          </div>
        </div>

        <nav className="nav">
          {NAV.map((item) =>
            item.disabled ? (
              <span key={item.to} className="nav-item disabled" title={t('common.comingSoon')}>
                <span className="nav-icon">{item.icon}</span>
                {t(item.key)}
                <span className="soon">{t('common.comingSoon')}</span>
              </span>
            ) : (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <span className="nav-icon">{item.icon}</span>
                {t(item.key)}
              </NavLink>
            ),
          )}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <LanguageToggle />
          <div className="topbar-right">
            <span className="user-email">{user?.email}</span>
            <button className="btn-ghost" onClick={() => signOut()}>
              {t('common.signOut')}
            </button>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
