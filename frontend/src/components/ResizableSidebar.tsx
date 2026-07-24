import { useState, useRef, useEffect, type ReactNode } from "react";

interface ResizableSidebarProps {
  children: ReactNode;
  storageKey: string;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  className?: string;
}

const STORAGE_PREFIX = "comptaflow_sidebar_width_";

// Sidebar générique dont la largeur se règle en glissant une poignée
// sur son bord droit, et se souvient de la valeur choisie (par clé,
// localStorage) -- utilisée pour la sidebar principale du Layout ET
// pour la colonne de filtres de ChronosPage.
export function ResizableSidebar({
  children,
  storageKey,
  defaultWidth = 240,
  minWidth = 160,
  maxWidth = 480,
  className = "",
}: ResizableSidebarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState<number>(() => {
    const saved = localStorage.getItem(STORAGE_PREFIX + storageKey);
    const parsed = saved ? Number(saved) : defaultWidth;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : defaultWidth;
  });
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    if (!isResizing) return;

    function handleMouseMove(e: MouseEvent) {
      if (!containerRef.current) return;
      const left = containerRef.current.getBoundingClientRect().left;
      const newWidth = Math.min(maxWidth, Math.max(minWidth, e.clientX - left));
      setWidth(newWidth);
    }
    function handleMouseUp() {
      setIsResizing(false);
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, minWidth, maxWidth]);

  useEffect(() => {
    localStorage.setItem(STORAGE_PREFIX + storageKey, String(width));
  }, [width, storageKey]);

  return (
    <div ref={containerRef} style={{ width }} className={`relative shrink-0 ${className}`}>
      <div className="h-full overflow-y-auto">{children}</div>
      <div
        onMouseDown={() => setIsResizing(true)}
        className={`absolute top-0 right-0 h-full w-1.5 cursor-col-resize hover:bg-green-400/40 z-10 ${
          isResizing ? "bg-green-500/50" : ""
        }`}
        title="Glisser pour redimensionner"
      />
    </div>
  );
}