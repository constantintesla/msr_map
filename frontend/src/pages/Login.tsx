import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { login } from '../api/client';
import { unlockNotificationAudio } from '../utils/notificationSound';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const redirectFrom = (location.state as { from?: string } | null)?.from;

  const afterLoginPath = (data: Awaited<ReturnType<typeof login>>) => {
    if (redirectFrom?.startsWith('/g/') || redirectFrom?.startsWith('/point/')) {
      return redirectFrom;
    }
    if (data.role === 'admin') return '/admin';
    if (data.role === 'commander') return data.faction_id ? '/tower-command' : '/command';
    if (data.point_id) return `/point/${data.point_id}`;
    if (data.role === 'engineer') return '/engineer';
    if (data.role === 'faction') return '/tower';
    return '/login';
  };

  const doLogin = async (u: string, p: string) => {
    setError('');
    unlockNotificationAudio();
    try {
      const data = await login(u, p);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user_id', String(data.user_id));
      localStorage.setItem('role', data.role);
      localStorage.setItem('side', data.side || '');
      localStorage.setItem('username', u);
      localStorage.setItem('faction_id', data.faction_id ? String(data.faction_id) : '');
      localStorage.setItem('faction_code', data.faction_code || '');
      localStorage.setItem('faction_name', data.faction_name || '');

      navigate(afterLoginPath(data), { replace: true });
    } catch {
      setError('Неверный логин или пароль');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await doLogin(username, password);
  };

  return (
    <div className="min-h-dvh flex flex-col p-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2 text-center">MSR Map</h1>
      <p className="text-center text-sm text-zinc-500 mb-6">Вход командования / инженера / админа</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          className="input"
          placeholder="Логин"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
        />
        <input
          className="input"
          type="password"
          placeholder="Пароль"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <p className="text-sideB text-sm">{error}</p>}
        <button type="submit" className="btn w-full bg-sideA text-white">
          Войти
        </button>
      </form>
    </div>
  );
}
