import { Toaster as SonnerToaster } from "sonner";

import { useTheme } from "@/lib/theme";

/**
 * Branded wrapper around sonner. We feed it our `data-theme` value so the
 * default sonner palette flips along with the rest of the app.
 */
export function Toaster() {
  const { resolved } = useTheme();
  return (
    <SonnerToaster
      theme={resolved}
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast:
            "!rounded-card !border !border-border !bg-surface !text-ink-1 !shadow-elev-2 !font-sans",
          title: "!text-ink-1",
          description: "!text-ink-2",
          actionButton:
            "!rounded-md !bg-accent !text-white !text-[12px] !font-medium",
          cancelButton:
            "!rounded-md !bg-sunken !text-ink-2 !text-[12px] !font-medium",
        },
      }}
    />
  );
}
