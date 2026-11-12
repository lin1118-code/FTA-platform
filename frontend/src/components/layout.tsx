import type { ReactNode } from "react";
import { Boxes, ClipboardCheck, FileText, LayoutDashboard, Package, Wallet, Waves } from "lucide-react";

export type Page = "dashboard" | "product" | "fob" | "origin" | "vnm" | "extras" | "results";
export type Stage = { id: Page; label: string; hint?: string };
const icons = [LayoutDashboard, Package, Wallet, ClipboardCheck, Waves, FileText];

export function Layout({ page, setPage, stages, selectedProductName, children }: {
  page: Page; setPage: (page: Page) => void; stages: Stage[]; selectedProductName: string; children: ReactNode;
}) {
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">F</span><span>FTA <b>Compass</b></span></div>
      <p className="workspace-label">FTA WORKFLOW</p>
      <nav>{stages.map((stage, index) => { const Icon = icons[index] ?? Boxes; return <button key={stage.id} onClick={() => setPage(stage.id)} className={`nav-link ${page === stage.id ? "active" : ""}`}><Icon size={18}/><span>{index}. {stage.label}</span></button>; })}</nav>
      <div className="sidebar-note"><span className="dot"/> API <small>{selectedProductName}</small></div>
    </aside>
    <main className="main"><header className="topbar"><div><p className="eyebrow">FTA UTILIZATION PLATFORM</p><h1>{stages.find(item => item.id === page)?.label ?? (page === "results" ? "분석 결과" : "FTA Compass")}</h1></div><div className="topbar-product">{selectedProductName}</div></header>{children}</main>
  </div>;
}
