import { createContext, useContext, type ReactNode } from "react";
import type { DiagramTheme } from "../styles/diagramThemes";
import { getDiagramTheme, type DiagramThemeId } from "../styles/diagramThemes";

interface DiagramThemeContextValue {
  theme: DiagramTheme;
  themeId: DiagramThemeId;
}

const DiagramThemeCtx = createContext<DiagramThemeContextValue>({
  theme: getDiagramTheme("technical"),
  themeId: "technical",
});

export function DiagramThemeProvider({
  themeId,
  children,
}: {
  themeId: DiagramThemeId;
  children: ReactNode;
}) {
  const theme = getDiagramTheme(themeId);
  return (
    <DiagramThemeCtx.Provider value={{ theme, themeId }}>
      {children}
    </DiagramThemeCtx.Provider>
  );
}

export function useDiagramTheme() {
  return useContext(DiagramThemeCtx);
}
