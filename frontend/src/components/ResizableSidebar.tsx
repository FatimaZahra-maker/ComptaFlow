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
    // try/catch : certains navigateurs (navigation privée stricte) peuvent
    // lever une exception sur l'accès à localStorage plutôt que renvoyer null.
    try {
      const saved = localStorage.getItem(STORAGE_PREFIX + storageKey);
      const parsed = saved ? Number(saved) : defaultWidth;
      return Number.isFinite(parsed) && parsed > 0 ? parsed : defaultWidth;
    } catch {
      return defaultWidth;
    }
  });
  const [isResizing, setIsResizing] = useState(false);

  // Écoute les mouvements de souris UNIQUEMENT pendant un redimensionnement actif
  // (l'effet se ré-exécute à chaque changement de isResizing).
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

    // Pendant le drag : curseur "resize" partout + désactive la sélection de texte
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    // Nettoyage systématique quand isResizing repasse à false ou au démontage
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, minWidth, maxWidth]);

  // Sauvegarde la largeur choisie à chaque changement, pour la retrouver
  // à la prochaine visite (par clé, donc indépendamment pour chaque sidebar)
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_PREFIX + storageKey, String(width));
    } catch {
      // silencieux -- si localStorage est indisponible, on perd juste la persistance
    }
  }, [width, storageKey]);

  return (
    <div ref={containerRef} style={{ width }} className={`relative shrink-0 ${className}`}>
      <div className="h-full overflow-y-auto">{children}</div>
      {/* Poignée de redimensionnement : fine bande cliquable sur le bord droit */}
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