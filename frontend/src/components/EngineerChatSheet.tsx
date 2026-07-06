import { useState } from 'react';
import { createPortal } from 'react-dom';
import ChatPanel from './ChatPanel';
import { useOverlayBackClose } from '../hooks/useOverlayBackClose';

interface EngineerChatAsideProps {
  side: 'A' | 'B';
  onClose: () => void;
  className?: string;
}

export function EngineerChatAside({ side, onClose, className = '' }: EngineerChatAsideProps) {
  return (
    <aside
      className={`relative z-10 flex flex-col min-h-0 bg-zinc-950 border-zinc-800 ${className}`}
    >
      <div className="shrink-0 flex justify-between items-center px-3 py-2 border-b border-zinc-800">
        <span className="text-sm font-medium text-zinc-300">Штаб</span>
        <button type="button" className="text-zinc-500 text-sm px-2 hover:text-zinc-300" onClick={onClose}>
          ✕
        </button>
      </div>
      <ChatPanel mode="engineer" side={side} className="flex-1 min-h-0" />
    </aside>
  );
}

interface EngineerChatSheetProps {
  side: 'A' | 'B';
  /** Только кнопка — панель рендерит родитель (рядом с картой) */
  variant?: 'overlay' | 'toggle';
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  buttonClassName?: string;
}

export default function EngineerChatSheet({
  side,
  variant = 'overlay',
  open: openProp,
  onOpenChange,
  buttonClassName = '',
}: EngineerChatSheetProps) {
  const [openInternal, setOpenInternal] = useState(false);
  const open = openProp ?? openInternal;
  const setOpen = onOpenChange ?? setOpenInternal;

  const toggle = () => setOpen(!open);
  const close = () => setOpen(false);

  useOverlayBackClose(variant === 'overlay' && open, close);

  return (
    <>
      <button
        type="button"
        className={`btn text-sm border min-h-0 py-1.5 px-3 ${
          open ? 'border-warning bg-warning/15 text-warning' : 'border-zinc-600 text-zinc-300'
        } ${buttonClassName}`}
        onClick={toggle}
      >
        Штаб {open ? '▼' : '▲'}
      </button>

      {variant === 'overlay' &&
        open &&
        createPortal(
          <>
            <button
              type="button"
              className="fixed inset-0 z-[4999] bg-black/40"
              aria-label="Закрыть чат"
              onClick={close}
            />
            <div
              className="fixed inset-x-0 bottom-0 z-[5000] flex flex-col border-t border-zinc-700 bg-zinc-950 shadow-2xl"
              style={{ height: 'min(52vh, 420px)' }}
              role="dialog"
              aria-modal="true"
              aria-label="Штаб"
            >
              <EngineerChatAside side={side} onClose={close} className="flex-1 min-h-0 z-auto" />
            </div>
          </>,
          document.body,
        )}
    </>
  );
}
