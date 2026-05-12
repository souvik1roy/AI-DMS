import { createContext, useContext, useEffect, type ReactNode } from "react";

/**
 * Theme system is intentionally light-only. We keep the provider + hook
 * so call-sites compile, but `theme` and `resolved` are fixed to "light".
 * Toggling is a no-op.
 */

export type ThemeChoice = "light";
export type Resolved = "light";

interface ThemeCtx {
  theme: ThemeChoice;
  resolved: Resolved;
  setTheme: (t: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeCtx>({
  theme: "light",
  resolved: "light",
  setTheme: () => undefined,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.setAttribute("data-theme", "light");
    document.documentElement.style.colorScheme = "light";
  }, []);
  return (
    <ThemeContext.Provider value={{ theme: "light", resolved: "light", setTheme: () => undefined }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeCtx {
  return useContext(ThemeContext);
}
