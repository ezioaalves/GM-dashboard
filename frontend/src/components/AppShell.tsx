import type { ReactNode } from "react";

export function AppShell({ sidebar, children }: { sidebar: ReactNode; children: ReactNode }) {
  return (
    <div className="shell">
      {sidebar}
      <main className="main">{children}</main>
    </div>
  );
}
