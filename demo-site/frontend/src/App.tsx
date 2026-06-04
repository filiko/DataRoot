import React, { useEffect, useRef, useState } from "react";
import { SidebarGrading } from "./components/SidebarGrading";
import { ERDCanvas } from "./components/ERDCanvas";
import { DFDCanvas } from "./components/DFDCanvas";
import { ExportPanel } from "./components/ExportPanel";
import { SchemaInspector } from "./components/SchemaInspector";
import { LoginPage, type SessionUser } from "./components/LoginPage";
import { LandingPage } from "./components/LandingPage";
import { ProjectList } from "./components/ProjectList";
import { ShareDialog } from "./components/ShareDialog";
import { WarningsBanner } from "./components/WarningsBanner";
import type { PenFile } from "./types/pen";
import { GitBranch, Download, List, Boxes, Wand2, FileDown, Share2, ArrowLeft, Palette } from "lucide-react";
import { useLayoutPatch } from "./hooks/useLayoutPatch";
import { useProjectPolling } from "./hooks/useProjectPolling";
import { buildDfdLayoutGraph, buildErdLayoutGraph } from "./components/diagram/layout/graphModel";
import {
  optimizeDiagramLayout,
  toLayoutEdgePatch,
  toLayoutNodePatch,
} from "./components/diagram/layout/optimizeLayout";
import { toPng } from "html-to-image";
import jsPDF from "jspdf";
import { API } from "./config/api";
import { useAppTheme, APP_THEMES } from "./context/ThemeContext";
import { getDiagramTheme } from "./styles/diagramThemes";
import { DemoSwitcher } from "./components/DemoSwitcher";
import { loadDemoProject, DEMO_PROJECTS, type DemoProject } from "./components/datademo/loadDemo";
import { DocsPage } from "./components/DocsPage";

