import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes, useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost"; pending?: boolean };
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ variant = "secondary", pending, className = "", disabled, children, ...props }, ref) {
  return <button ref={ref} className={`ui-button ui-button--${variant} ${className}`} disabled={disabled || pending} {...props}>{pending ? "Working…" : children}</button>;
});

export const IconButton = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement>>(function IconButton({ className = "", ...props }, ref) {
  return <button ref={ref} type="button" className={`ui-icon-button ${className}`} {...props} />;
});

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return <header className="ui-page-header"><div><h1 className="page-title">{title}</h1>{subtitle && <p className="page-subtitle">{subtitle}</p>}</div>{actions && <div className="ui-page-header-actions">{actions}</div>}</header>;
}

export function Surface({ className = "", children, ...props }: HTMLAttributes<HTMLElement> & { children: ReactNode }) {
  return <section className={`ui-surface ${className}`} {...props}>{children}</section>;
}

export function Field({ label, hint, htmlFor, error, children }: { label: string; hint?: string; htmlFor?: string; error?: string; children: ReactNode }) {
  return <div className="ui-field"><label className="field-label" htmlFor={htmlFor}>{label}</label>{children}{error ? <span className="ui-field-error" role="alert">{error}</span> : hint && <span className="field-hint">{hint}</span>}</div>;
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className = "", ...props }, ref) { return <input ref={ref} className={`ui-input ${className}`} {...props} />; });
export const TextArea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function TextArea({ className = "", ...props }, ref) { return <textarea ref={ref} className={`ui-textarea ${className}`} {...props} />; });

export function StatusBadge({ state }: { state: string }) { return <span className={`ui-status ui-status--${state}`}>{state}</span>; }

export function Tabs<T extends string>({ value, tabs, onChange }: { value: T; tabs: { value: T; label: string; count?: number }[]; onChange: (value: T) => void }) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const move = (index: number) => { const next = (index + tabs.length) % tabs.length; onChange(tabs[next].value); refs.current[next]?.focus(); };
  return <div className="ui-tabs" role="tablist" aria-label="Idea filters">{tabs.map((tab, index) => <button key={tab.value} ref={(node) => { refs.current[index] = node; }} role="tab" aria-selected={value === tab.value} className={`ui-tab ${value === tab.value ? "is-active" : ""}`} onClick={() => onChange(tab.value)} onKeyDown={(event) => { if (event.key === "ArrowRight") { event.preventDefault(); move(index + 1); } if (event.key === "ArrowLeft") { event.preventDefault(); move(index - 1); } if (event.key === "Home") { event.preventDefault(); move(0); } if (event.key === "End") { event.preventDefault(); move(tabs.length - 1); } }}>{tab.label}{tab.count !== undefined && <span>{tab.count}</span>}</button>)}</div>;
}

export function LoadingState({ label = "Loading…" }: { label?: string }) { return <div className="ui-state" role="status">{label}</div>; }
export function EmptyState({ children }: { children: ReactNode }) { return <div className="ui-state">{children}</div>; }
export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) { return <div className="ui-state ui-state--error" role="alert"><span>{error.message}</span>{onRetry && <Button type="button" onClick={onRetry}>Retry</Button>}</div>; }

export function Modal({ title, titleAside, footer, onClose, children, width = 520 }: { title: string; titleAside?: ReactNode; footer: ReactNode; onClose: () => void; children: ReactNode; width?: 440 | 520 | 560 | 640 }) {
  const titleId = useId(); const dialogRef = useRef<HTMLDivElement>(null); const activeRef = useRef<HTMLElement | null>(null);
  useEffect(() => { activeRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; const focusable = dialogRef.current?.querySelector<HTMLElement>("button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [href]"); focusable?.focus(); const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); if (event.key !== "Tab" || !dialogRef.current) return; const nodes = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [href]")]; if (!nodes.length) return; const first = nodes[0], last = nodes[nodes.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } }; document.addEventListener("keydown", onKey); return () => { document.removeEventListener("keydown", onKey); activeRef.current?.focus(); }; }, [onClose]);
  return <div className="modal-overlay" onMouseDown={onClose}><div ref={dialogRef} className={`modal ui-modal ui-modal--${width}`} role="dialog" aria-modal="true" aria-labelledby={titleId} onMouseDown={(event) => event.stopPropagation()}><div className="modal-header"><h2 id={titleId} className="modal-title">{title}</h2>{titleAside}<IconButton aria-label={`Close ${title}`} onClick={onClose}><X size={18} /></IconButton></div><div className="modal-body">{children}</div><div className="modal-footer">{footer}</div></div></div>;
}
