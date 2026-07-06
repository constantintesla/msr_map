import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { fetchAdminStatus } from '../api/client';

export default function QRPrint() {
  const [pages, setPages] = useState<Array<{ label: string; url: string; qr: string; hint?: string }>>([]);

  useEffect(() => {
    fetchAdminStatus().then((data) => {
      const items = [
        ...data.points
          .filter((p) => p.entry_url)
          .map((p) => ({
            label: p.name,
            url: p.entry_url!,
          })),
        ...data.caches
          .filter((c) => c.entry_url)
          .map((c) => ({
            label: c.name,
            url: c.entry_url!,
            hint:
              c.cache_kind === 'film_loot'
                ? c.loot_variant === 'box_direct'
                  ? 'QR → войти → код от штаба → забрать → база'
                  : 'QR → войти → код от штаба → подрыв → видео → база'
                : 'QR → войти → код от штаба → удержание',
          })),
      ];
      Promise.all(
        items.map(async (item) => ({
          ...item,
          qr: await QRCode.toDataURL(item.url, { margin: 2, width: 256 }),
        }))
      ).then(setPages);
    });
  }, []);

  return (
    <div className="no-print">
      <button
        type="button"
        className="btn bg-sideA text-white mb-4"
        onClick={() => window.print()}
      >
        Печать QR
      </button>
      <div className="hidden print:block">
        {pages.map((page) => (
          <div key={page.url} className="qr-page flex flex-col items-center justify-center">
            <h1 className="text-2xl font-bold mb-4">{page.label}</h1>
            <img src={page.qr} alt={page.label} width={256} height={256} />
            {page.hint && <p className="mt-4 text-base">{page.hint}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