function ThemeSwitcher() {
  const { theme, setTheme } = useAppTheme();
  const diagramTheme = getDiagramTheme(theme.diagramThemeId);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "6px 10px",
          borderRadius: 6,
          fontSize: 12, fontWeight: 600,
          background: diagramTheme.menu.accentBg,
          color: diagramTheme.menu.accentText,
          border: `1px solid ${diagramTheme.menu.border}`,
          cursor: "pointer",
        }}
      >
        <Palette className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">{diagramTheme.name}</span>
      </button>
      {open && (
        <div style={{
          position: "absolute", right: 0, top: "100%", marginTop: 4,
          display: "grid", gridTemplateColumns: "1fr",
          gap: 4,
          background: diagramTheme.menu.bg,
          border: `1px solid ${diagramTheme.menu.border}`,
          borderRadius: 8,
          boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
          zIndex: 50,
          padding: 6,
          minWidth: 150,
        }}>
          {APP_THEMES.map((t) => {
            const dt = getDiagramTheme(t.diagramThemeId);
            return (
              <button
                key={t.id}
                onClick={() => { setTheme(t.id); setOpen(false); }}
                style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "8px 10px",
                  textAlign: "left",
                  borderRadius: 6,
                  fontSize: 12, fontWeight: 500,
                  background: theme.id === t.id ? dt.menu.accentBg : "transparent",
                  color: theme.id === t.id ? dt.menu.accentText : dt.menu.text,
                  border: "none",
                  cursor: "pointer",
                  transition: "background .1s",
                }}
                onMouseEnter={e => { if (theme.id !== t.id) e.currentTarget.style.background = dt.menu.bgHover; }}
                onMouseLeave={e => { if (theme.id !== t.id) e.currentTarget.style.background = "transparent"; }}
              >
                <span style={{ width: 14, height: 14, borderRadius: 4, background: dt.canvas.bg, border: `2px solid ${dt.dfd.process.border}` }} />
                {dt.name}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
type ActiveTab = "erd" | "dfd" | "inspector" | "export";

function readInviteFromUrl(): string | null {
  const m = window.location.pathname.match(/^\/invite\/([^/]+)/);
  return m ? m[1] : null;
}

function clearInviteFromUrl() {
  if (window.location.pathname.startsWith("/invite/")) {
    window.history.replaceState({}, "", "/");
  }
}

export default function App() {
  const { theme } = useAppTheme();
  const diagramTheme = getDiagramTheme(theme.diagramThemeId);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [pendingInviteToken, setPendingInviteToken] = useState<string | null>(null);
  const [inviteBanner, setInviteBanner] = useState<string | null>(null);

  const [showLogin, setShowLogin] = useState(false);
  const [showProjects, setShowProjects] = useState(false);

  const [projectId, setProjectId] = useState<string | null>(null);
  const [pen, setPen] = useState<PenFile | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("erd");
  const [arrangingAll, setArrangingAll] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [activeDemoId, setActiveDemoId] = useState<string | null>(null);
  const [demoSwitching, setDemoSwitching] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [collaboratorToast, setCollaboratorToast] = useState<string | null>(null);
  const diagramRef = useRef<HTMLDivElement>(null);
  const { patchLayout } = useLayoutPatch(projectId ?? "");
  const isDocsRoute = window.location.pathname === "/docs" || window.location.pathname.startsWith("/docs/");
  const isDemoRoute = window.location.pathname === "/demo";

  // ── Auth bootstrap ────────────────────────────────────────────────────────
  useEffect(() => {
    setPendingInviteToken(readInviteFromUrl());
    fetch(API.me())
      .then(async (res) => {
        if (res.ok) {
          const u: SessionUser = await res.json();
          setUser(u);
        }
      })
      .catch(() => {})
      .finally(() => setAuthChecked(true));
  }, []);

  // ── Auto-load demo when visiting /demo ───────────────────────────────────
  useEffect(() => {
    if (!isDemoRoute || !authChecked || pen) return;
    loadDemoProject().then(({ projectId: id, pen: p }) => {
      if (!user) setUser({ id: "guest", username: "demo" });
      setProjectId(id);
      setPen(p);
      setActiveTab("erd");
      setActiveDemoId(DEMO_PROJECTS[0].id);
    }).catch(() => {});
  }, [authChecked]);

  // ── Invite acceptance after login ─────────────────────────────────────────
  useEffect(() => {
    if (!user || !pendingInviteToken) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(API.acceptInvite(pendingInviteToken), { method: "POST" });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error(detail.detail || `Invite failed (${res.status})`);
        }
        const data: { project_id: string } = await res.json();
        if (cancelled) return;
        // Open the project
        const penRes = await fetch(API.projects(data.project_id));
        if (penRes.ok) {
          const p: PenFile = await penRes.json();
          if (!cancelled) {
            setProjectId(data.project_id);
            setPen(p);
            setActiveTab("erd");
            setInviteBanner(`Joined "${p.project.name}" as editor.`);
            setTimeout(() => setInviteBanner(null), 4000);
          }
        }
      } catch (err: any) {
        setInviteBanner(`Invite error: ${err.message || err}`);
      } finally {
        setPendingInviteToken(null);
        clearInviteFromUrl();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, pendingInviteToken]);

  // ── Polling: pick up edits from other collaborators ──────────────────────
  useProjectPolling({
    projectId,
    currentRevision: pen?.project.revision,
    enabled: !!pen && !!projectId,
    onRefresh: (incoming) => {
      setPen(incoming);
      setCollaboratorToast(`Synced changes from another collaborator (rev ${incoming.project.revision}).`);
      setTimeout(() => setCollaboratorToast(null), 3000);
    },
  });

  // ── Project lifecycle ─────────────────────────────────────────────────────
  const openProject = (id: string, p: PenFile) => {
    if (!user) setUser({ id: "guest", username: "demo" });
    setProjectId(id);
    setPen(p);
    setActiveTab("erd");
    setShowProjects(false);
    // Mark as demo mode — activeDemoId defaults to first demo entry
    setActiveDemoId(DEMO_PROJECTS[0].id);
  };

  const closeProject = () => {
    setProjectId(null);
    setPen(null);
    setActiveDemoId(null);
    if (user?.id === "guest") setUser(null);
  };

  const handleSwitchDemo = async (demo: DemoProject) => {
    setDemoSwitching(true);
    try {
      const { projectId: id, pen: p } = await loadDemoProject(demo);
      setActiveDemoId(demo.id);
      setProjectId(id);
      setPen(p);
      setActiveTab("erd");
    } catch {}
    setDemoSwitching(false);
  };

  const handlePenUpdate = (updated: PenFile) => setPen(updated);

  const handleAutoArrangeAll = async () => {
    if (!pen) return;
    setArrangingAll(true);
    try {
      let current = pen;
      const scopes = [
        { diagram: "erd" as const, level: "root" as const },
        { diagram: "dfd" as const, level: "root" as const },
        ...current.dfd.processes
          .filter((process) => process.level_1_diagram)
          .map((process) => ({
            diagram: "dfd" as const,
            level: "process" as const,
            process_id: process.id,
          })),
      ];

      for (const scope of scopes) {
        const graph =
          scope.diagram === "erd"
            ? buildErdLayoutGraph(current)
            : buildDfdLayoutGraph(current, scope);
        const result = await optimizeDiagramLayout(graph, {
          mode: "auto",
          gridSize: scope.diagram === "erd" ? 20 : 24,
        });
        current = await patchLayout({
          scope,
          baseRevision: current.project.revision,
          nodes: result.nodes.map(toLayoutNodePatch),
          edges: result.edges.map(toLayoutEdgePatch),
        });
      }
      setPen(current);
    } catch (err) {
      alert(`Failed to auto arrange project: ${err}`);
    } finally {
      setArrangingAll(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!diagramRef.current) return;
    setExportingPdf(true);
    try {
      const el = diagramRef.current;
      const dataUrl = await toPng(el, { backgroundColor: "#f9fafb", pixelRatio: 2 });
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      const pdf = new jsPDF({
        orientation: w >= h ? "landscape" : "portrait",
        unit: "px",
        format: [w, h],
      });
      pdf.addImage(dataUrl, "PNG", 0, 0, w, h);
      pdf.save(`diagram-${activeTab}.pdf`);
    } catch (err) {
      alert(`Failed to export PDF: ${err}`);
    } finally {
      setExportingPdf(false);
    }
  };

  const tabs: { id: ActiveTab; icon: React.ReactNode; label: string }[] = [
    { id: "erd", icon: <GitBranch className="w-4 h-4" />, label: "ERD" },
    { id: "dfd", icon: <Boxes className="w-4 h-4" />, label: "DFD" },
    { id: "inspector", icon: <List className="w-4 h-4" />, label: "Schema" },
    { id: "export", icon: <Download className="w-4 h-4" />, label: "Export" },
  ];

  // ── Render gates ──────────────────────────────────────────────────────────
  if (isDocsRoute) {
    return <DocsPage />;
  }

  if (!authChecked || (isDemoRoute && !pen)) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-gray-500">
        Loading…
      </div>
    );
  }

  if (!user) {
    if (showLogin || pendingInviteToken) {
      return (
        <LoginPage
          onLogin={(u) => { setUser(u); setShowLogin(false); }}
          pendingInviteToken={pendingInviteToken}
          onBack={pendingInviteToken ? undefined : () => setShowLogin(false)}
        />
      );
    }
    return (
      <LandingPage
        onIngested={openProject}
        onStartBlank={openProject}
        onLoadExample={openProject}
        onLoadMorSat0Exercise={openProject}
        onLoadClaudeEval={openProject}
        onLoadRepoAnalysis={openProject}
      />
    );
  }

  if (showProjects && user && (!pen || !projectId)) {
    return (
      <ProjectList
        username={user.username}
        onOpenProject={openProject}
        onLogout={() => {
          setUser(null);
          closeProject();
        }}
      />
    );
  }

  if (!pen || !projectId) {
    return (
      <LandingPage
        onIngested={openProject}
        onStartBlank={openProject}
        onLoadExample={openProject}
        onLoadMorSat0Exercise={openProject}
        onLoadClaudeEval={openProject}
        onLoadRepoAnalysis={openProject}
      />
    );
  }
  return (
    <div className="dfdmaker-app flex flex-col h-screen bg-gray-50" data-app-theme={theme.id}>
      {inviteBanner && (
        <div className="bg-indigo-50 border-b border-indigo-200 text-indigo-800 text-xs px-4 py-1.5">
          {inviteBanner}
        </div>
      )}
      {collaboratorToast && (
        <div className="fixed top-2 right-2 z-40 bg-gray-900 text-white text-xs rounded px-3 py-1.5 shadow">
          {collaboratorToast}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-80 flex-shrink-0 border-r border-gray-200 bg-white overflow-hidden flex flex-col">
          <SidebarGrading projectId={projectId} pen={pen} onPenUpdate={handlePenUpdate} />
        </aside>

        <main className="flex-1 flex flex-col overflow-hidden">
          <WarningsBanner pen={pen} />
          <div className="flex items-center justify-between h-10 px-3 flex-shrink-0">
            <div className="flex gap-1 items-center">
              <button
                onClick={closeProject}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                title="Back to home"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
              </button>
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "6px 12px",
                    borderRadius: 6,
                    fontSize: 13, fontWeight: 500,
                    background: activeTab === tab.id ? diagramTheme.menu.accentBg : "transparent",
                    color: activeTab === tab.id ? diagramTheme.menu.accentText : diagramTheme.menu.text,
                    border: "none",
                    cursor: "pointer",
                    transition: "background .1s, color .1s",
                  }}
                  onMouseEnter={e => { if (activeTab !== tab.id) e.currentTarget.style.background = diagramTheme.menu.bgHover; }}
                  onMouseLeave={e => { if (activeTab !== tab.id) e.currentTarget.style.background = "transparent"; }}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowShare(true)}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "6px 10px",
                  borderRadius: 6,
                  fontSize: 12, fontWeight: 600,
                  background: diagramTheme.menu.accentBg,
                  color: diagramTheme.menu.accentText,
                  border: `1px solid ${diagramTheme.menu.border}`,
                  cursor: "pointer",
                }}
                title="Share project"
              >
                <Share2 className="w-3.5 h-3.5" />
                Share
              </button>
              {(activeTab === "erd" || activeTab === "dfd") && (
                <button
                  onClick={handleDownloadPdf}
                  disabled={exportingPdf}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "6px 10px",
                    borderRadius: 6,
                    fontSize: 12, fontWeight: 600,
                    background: diagramTheme.menu.bg,
                    color: diagramTheme.menu.text,
                    border: `1px solid ${diagramTheme.menu.border}`,
                    cursor: "pointer",
                    opacity: exportingPdf ? 0.5 : 1,
                  }}
                >
                  <FileDown className="w-3.5 h-3.5" />
                  {exportingPdf ? "Exporting..." : "Export PDF"}
                </button>
              )}
              <button
                onClick={handleAutoArrangeAll}
                disabled={arrangingAll}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "6px 10px",
                  borderRadius: 6,
                  fontSize: 12, fontWeight: 600,
                  background: diagramTheme.menu.accentBg,
                  color: diagramTheme.menu.accentText,
                  border: `1px solid ${diagramTheme.menu.border}`,
                  cursor: "pointer",
                  opacity: arrangingAll ? 0.5 : 1,
                }}
              >
                <Wand2 className="w-3.5 h-3.5" />
                {arrangingAll ? "Arranging..." : "Auto Arrange All"}
              </button>
              <ThemeSwitcher />
              <span style={{ fontSize: 12, color: diagramTheme.menu.text, opacity: 0.6 }}>{user?.username ?? "demo"}</span>
            </div>
          </div>

          <div ref={diagramRef} className="flex-1 overflow-hidden" style={{ position: "relative" }}>
            {activeTab === "erd" && (
              <ERDCanvas pen={pen} projectId={projectId} onPenUpdate={handlePenUpdate} />
            )}
            {activeTab === "dfd" && (
              <DFDCanvas pen={pen} projectId={projectId} onPenUpdate={handlePenUpdate} />
            )}
            {activeDemoId !== null && (activeTab === "erd" || activeTab === "dfd") && (
              <DemoSwitcher
                activeDemoId={activeDemoId}
                demos={DEMO_PROJECTS}
                onSwitch={handleSwitchDemo}
                loading={demoSwitching}
              />
            )}
            {activeTab === "inspector" && (
              <div className="h-full bg-white">
                <SchemaInspector pen={pen} theme={diagramTheme} />
              </div>
            )}
            {activeTab === "export" && <ExportPanel projectId={projectId} />}
          </div>
        </main>
      </div>

      {showShare && projectId && (
        <ShareDialog projectId={projectId} onClose={() => setShowShare(false)} />
      )}
    </div>
  );
}
