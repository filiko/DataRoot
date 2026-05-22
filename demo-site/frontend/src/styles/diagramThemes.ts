export type DiagramThemeId = "technical" | "minimal" | "chalkboard";

export interface DfdThemeTokens {
  process: { border: string; header: string; text: string; accent: string; lightAccent: string; };
  store: { border: string; header: string; text: string; accent: string; lightAccent: string; };
  external: { border: string; header: string; text: string; accent: string; lightAccent: string; };
  edge: { stroke: string; labelBg: string; labelText: string; };
}

export interface ErdThemeTokens {
  entity: { border: string; header: string; text: string; accent: string; };
  relationship: { stroke: string; labelBg: string; labelText: string; };
  pkBadge: { bg: string; text: string; };
}

export interface DiagramTheme {
  id: DiagramThemeId;
  name: string;
  dfd: DfdThemeTokens;
  erd: ErdThemeTokens;
  canvas: { bg: string; grid: string; };
  menu: { bg: string; bgHover: string; text: string; textActive: string; accentBg: string; accentText: string; border: string; };
}

export const DIAGRAM_THEMES: DiagramTheme[] = [
  {
    id: "technical",
    name: "Technical",
    dfd: {
      process: { border: "#2563eb", header: "#eff6ff", text: "#1e3a8a", accent: "#2563eb", lightAccent: "#bbf7d0" },
      store: { border: "#15803d", header: "#f0fdf4", text: "#14532d", accent: "#15803d", lightAccent: "#bbf7d0" },
      external: { border: "#6b7280", header: "#f3f4f6", text: "#1f2937", accent: "#4b5563", lightAccent: "#d1d5db" },
      edge: { stroke: "#1e3a8a", labelBg: "#ffffff", labelText: "#6b7280" },
    },
    erd: {
      entity: { border: "#6366f1", header: "#eef2ff", text: "#1e1b4b", accent: "#6366f1" },
      relationship: { stroke: "#3730a3", labelBg: "#ffffff", labelText: "#6b7280" },
      pkBadge: { bg: "#fffbeb", text: "#92400e" },
    },
    canvas: { bg: "#f8fafc", grid: "#cbd5e1" },
    menu: { bg: "#ffffff", bgHover: "#f1f5f9", text: "#374151", textActive: "#4338ca", accentBg: "#eef2ff", accentText: "#4338ca", border: "#e2e8f0" },
  },
  {
    id: "minimal",
    name: "Minimal",
    dfd: {
      process: { border: "#18181b", header: "#fafafa", text: "#09090b", accent: "#09090b", lightAccent: "#e4e4e7" },
      store: { border: "#27272a", header: "#fafafa", text: "#09090b", accent: "#09090b", lightAccent: "#e4e4e7" },
      external: { border: "#71717a", header: "#fafafa", text: "#09090b", accent: "#09090b", lightAccent: "#e4e4e7" },
      edge: { stroke: "#d4d4d8", labelBg: "#ffffff", labelText: "#71717a" },
    },
    erd: {
      entity: { border: "#18181b", header: "#fafafa", text: "#09090b", accent: "#09090b" },
      relationship: { stroke: "#18181b", labelBg: "#ffffff", labelText: "#71717a" },
      pkBadge: { bg: "#fafafa", text: "#09090b" },
    },
    canvas: { bg: "#ffffff", grid: "#e4e4e7" },
    menu: { bg: "#ffffff", bgHover: "#f4f4f5", text: "#27272a", textActive: "#09090b", accentBg: "#fafafa", accentText: "#09090b", border: "#e4e4e7" },
  },
  {
    id: "chalkboard",
    name: "Chalkboard",
    dfd: {
      process: { border: "#efe8d5", header: "#1d2b1d", text: "#efe8d5", accent: "#efe8d5", lightAccent: "rgba(239,232,213,0.30)" },
      store: { border: "#efe8d5", header: "#1d2b1d", text: "#efe8d5", accent: "#efe8d5", lightAccent: "rgba(239,232,213,0.30)" },
      external: { border: "#efe8d5", header: "#1d2b1d", text: "#efe8d5", accent: "#efe8d5", lightAccent: "rgba(239,232,213,0.30)" },
      edge: { stroke: "#efe8d5", labelBg: "#1d2b1d", labelText: "#efe8d5" },
    },
    erd: {
      entity: { border: "#efe8d5", header: "#1d2b1d", text: "#efe8d5", accent: "#efe8d5" },
      relationship: { stroke: "#efe8d5", labelBg: "#1d2b1d", labelText: "#efe8d5" },
      pkBadge: { bg: "#1d2b1d", text: "#efe8d5" },
    },
    canvas: { bg: "#253325", grid: "rgba(239,232,213,0.10)" },
    menu: { bg: "#1d2b1d", bgHover: "#253325", text: "#efe8d5", textActive: "#ffffff", accentBg: "#253325", accentText: "#efe8d5", border: "rgba(239,232,213,0.25)" },
  },
];

export function getDiagramTheme(id: DiagramThemeId): DiagramTheme {
  return DIAGRAM_THEMES.find((t) => t.id === id) ?? DIAGRAM_THEMES[0];
}
