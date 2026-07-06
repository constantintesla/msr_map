import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useOverlayBackClose } from '../hooks/useOverlayBackClose';

interface MobileSheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** 'full' covers the screen; 'bottom' slides up from the bottom */
  variant?: 'full' | 'bottom';
  className?: string;
  contentClassName?: string;
  closeLabel?: string;
}

export default function MobileSheet({
  open,
  onClose,
  title,
  children,
  variant = 'full',
  className = '',
  contentClassName = 'flex-1 overflow-y-auto overscroll-contain min-h-0',
  closeLabel,
}: MobileSheetProps) {
  useOverlayBackClose(open, onClose);

  if (!open) return null;

  const shellClass =
    variant === 'bottom'
      ? 'fixed inset-x-0 bottom-0 z-[5000] flex flex-col border-t border-zinc-700 bg-zinc-950 shadow-2xl max-h-[min(85dvh,720px)]'
      : 'fixed inset-0 z-[5000] flex flex-col bg-zinc-950';

  const dismissLabel = closeLabel ?? (variant === 'full' ? '← На карту' : 'Закрыть');

  return createPortal(
    <>
      {variant === 'full' && (
        <button
          type="button"
          className="fixed inset-0 z-[4999] bg-black/60"
          aria-label={dismissLabel}
          onClick={onClose}
        />
      )}
      <div className={shellClass} role="dialog" aria-modal="true" aria-label={title}>
        <div className="shrink-0 flex items-center justify-between gap-3 px-3 py-3 border-b border-zinc-800 bg-zinc-950">
          <button
            type="button"
            className="shrink-0 text-sm font-medium text-sideA px-2 py-1 -ml-1 active:opacity-80"
            onClick={onClose}
          >
            {dismissLabel}
          </button>
          <h2 className="text-sm font-bold text-zinc-100 truncate text-center flex-1">{title}</h2>
          <button
            type="button"
            className="shrink-0 text-zinc-500 text-sm px-2 py-1 hover:text-zinc-300"
            onClick={onClose}
            aria-label="Закрыть"
          >
            ✕
          </button>
        </div>
        <div className={`${contentClassName} ${className}`}>{children}</div>
      </div>
    </>,
    document.body,
  );
}
