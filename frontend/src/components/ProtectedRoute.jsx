// src/components/ProtectedRoute.jsx
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, initializing } = useAuth()
  if (initializing) return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm text-slate-500">Restoring session…</div>
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}
