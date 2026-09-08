import { useNavigate } from 'react-router-dom';

export function logout(navigate: ReturnType<typeof useNavigate>) {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('side');
  localStorage.removeItem('username');
  localStorage.removeItem('faction_id');
  localStorage.removeItem('faction_code');
  localStorage.removeItem('faction_name');
  navigate('/login');
}

export function homePathForRole(role: string | null, factionId?: string | null): string {
  if (role === 'admin') return '/admin';
  if (role === 'commander') return factionId ? '/tower-command' : '/command';
  if (role === 'engineer') return '/engineer';
  if (role === 'faction') return '/tower';
  return '/login';
}
