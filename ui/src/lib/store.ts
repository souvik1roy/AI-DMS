import { create } from "zustand";

interface AppState {
  activeJobId: string | null;
  setActiveJobId: (id: string | null) => void;

  /** Pre-selected document_type filter applied when Browse loads (set by
   * the Dashboard "top types" rows). Cleared by Browse on first read. */
  browseTypeFilter: string | null;
  setBrowseTypeFilter: (type: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeJobId: null,
  setActiveJobId: (activeJobId) => set({ activeJobId }),
  browseTypeFilter: null,
  setBrowseTypeFilter: (browseTypeFilter) => set({ browseTypeFilter }),
}));
