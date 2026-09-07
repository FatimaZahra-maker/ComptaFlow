import type { ComponentPropsWithoutRef } from "react";

type BrandMarkProps = ComponentPropsWithoutRef<"svg">;

export function BrandMark({ className, ...props }: BrandMarkProps) {
  return (
    <svg className={className} viewBox="0 0 72 58" fill="none" aria-hidden="true" focusable="false" {...props}>
      <defs>
        <linearGradient id="comptaflow-cf-orange" x1="8" y1="7" x2="59" y2="52" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FF9A4A" />
          <stop offset="1" stopColor="#F97316" />
        </linearGradient>
      </defs>
      <path d="M52 7H30C17 7 8 16 8 29s9 22 22 22h12V39H30c-6 0-10-4-10-10s4-10 10-10h16z" fill="url(#comptaflow-cf-orange)" />
      <path d="M31 25h30l-6 11H43v16H31z" fill="url(#comptaflow-cf-orange)" />
    </svg>
  );
}
