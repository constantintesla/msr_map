let audioCtx: AudioContext | null = null;

function getCtx(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return null;
    if (!audioCtx) audioCtx = new Ctx();
    if (audioCtx.state === 'suspended') void audioCtx.resume();
    return audioCtx;
  } catch {
    return null;
  }
}

function tone(ctx: AudioContext, freq: number, start: number, duration: number, volume = 0.12) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.setValueAtTime(freq, start);
  gain.gain.setValueAtTime(volume, start);
  gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(start);
  osc.stop(start + duration + 0.02);
}

/** Short ping for incoming chat messages. */
export function playMessagePing() {
  const ctx = getCtx();
  if (!ctx) return;
  const t = ctx.currentTime;
  tone(ctx, 880, t, 0.1);
}

/** Distinct two-tone ping for field orders. */
export function playOrderPing() {
  const ctx = getCtx();
  if (!ctx) return;
  const t = ctx.currentTime;
  tone(ctx, 660, t, 0.1);
  tone(ctx, 990, t + 0.14, 0.14, 0.14);
}

/** Resume audio after user gesture (mobile browsers). */
export function unlockNotificationAudio() {
  const ctx = getCtx();
  if (ctx?.state === 'suspended') void ctx.resume();
}
