import { createBrowserRouter } from 'react-router-dom'
import { AuthGuard, HomeRedirect, RoleGuard } from './auth/guards'
import Layout from './components/Layout'
import Chat from './pages/Chat'
import ErrorPage from './pages/ErrorPage'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import RequesterHome from './pages/RequesterHome'
import VolunteerHome from './pages/VolunteerHome'

export const router = createBrowserRouter([
  { path: '/login', element: <Login />, errorElement: <ErrorPage /> },
  {
    element: (
      <AuthGuard>
        <Layout />
      </AuthGuard>
    ),
    errorElement: <ErrorPage />,
    children: [
      { path: '/', element: <HomeRedirect /> },
      { path: '/onboarding', element: <Onboarding /> },
      { path: '/r', element: <RoleGuard role="requester"><RequesterHome /></RoleGuard> },
      { path: '/h', element: <RoleGuard role="helper"><VolunteerHome /></RoleGuard> },
      { path: '/chat/:requestId', element: <Chat /> },
      { path: '*', element: <HomeRedirect /> },
    ],
  },
])
