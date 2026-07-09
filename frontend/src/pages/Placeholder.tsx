export function Placeholder({ title }: { title: string }) {
  return (
    <>
      <header className="page-header">
        <div>
          <h1 className="page-title">{title}</h1>
          <span className="page-subtitle">Not built in this design pass yet</span>
        </div>
      </header>
      <div className="placeholder">
        <h2>{title}</h2>
        <p>
          This screen is next in line for the redesign. The Cockpit is the first fully
          implemented page of the new frontend — everything else routes here for now.
        </p>
      </div>
    </>
  );
}
