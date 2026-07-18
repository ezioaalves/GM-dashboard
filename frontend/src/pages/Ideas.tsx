import { useState } from "react";
import { useCreateIdea, useIdeasQuery } from "../api/ideas";

export function Ideas() {
  const { data: ideas = [], isLoading } = useIdeasQuery();
  const create = useCreateIdea();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    create.mutate({ title: title.trim(), body }, { onSuccess: () => { setTitle(""); setBody(""); } });
  }
  return <>
    <header className="page-header"><div><h1 className="page-title">Idea Inbox</h1><span className="page-subtitle">Capture now; triage and promote later</span></div></header>
    <section className="panel" style={{ maxWidth: 720 }}>
      <form onSubmit={submit}>
        <input className="text-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Idea title" autoFocus />
        <textarea className="text-input" value={body} onChange={(e) => setBody(e.target.value)} placeholder="Optional detail" rows={3} />
        <button className="btn btn-primary" type="submit" disabled={create.isPending}>Capture idea</button>
      </form>
    </section>
    <section className="column" style={{ maxWidth: 720 }}>
      {isLoading && <div className="empty-state">Loading ideas…</div>}
      {!isLoading && ideas.length === 0 && <div className="empty-state">No ideas captured yet.</div>}
      {ideas.map((idea) => <article className="attention-card" key={idea.id}><div className="attention-card-body"><span className="attention-card-title">{idea.title}</span>{idea.body && <span className="attention-card-detail">{idea.body}</span>}</div><span className="tag-pill">{idea.state}</span></article>)}
    </section>
  </>;
}
