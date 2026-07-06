import { useEffect, useRef } from 'react';

/** Swipe-back / browser back closes overlay instead of leaving the app. */
export function useOverlayBackClose(open: boolean, onClose: () => void) {
  const closedByPopRef = useRef(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;

    closedByPopRef.current = false;
    window.history.pushState({ msrOverlay: true }, '');

    const onPopState = () => {
      closedByPopRef.current = true;
      onCloseRef.current();
    };

    window.addEventListener('popstate', onPopState);
    return () => {
      window.removeEventListener('popstate', onPopState);
      if (!closedByPopRef.current) {
        window.history.back();
      }
    };
  }, [open]);
}
