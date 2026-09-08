import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { resolveQrToken, scanTowerToken, type TowerScanResult } from '../api/client';
import { homePathForRole } from '../utils/auth';
import CachePage from './Cache';
import PointPage from './Point';
import TowerScanResultView from '../components/TowerScanResultView';

type QrTarget = { kind: 'point' | 'cache'; id: number };

export default function QrEntryPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [target, setTarget] = useState<QrTarget | null>(null);
  const [towerResult, setTowerResult] = useState<TowerScanResult | null>(null);

  useEffect(() => {
    if (!token) {
      setError('Ссылка недействительна');
      return;
    }

    const authToken = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    const factionId = localStorage.getItem('faction_id');
    const entryPath = `/g/${token}`;

    if (!authToken) {
      navigate('/login', { replace: true, state: { from: entryPath } });
      return;
    }

    if (role !== 'engineer' && !(role === 'faction' || (role === 'commander' && factionId))) {
      navigate(homePathForRole(role, factionId), { replace: true });
      return;
    }

    if (role === 'faction' || role === 'commander') {
      scanTowerToken(token)
        .then(setTowerResult)
        .catch((e) => setError(e instanceof Error ? e.message : 'Ссылка недействительна или устарела'));
      return;
    }

    resolveQrToken(token)
      .then(setTarget)
      .catch(() => setError('Ссылка недействительна или устарела'));
  }, [token, navigate]);

  if (error) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center p-6 text-center gap-3">
        <p className="text-sideB">{error}</p>
      </div>
    );
  }

  if (towerResult) {
    return (
      <div className="min-h-dvh p-6 max-w-lg mx-auto">
        <TowerScanResultView result={towerResult} />
      </div>
    );
  }

  if (!target) {
    return (
      <div className="min-h-dvh flex items-center justify-center text-zinc-500 text-sm">
        Открытие…
      </div>
    );
  }

  if (target.kind === 'cache') {
    return <CachePage cacheId={target.id} qrToken={token!} />;
  }

  return <PointPage pointId={target.id} />;
}
