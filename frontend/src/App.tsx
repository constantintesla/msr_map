import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import LoginPage from './pages/Login';
import CommanderPage from './pages/Commander';
import PointPage from './pages/Point';
import AdminPage from './pages/Admin';
import EngineerPage from './pages/Engineer';
import QrEntryPage from './pages/QrEntry';
import RegisterTowerPage from './pages/RegisterTower';
import TowerHomePage from './pages/TowerHome';
import TowerCommanderPage from './pages/TowerCommander';
import NotificationPings from './hooks/useNotificationPings';
import { EngineerOrdersProvider } from './context/EngineerOrdersContext';
import { homePathForRole } from './utils/auth';

function RequireAuth({ children, role }: { children: React.ReactNode; role?: string | string[] }) {
  const location = useLocation();
  const token = localStorage.getItem('token');
  const userRole = localStorage.getItem('role');
  const factionId = localStorage.getItem('faction_id');
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  const allowed = Array.isArray(role) ? role : role ? [role] : null;
  if (allowed && !(userRole && allowed.includes(userRole))) {
    return <Navigate to={homePathForRole(userRole, factionId)} replace />;
  }
  return <>{children}</>;
}

function HomeRedirect() {
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role');
  const factionId = localStorage.getItem('faction_id');
  if (!token) return <Navigate to="/login" replace />;
  return <Navigate to={homePathForRole(role, factionId)} replace />;
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
          <Route path="/join/:token" element={<RegisterTowerPage />} />
          <Route
            path="/g/:token"
            element={
              <RequireAuth role={['engineer', 'faction', 'commander']}>
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
            path="/tower-command"
            element={
              <RequireAuth role="commander">
                <TowerCommanderPage />
              </RequireAuth>
            }
          />
          <Route
            path="/tower"
            element={
              <RequireAuth role="faction">
                <TowerHomePage />
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
          <Route path="/status" element={<HomeRedirect />} />
          <Route path="*" element={<HomeRedirect />} />
        </Routes>
      </EngineerOrdersProvider>
    </HashRouter>
  );
}
