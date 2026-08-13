import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { apiGet } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [role, setRole] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession)
    })
    return () => sub.subscription.unsubscribe()
  }, [])

  // Fetch the current user's role from the backend whenever the session changes.
  useEffect(() => {
    if (!session) { setRole(null); return }
    let active = true
    apiGet('/api/me')
      .then((m) => { if (active) setRole(m.role) })
      .catch(() => { if (active) setRole(null) })
    return () => { active = false }
  }, [session])

  const value = {
    session,
    user: session?.user ?? null,
    role,
    loading,
    signIn: (email, password) =>
      supabase.auth.signInWithPassword({ email, password }),
    resetPassword: (email) =>
      supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      }),
    signOut: () => supabase.auth.signOut(),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
