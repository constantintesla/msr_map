import { useCallback, useEffect, useState } from 'react';
import { fetchEngineerProfile, type EngineerProfile } from '../api/client';
import { engineerSocketHub } from '../ws/hubs';

export function useEngineerProfile() {
  const [profile, setProfile] = useState<EngineerProfile | null>(null);
  const isEngineer = localStorage.getItem('role') === 'engineer';
  const username = localStorage.getItem('username') || '';

  const load = useCallback(() => {
    if (!isEngineer) return;
    fetchEngineerProfile()
      .then(setProfile)
      .catch(() => {});
  }, [isEngineer]);

  useEffect(() => {
    if (!isEngineer) return;

    load();
    const pollId = setInterval(load, 30000);

    const unsub = engineerSocketHub.subscribe((packet) => {
      if (packet.e === 'lpd_channel' && packet.u === username) {
        setProfile((prev) =>
          prev
            ? {
                ...prev,
                lpd_channel: (packet.ch as number | null) ?? null,
                lpd_frequency_mhz: (packet.freq as number | null) ?? null,
                lpd_label: (packet.label as string | null) ?? null,
              }
            : prev
        );
      }
    });

    return () => {
      clearInterval(pollId);
      unsub();
    };
  }, [isEngineer, username, load]);

  return profile;
}
