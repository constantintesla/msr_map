import { useNavigate } from 'react-router-dom';

export function logout(navigate: ReturnType<typeof useNavigate>) {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('side');
  localStorage.removeItem('username');
  navigate('/login');
}

export function homePathForRole(role: string | null): string {
  if (role === 'admin') return '/admin';
  if (role === 'commander') return '/command';
  if (role === 'engineer') return '/engineer';
  return '/login';
}
