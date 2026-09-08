import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchTowerJoinInfo, registerTowerAccount } from '../api/client';

export default function RegisterTowerPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [factionName, setFactionName] = useState('');
  const [callsign, setCallsign] = useState('');
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetchTowerJoinInfo(token)
      .then((info) => setFactionName(info.faction_name))
      .catch((e) => setLoadError(e instanceof Error ? e.message : 'Ссылка недействительна'));
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError('');
    if (!/^\d{4}$/.test(pin)) {
      setError('PIN — ровно 4 цифры');
      return;
    }
    if (callsign.trim().length < 2) {
      setError('Позывной — минимум 2 символа');
      return;
    }
    setSubmitting(true);
    try {
      const data = await registerTowerAccount(token, callsign.trim(), pin);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user_id', String(data.user_id));
      localStorage.setItem('role', data.role);
      localStorage.setItem('side', data.side || '');
      localStorage.setItem('username', callsign.trim());
      localStorage.setItem('faction_id', data.faction_id ? String(data.faction_id) : '');
      localStorage.setItem('faction_code', data.faction_code || '');
      localStorage.setItem('faction_name', data.faction_name || '');
      navigate('/tower', { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось зарегистрироваться');
    } finally {
      setSubmitting(false);
    }
  };

  if (loadError) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center p-6 text-center gap-3">
        <p className="text-sideB">{loadError}</p>
      </div>
    );
  }

  return (
    <div className="min-h-dvh flex flex-col p-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2 text-center">Башня</h1>
      <p className="text-center text-sm text-zinc-500 mb-6">
        {factionName ? `Регистрация — ${factionName}` : 'Загрузка…'}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          className="input"
          placeholder="Позывной"
          value={callsign}
          onChange={(e) => setCallsign(e.target.value)}
          autoComplete="username"
          maxLength={24}
        />
        <input
          className="input"
          type="tel"
          inputMode="numeric"
          pattern="\d{4}"
          placeholder="PIN (4 цифры)"
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
          autoComplete="new-password"
        />
        {error && <p className="text-sideB text-sm">{error}</p>}
        <button type="submit" className="btn w-full bg-sideA text-white" disabled={submitting || !factionName}>
          {submitting ? '…' : 'Зарегистрироваться и войти'}
        </button>
      </form>

      <p className="text-xs text-zinc-500 mt-4 text-center">
        Уже зарегистрированы? <a href="#/login" className="underline">Войти</a>
      </p>
    </div>
  );
}
