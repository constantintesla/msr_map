import type { ReactNode } from 'react';
import MobileSheet from '../MobileSheet';

interface AdminPanelShellProps {
  open: boolean;
  isNarrow: boolean;
  onClose: () => void;
  title: string;
  borderClass?: string;
  children: ReactNode;
}

/** Inline section on desktop, full-screen sheet on narrow viewports. */
export default function AdminPanelShell({
  open,
  isNarrow,
  onClose,
  title,
  borderClass = 'border-zinc-800',
  children,
}: AdminPanelShellProps) {
  if (!open) return null;

  if (isNarrow) {
    return (
      <MobileSheet open onClose={onClose} title={title}>
        {children}
      </MobileSheet>
    );
  }

  return (
    <section
      className={`no-print shrink-0 z-20 border-b ${borderClass} bg-zinc-900/98 backdrop-blur-sm shadow-lg max-h-[min(52vh,440px)] overflow-y-auto`}
    >
      {children}
    </section>
  );
}
