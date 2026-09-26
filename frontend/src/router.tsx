import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AuthGuard, RoleGuard } from './auth/guards'
import Layout from './components/Layout'
import PublicLayout from './components/PublicLayout'
import Chat from './pages/Chat'
import ErrorPage from './pages/ErrorPage'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import RequesterHome from './pages/RequesterHome'
import VolunteerHome from './pages/VolunteerHome'

export const router = createBrowserRouter([
  {
    // Public pages render without the backend.
    element: <PublicLayout />,
    errorElement: <ErrorPage />,
    children: [
      { path: '/', element: <Landing /> },
      { path: '/login', element: <Login /> },
    ],
  },
  {
    element: (
      <AuthGuard>
        <Layout />
      </AuthGuard>
    ),
    errorElement: <ErrorPage />,
    children: [
      { path: '/onboarding', element: <Onboarding /> },
      { path: '/r', element: <RoleGuard role="requester"><RequesterHome /></RoleGuard> },
      { path: '/h', element: <RoleGuard role="helper"><VolunteerHome /></RoleGuard> },
      { path: '/chat/:requestId', element: <Chat /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
