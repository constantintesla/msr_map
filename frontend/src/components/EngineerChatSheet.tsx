import { useState } from 'react';
import ChatPanel from './ChatPanel';

interface EngineerChatAsideProps {
  side: 'A' | 'B';
  onClose: () => void;
  className?: string;
}

export function EngineerChatAside({ side, onClose, className = '' }: EngineerChatAsideProps) {
  return (
    <aside
      className={`flex flex-col min-h-0 bg-zinc-950 border-zinc-800 ${className}`}
    >
      <div className="shrink-0 flex justify-between items-center px-3 py-2 border-b border-zinc-800">
        <span className="text-sm font-medium text-zinc-300">Чат со штабом</span>
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
}

export default function EngineerChatSheet({
  side,
  variant = 'overlay',
  open: openProp,
  onOpenChange,
}: EngineerChatSheetProps) {
  const [openInternal, setOpenInternal] = useState(false);
  const open = openProp ?? openInternal;
  const setOpen = onOpenChange ?? setOpenInternal;

  const toggle = () => setOpen(!open);

  return (
    <>
      <button
        type="button"
        className={`btn text-sm border min-h-0 py-1.5 px-3 ${
          open ? 'border-warning bg-warning/15 text-warning' : 'border-zinc-600 text-zinc-300'
        }`}
        onClick={toggle}
      >
        Штаб {open ? '▼' : '▲'}
      </button>

      {variant === 'overlay' && open && (
        <div
          className="fixed inset-x-0 bottom-0 z-[5000] flex flex-col border-t border-zinc-700 bg-zinc-950 shadow-2xl"
          style={{ height: 'min(52vh, 420px)' }}
        >
          <EngineerChatAside side={side} onClose={() => setOpen(false)} className="flex-1 min-h-0" />
        </div>
      )}
    </>
  );
}
