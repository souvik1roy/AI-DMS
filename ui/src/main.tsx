import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";

import App from "./App";
import { Toaster } from "./components/Toaster";
import { persister, shouldDehydrateQuery } from "./lib/query-persister";
import { ThemeProvider } from "./lib/theme";
import "./styles/globals.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30 * 1000,
      gcTime: 1000 * 60 * 60 * 24 * 14, // 14 days
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{
          persister,
          maxAge: 1000 * 60 * 60 * 24 * 14,
          buster: "v1",
          dehydrateOptions: { shouldDehydrateQuery },
        }}
      >
        <App />
        <Toaster />
      </PersistQueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>
);
