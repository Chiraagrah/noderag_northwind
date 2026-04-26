import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Topbar from "./components/layout/Topbar";
import AppShell from "./components/layout/AppShell";
import useGraphStore from "./store/graphStore";

const queryClient = new QueryClient();

function KeyboardShortcuts() {
  const selectNode      = useGraphStore(s => s.selectNode);
  const clearHighlights = useGraphStore(s => s.clearHighlights);

  useEffect(() => {
    const handler = (e) => {
      // / or Ctrl+K — focus query input
      if (e.key === "/" || (e.ctrlKey && e.key === "k")) {
        const input = window.__queryInputRef?.current;
        if (!input) return;
        if (document.activeElement === input) return;
        e.preventDefault();
        input.focus();
        return;
      }

      // Escape — deselect node + clear highlights
      if (e.key === "Escape") {
        selectNode(null);
        clearHighlights();
        return;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectNode, clearHighlights]);

  return null;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <KeyboardShortcuts />
      <Topbar />
      <AppShell />
    </QueryClientProvider>
  );
}
