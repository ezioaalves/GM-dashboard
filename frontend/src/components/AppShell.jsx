export function AppShell({ sidebar, children }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">{sidebar}</aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
