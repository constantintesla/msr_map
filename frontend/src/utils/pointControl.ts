/** Сторона, контролирующая точку на карте (идёт захват или уже захвачена). */
export function pointController(p: { held_by?: string | null; side?: string | null }): string | null {
  return p.held_by ?? p.side ?? null;
}

/** Этап 1: КТ захвачена — владелец в point.side. */
export function isStage1Captured(p: { side?: string | null }): boolean {
  return !!p.side;
}

/** Этап 1: идёт захват (удержание), владелец ещё не закреплён. */
export function isStage1Capturing(p: { held_by?: string | null; side?: string | null }): boolean {
  return !!p.held_by && !p.side;
}

/** Этап 1: состояние блокировки захвата для инженера текущей стороны. */
export function stage1CaptureBlocked(
  p: { side?: string | null; held_by?: string | null } | undefined,
  mySide: string,
  recapturable: boolean,
): {
  ownedByUs: boolean;
  lockedByEnemy: boolean;
  underAttack: boolean;
  blocked: boolean;
} {
  const enemyHolding = !!p?.held_by && p.held_by !== mySide;
  const ownedByUs = !!p?.side && p.side === mySide && !enemyHolding;
  const lockedByEnemy = !!p?.side && p.side !== mySide && !recapturable;
  const underAttack = !!p?.side && p.side === mySide && enemyHolding;
  return {
    ownedByUs,
    lockedByEnemy,
    underAttack,
    blocked: ownedByUs || lockedByEnemy || underAttack,
  };
}
