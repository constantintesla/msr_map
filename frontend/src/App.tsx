import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import LoginPage from './pages/Login';
import CommanderPage from './pages/Commander';
import PointPage from './pages/Point';
import AdminPage from './pages/Admin';
import EngineerPage from './pages/Engineer';
import QrEntryPage from './pages/QrEntry';
import NotificationPings from './hooks/useNotificationPings';
import { EngineerOrdersProvider } from './context/EngineerOrdersContext';
import { homePathForRole } from './utils/auth';

function RequireAuth({ children, role }: { children: React.ReactNode; role?: string }) {
  const location = useLocation();
  const token = localStorage.getItem('token');
  const userRole = localStorage.getItem('role');
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (role && userRole !== role) {
    return <Navigate to={homePathForRole(userRole)} replace />;
  }
  return <>{children}</>;
}

function HomeRedirect() {
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role');
  if (!token) return <Navigate to="/login" replace />;
  return <Navigate to={homePathForRole(role)} replace />;
}

export default function App() {
  return (
    <HashRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <NotificationPings />
      <EngineerOrdersProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/g/:token"
            element={
              <RequireAuth role="engineer">
                <QrEntryPage />
              </RequireAuth>
            }
          />
          <Route
            path="/command"
            element={
              <RequireAuth role="commander">
                <CommanderPage />
              </RequireAuth>
            }
          />
          <Route
            path="/point/:id"
            element={
              <RequireAuth role="engineer">
                <PointPage />
              </RequireAuth>
            }
          />
          <Route path="/cache/:id" element={<Navigate to="/engineer" replace />} />
          <Route
            path="/engineer"
            element={
              <RequireAuth role="engineer">
                <EngineerPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin"
            element={
              <RequireAuth role="admin">
                <AdminPage />
              </RequireAuth>
            }
          />
          <Route path="/status" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<HomeRedirect />} />
        </Routes>
      </EngineerOrdersProvider>
    </HashRouter>
  );
}
