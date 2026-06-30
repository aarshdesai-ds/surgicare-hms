import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

/** Redirects to /login when there is no active session. */
export default function ProtectedRoute({ children }) {
  const { session } = useAuth()
  if (!session) return <Navigate to="/login" replace />
  return children
}
