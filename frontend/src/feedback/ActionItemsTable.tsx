import { useState } from "react";
import { useCreateActionItem, useDeleteActionItem, usePatchActionItem } from "../api/feedback";
import type { ActionItemStatus, FeedbackActionItem } from "../types/feedback";

export default function ActionItemsTable({ entryId, items }: { entryId: number; items: FeedbackActionItem[] }) {
  const [item, setItem] = useState("");
  const [owner, setOwner] = useState("");
  const [followUp, setFollowUp] = useState("");
  const create = useCreateActionItem();
  const patch = usePatchActionItem();
  const del = useDeleteActionItem();

  async function addItem() {
    if (!item) return;
    await create.mutateAsync({ entryId, item, owner, follow_up: followUp });
    setItem("");
    setOwner("");
    setFollowUp("");
  }

  function cycleStatus(current: ActionItemStatus): ActionItemStatus {
    return current === "open" ? "done" : current === "done" ? "dropped" : "open";
  }

  return (
    <div className="action-items-table">
      <h4>Action Items</h4>
      <table>
        <thead>
          <tr><th>Item</th><th>Owner</th><th>Follow-up</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id}>
              <td>{row.item}</td>
              <td>{row.owner}</td>
              <td>{row.follow_up}</td>
              <td>
                <button onClick={() => patch.mutate({ entryId, itemId: row.id, status: cycleStatus(row.status) })}>
                  {row.status}
                </button>
              </td>
              <td>
                <button onClick={() => del.mutate({ entryId, itemId: row.id })}>Remove</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="action-item-add">
        <input placeholder="Item" value={item} onChange={(e) => setItem(e.target.value)} />
        <input placeholder="Owner" value={owner} onChange={(e) => setOwner(e.target.value)} />
        <input placeholder="Follow-up" value={followUp} onChange={(e) => setFollowUp(e.target.value)} />
        <button onClick={addItem} disabled={!item || create.isPending}>Add</button>
      </div>
    </div>
  );
}
