import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { DiagramThemeId } from "../styles/diagramThemes";

export type AppThemeId = "technical" | "minimal" | "chalkboard" | "gridly";

interface AppTheme {
  id: AppThemeId;
  diagramThemeId: DiagramThemeId;
}

interface ThemeContextValue {
  theme: AppTheme;
  setTheme: (id: AppThemeId) => void;
  diagramThemeId: DiagramThemeId;
}

const APP_THEMES: AppTheme[] = [
  { id: "technical",  diagramThemeId: "technical" },
  { id: "minimal",    diagramThemeId: "minimal" },
  { id: "chalkboard", diagramThemeId: "chalkboard" },
  { id: "gridly",     diagramThemeId: "chalkboard" },
];

const ThemeCtx = createContext<ThemeContextValue>({
  theme: APP_THEMES[0],
  setTheme: () => {},
  diagramThemeId: "technical",
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Always start at chalkboard for the pitch demo; localStorage is ignored on load.
  const [theme, setThemeState] = useState<AppTheme>(APP_THEMES[2]);

  const setTheme = useCallback((id: AppThemeId) => {
    const next = APP_THEMES.find((t) => t.id === id);
    if (!next) return;
    setThemeState(next);
    try { localStorage.setItem("dfdmaker:theme", id); } catch {}
  }, []);

  return (
    <ThemeCtx.Provider value={{ theme, setTheme, diagramThemeId: theme.diagramThemeId }}>
      {children}
    </ThemeCtx.Provider>
  );
}

export function useAppTheme() {
  return useContext(ThemeCtx);
}

export { APP_THEMES };
export { DiagramThemeProvider, useDiagramTheme } from "./DiagramThemeContext";
