import type { ReactNode } from "react";
import { Boxes, ClipboardCheck, FileText, LayoutDashboard, Package, Wallet, Waves } from "lucide-react";

export type Page = "dashboard" | "product" | "fob" | "origin" | "vnm" | "extras" | "results";
export type Stage = { id: Page; label: string; hint?: string };
const icons = [LayoutDashboard, Package, Wallet, ClipboardCheck, Waves, FileText];

export function Layout({ page, setPage, stages, children }: {
  page: Page; setPage: (page: Page) => void; stages: Stage[]; children: ReactNode;
}) {
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">F</span><span>FTA <b>Compass</b></span></div>
      <p className="workspace-label">FTA 업무 단계</p>
      <nav>{stages.map((stage, index) => { const Icon = icons[index] ?? Boxes; return <button key={stage.id} onClick={() => setPage(stage.id)} className={`nav-link ${page === stage.id ? "active" : ""}`}><Icon size={18}/><span>{index}. {stage.label}</span></button>; })}</nav>
      <div className="sidebar-note"><span className="dot"/> API <small>FTA 플랫폼</small></div>
    </aside>
    <main className="main"><header className="topbar"><div><p className="eyebrow">FTA 활용 플랫폼</p><h1>{stages.find(item => item.id === page)?.label ?? (page === "results" ? "분석 결과" : "FTA Compass")}</h1></div></header>{children}</main>
  </div>;
}
