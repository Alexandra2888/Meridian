"use client";

import { create } from "zustand";

/**
 * Mobile sidebar open/closed state. Shared between the hamburger toggle in
 * the header and the sidebar drawer so they don't need a common parent —
 * keeps `app/page.tsx` a server component.
 */
interface SidebarStore {
  mobileOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

export const useSidebarStore = create<SidebarStore>((set) => ({
  mobileOpen: false,
  open: () => set({ mobileOpen: true }),
  close: () => set({ mobileOpen: false }),
  toggle: () => set((s) => ({ mobileOpen: !s.mobileOpen })),
}));
