import type { ReactNode } from "react";

// Line icons drawn on a 20px grid, 1.5px stroke. Owned, no icon package. An app that hosts these
// pages draws its own pages' icons with the same Svg.

export type IconProps = { className?: string };

export function Svg({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className ?? "size-5"}
    >
      {children}
    </svg>
  );
}

export const PeopleIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="7.5" cy="7" r="2.6" />
    <path d="M2.8 16c.6-2.6 2.4-4 4.7-4s4.1 1.4 4.7 4" />
    <circle cx="14" cy="7.8" r="2" />
    <path d="M13.6 12.1c1.8.1 3.1 1.3 3.6 3.4" />
  </Svg>
);

export const CareerIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 16.5h14" />
    <path d="M5 13.5 8.5 9l3 2.5L16 5" />
    <path d="M12.5 5H16v3.5" />
  </Svg>
);
