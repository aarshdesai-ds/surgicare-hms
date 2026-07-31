import { Routes, Route, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Patients from './pages/Patients'
import PatientForm from './pages/PatientForm'
import PatientProfile from './pages/PatientProfile'
import Queue from './pages/Queue'
import OT from './pages/OT'
import Reports from './pages/Reports'
import Staff from './pages/Staff'
import Billing from './pages/Billing'
import InvoiceDetail from './pages/InvoiceDetail'
import ServiceCatalog from './pages/ServiceCatalog'
import Beds from './pages/Beds'
import Pharmacy from './pages/Pharmacy'

export default function App() {
  const { loading } = useAuth()
  const { t } = useTranslation()

  if (loading) {
    return <div className="full-center">{t('common.loading')}</div>
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/patients" element={<Patients />} />
        <Route path="/patients/new" element={<PatientForm />} />
        <Route path="/patients/:id" element={<PatientProfile />} />
        <Route path="/patients/:id/edit" element={<PatientForm />} />
        <Route path="/queue" element={<Queue />} />
        <Route path="/ot" element={<OT />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/staff" element={<Staff />} />
        <Route path="/billing" element={<Billing />} />
        <Route path="/billing/services" element={<ServiceCatalog />} />
        <Route path="/billing/:id" element={<InvoiceDetail />} />
        <Route path="/beds" element={<Beds />} />
        <Route path="/pharmacy" element={<Pharmacy />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
