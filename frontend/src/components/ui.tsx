import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Link2Off, Loader2 } from "lucide-react";
import type { RunStatus } from "../types/api";

export function StatusBadge({ status }: { status: RunStatus | string }) {
  const details: Record<string, { label: string; className: string; icon: ReactNode }> = {
    succeeded: { label: "완료", className: "status-success", icon: <CheckCircle2 size={14} /> },
    running: { label: "실행 중", className: "status-running", icon: <Loader2 size={14} className="animate-spin" /> },
    failed: { label: "실패", className: "status-failed", icon: <AlertTriangle size={14} /> },
    not_connected: { label: "미연결", className: "status-muted", icon: <Link2Off size={14} /> },
    insufficient_information: { label: "정보 부족", className: "status-warning", icon: <AlertTriangle size={14} /> },
    not_started: { label: "대기", className: "status-muted", icon: <CircleDashed size={14} /> },
  };
  const value = details[status] ?? details.not_started;
  return <span className={`status ${value.className}`}>{value.icon}{value.label}</span>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return <div className="empty"><CircleDashed size={28} /><strong>{title}</strong><p>{message}</p></div>;
}
