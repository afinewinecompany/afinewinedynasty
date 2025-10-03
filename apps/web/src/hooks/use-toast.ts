import { useState, useCallback } from 'react';

interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive';
}

let toastCounter = 0;
const listeners = new Set<(toasts: Toast[]) => void>();
let memoryToasts: Toast[] = [];

function addToast(toast: Omit<Toast, 'id'>) {
  const id = `toast-${++toastCounter}`;
  const newToast: Toast = { ...toast, id };

  memoryToasts = [...memoryToasts, newToast];
  listeners.forEach((listener) => listener(memoryToasts));

  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    memoryToasts = memoryToasts.filter((t) => t.id !== id);
    listeners.forEach((listener) => listener(memoryToasts));
  }, 5000);
}

function dismissToast(id: string) {
  memoryToasts = memoryToasts.filter((t) => t.id !== id);
  listeners.forEach((listener) => listener(memoryToasts));
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>(memoryToasts);

  useCallback(() => {
    listeners.add(setToasts);
    return () => {
      listeners.delete(setToasts);
    };
  }, []);

  return {
    toasts,
    toast: addToast,
    dismiss: dismissToast,
  };
}

export const toast = addToast;
