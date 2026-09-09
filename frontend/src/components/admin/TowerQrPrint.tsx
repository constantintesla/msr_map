import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import type { TowerAdminOverview } from '../../api/client';

interface QrCard {
  key: string;
  label: string;
  sublabel: string;
  url: string;
  manualCode: string | null;
  qr: string;
}

function buildItems(overview: TowerAdminOverview): Array<Omit<QrCard, 'qr'>> {
  const items: Array<Omit<QrCard, 'qr'>> = [];
  for (const f of overview.factions) {
    if (f.join_url) {
      items.push({
        key: `join-${f.id}`,
        label: `Регистрация — ${f.name}`,
        sublabel: 'Ссылка для игроков стороны (позывной + PIN)',
        url: f.join_url,
        manualCode: null,
      });
    }
    if (f.qr_url) {
      items.push({
        key: `qr-${f.id}`,
        label: `Табличка — ${f.name}`,
        sublabel: f.kind === 'village' ? 'QR на входе в деревню' : 'QR стороны',
        url: f.qr_url,
        manualCode: f.manual_code,
      });
    }
  }
  for (const z of overview.ur_zones) {
    for (const p of z.points) {
      if (p.qr_url) {
        items.push({
          key: `ur-${p.id}`,
          label: p.name,
          sublabel: `Точка укрепрайона ${z.name}`,
          url: p.qr_url,
          manualCode: p.manual_code,
        });
      }
    }
  }
  return items;
}

function downloadDataUrl(dataUrl: string, filename: string) {
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export default function TowerQrPrint({ overview }: { overview: TowerAdminOverview }) {
  const [cards, setCards] = useState<QrCard[]>([]);

  useEffect(() => {
    let cancelled = false;
    const items = buildItems(overview);
    Promise.all(
      items.map(async (item) => ({
        ...item,
        qr: await QRCode.toDataURL(item.url, { margin: 2, width: 480 }),
      }))
    ).then((result) => {
      if (!cancelled) setCards(result);
    });
    return () => {
      cancelled = true;
    };
  }, [overview]);

  return (
    <div className="space-y-3">
      <div className="no-print flex items-center justify-between gap-2">
        <p className="text-xs text-zinc-500">
          QR-коды для печати табличек и раздачи ссылок регистрации. {cards.length} шт.
        </p>
        <button type="button" className="btn text-xs bg-sideA text-white" onClick={() => window.print()}>
          Печать всех
        </button>
      </div>

      <div className="no-print grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {cards.map((card) => (
          <div key={card.key} className="rounded-lg border border-zinc-700 bg-zinc-950 p-3 flex flex-col items-center gap-2">
            <img src={card.qr} alt={card.label} className="w-full max-w-[160px] rounded bg-white p-1" />
            <div className="text-center">
              <div className="text-sm font-semibold text-zinc-100">{card.label}</div>
              <div className="text-xs text-zinc-500">{card.sublabel}</div>
              {card.manualCode && (
                <div className="text-xs text-zinc-400 mt-1">
                  Код вручную: <span className="font-mono text-sideA">{card.manualCode}</span>
                </div>
              )}
            </div>
            <button
              type="button"
              className="btn text-xs py-0.5 px-2 min-h-0 border border-zinc-600 w-full"
              onClick={() => downloadDataUrl(card.qr, `${card.key}.png`)}
            >
              Скачать PNG
            </button>
          </div>
        ))}
      </div>

      <div className="hidden print:block">
        {cards.map((card) => (
          <div key={card.key} className="qr-page flex flex-col items-center justify-center">
            <h1 className="text-2xl font-bold mb-4">{card.label}</h1>
            <img src={card.qr} alt={card.label} width={320} height={320} />
            <p className="mt-4 text-base">{card.sublabel}</p>
            {card.manualCode && <p className="mt-2 text-lg font-mono">Код вручную: {card.manualCode}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
