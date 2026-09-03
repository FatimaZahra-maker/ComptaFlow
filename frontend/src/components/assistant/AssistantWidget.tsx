import { useEffect, useRef, useState, type PointerEvent } from "react";
import { Bot, Minus } from "lucide-react";
import { useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { AssistantConversation } from "./AssistantConversation";
import {
  ASSISTANT_DRAG_THRESHOLD,
  assistantPositionStorageKey,
  clampAssistantPosition,
  type AssistantPosition,
} from "./assistantWidgetPosition";

function defaultPosition(): AssistantPosition {
  return clampAssistantPosition(
    { x: window.innerWidth - 88, y: window.innerHeight - 128 },
    window.innerWidth,
    window.innerHeight,
  );
}

export function AssistantWidget() {
  const { user } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<AssistantPosition>(defaultPosition);
  const drag = useRef<{ startX: number; startY: number; origin: AssistantPosition; moved: boolean } | null>(null);
  const suppressClick = useRef(false);

  useEffect(() => {
    if (!user) return;
    try {
      const saved = localStorage.getItem(assistantPositionStorageKey(user.id));
      if (!saved) { setPosition(defaultPosition()); return; }
      const parsed = JSON.parse(saved) as Partial<AssistantPosition>;
      if (typeof parsed.x !== "number" || typeof parsed.y !== "number") throw new Error("position invalide");
      setPosition(clampAssistantPosition({ x: parsed.x, y: parsed.y }, window.innerWidth, window.innerHeight));
    } catch {
      setPosition(defaultPosition());
    }
  }, [user]);

  useEffect(() => {
    function resize() {
      setPosition((current) => clampAssistantPosition(current, window.innerWidth, window.innerHeight));
    }
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  if (!user || location.pathname === "/assistant" || location.pathname === "/login") return null;

  function pointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { startX: event.clientX, startY: event.clientY, origin: position, moved: false };
  }

  function pointerMove(event: PointerEvent<HTMLButtonElement>) {
    if (!drag.current) return;
    const dx = event.clientX - drag.current.startX;
    const dy = event.clientY - drag.current.startY;
    if (Math.hypot(dx, dy) >= ASSISTANT_DRAG_THRESHOLD) drag.current.moved = true;
    if (!drag.current.moved) return;
    setPosition(clampAssistantPosition({
      x: drag.current.origin.x + dx,
      y: drag.current.origin.y + dy,
    }, window.innerWidth, window.innerHeight));
  }

  function pointerUp(event: PointerEvent<HTMLButtonElement>) {
    if (!drag.current) return;
    suppressClick.current = drag.current.moved;
    drag.current = null;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    if (suppressClick.current) {
      setPosition((current) => {
        const safe = clampAssistantPosition(current, window.innerWidth, window.innerHeight);
        if (user) localStorage.setItem(assistantPositionStorageKey(user.id), JSON.stringify(safe));
        return safe;
      });
    }
  }

  function click() {
    if (suppressClick.current) { suppressClick.current = false; return; }
    setOpen((current) => !current);
  }

  return <>
    {open && <aside role="dialog" aria-label="Assistant ComptaFlow" data-testid="assistant-widget-panel" className="fixed inset-x-2 bottom-2 top-2 z-[9998] flex flex-col overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-2xl sm:inset-auto sm:bottom-5 sm:right-5 sm:top-auto sm:h-[min(720px,calc(100vh-40px))] sm:w-[420px]">
      <header className="flex items-center justify-between bg-emerald-800 px-4 py-3 text-white"><div className="flex items-center gap-2"><Bot size={19} /><h2 className="font-bold">Assistant ComptaFlow</h2></div><button type="button" onClick={() => setOpen(false)} aria-label="Réduire l'Assistant" className="rounded-lg p-1.5 hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"><Minus size={19} /></button></header>
      <AssistantConversation mode="widget" />
    </aside>}
    <button
      type="button"
      data-testid="assistant-floating-button"
      aria-label="Ouvrir l'Assistant ComptaFlow"
      title="Ouvrir l'Assistant ComptaFlow"
      onPointerDown={pointerDown}
      onPointerMove={pointerMove}
      onPointerUp={pointerUp}
      onPointerCancel={() => { drag.current = null; }}
      onClick={click}
      style={{ left: position.x, top: position.y }}
      className="fixed z-[9999] flex h-14 w-14 touch-none items-center justify-center rounded-full bg-emerald-700 text-white shadow-xl ring-4 ring-white/80 transition-shadow hover:bg-emerald-800 hover:shadow-2xl focus-visible:outline focus-visible:outline-4 focus-visible:outline-emerald-300"
    ><Bot size={25} /></button>
  </>;
}
