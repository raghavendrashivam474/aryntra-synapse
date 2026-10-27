import { useEffect, useRef, useCallback } from "react";

interface Props {
  title: string;
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export default function ModalShell({ title, isOpen, onClose, children }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  // Open/close the native dialog
  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (isOpen && !el.open) {
      previousFocus.current = document.activeElement as HTMLElement;
      el.showModal();
    } else if (!isOpen && el.open) {
      el.close();
      previousFocus.current?.focus();
    }
  }, [isOpen]);

  // Escape key is handled natively by <dialog>, but we also
  // listen for the cancel event to sync React state.
  const handleCancel = useCallback(
    (e: React.SyntheticEvent) => {
      e.preventDefault();
      onClose();
    },
    [onClose]
  );

  // Backdrop click
  const handleBackdrop = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === dialogRef.current) onClose();
    },
    [onClose]
  );

  if (!isOpen) return null;

  return (
    <dialog
      ref={dialogRef}
      className="modal-shell"
      aria-label={title}
      onCancel={handleCancel}
      onClick={handleBackdrop}
    >
      <div className="modal-header">
        <h2 className="modal-title">{title}</h2>
        <button
          className="modal-close"
          onClick={onClose}
          aria-label="Close inspection"
        >
          ✕
        </button>
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
