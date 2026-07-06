import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { login } from '../api/client';
import { unlockNotificationAudio } from '../utils/notificationSound';

const DEMO_ACCOUNTS = [
  { login: 'admin', pass: 'admin', label: 'Администратор' },
  { login: 'cmd_a', pass: 'alfa', label: 'Сторона А · командование ЛК' },
  { login: 'cmd_b', pass: 'bravo', label: 'Сторона Б · командование СБГ' },
  { login: 'eng_a1', pass: 'alfa01', label: 'Сторона А · инженер 1 (тест)' },
  { login: 'eng_b1', pass: 'bravo1', label: 'Сторона Б · инженер 1 (тест)' },
];

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [showAccounts, setShowAccounts] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const redirectFrom = (location.state as { from?: string } | null)?.from;

  const afterLoginPath = (data: Awaited<ReturnType<typeof login>>) => {
    if (redirectFrom?.startsWith('/g/') || redirectFrom?.startsWith('/point/')) {
      return redirectFrom;
    }
    if (data.role === 'admin') return '/admin';
    if (data.role === 'commander') return '/command';
    if (data.point_id) return `/point/${data.point_id}`;
    if (data.role === 'engineer') return '/engineer';
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

      navigate(afterLoginPath(data), { replace: true });
    } catch {
      setError('Неверный логин или пароль');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await doLogin(username, password);
  };

  const fillAccount = (loginName: string, pass: string) => {
    setUsername(loginName);
    setPassword(pass);
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

      <button
        type="button"
        className="mt-4 text-sm text-zinc-500 underline"
        onClick={() => setShowAccounts(!showAccounts)}
      >
        {showAccounts ? 'Скрыть' : 'Показать'} тестовые учётки
      </button>

      {showAccounts && (
        <div className="mt-3 space-y-2 text-sm border border-zinc-800 rounded-lg p-3">
          <p className="text-zinc-400 mb-2">
            Командиры: <span className="text-sideA">cmd_a</span> / <span className="text-sideB">cmd_b</span> — пароли{' '}
            <code className="text-text">alfa</code> / <code className="text-text">bravo</code>
          </p>
          <p className="text-xs text-zinc-500 mb-2">
            Инженеры 2…N — индивидуальные пароли (6 символов), список в настройках штаба.{' '}
            <span className="text-zinc-400">eng_a1 / eng_b1 — тестовые: alfa01 / bravo1</span>
          </p>
          {DEMO_ACCOUNTS.map((a) => (
            <button
              key={a.login}
              type="button"
              className="w-full text-left py-2 px-3 rounded bg-zinc-900 border border-zinc-800 active:bg-zinc-800"
              onClick={() => fillAccount(a.login, a.pass)}
            >
              <span className="font-mono text-sideA">{a.login}</span>
              <span className="text-zinc-500 mx-2">/</span>
              <span className="font-mono">{a.pass}</span>
              <span className="block text-xs text-zinc-500 mt-0.5">{a.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
