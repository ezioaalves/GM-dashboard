import { useState } from "react";
import { useGeneratorTablesQuery, useRollGeneratorTable, usePatchGeneratorEntry } from "../api/generator";

interface Props {
  onCopyToEncounter?: (entry: { name: string; description: string }) => void;
}

export default function GeneratorPanel({ onCopyToEncounter }: Props) {
  const { data: tables = [] } = useGeneratorTablesQuery();
  const roll = useRollGeneratorTable();
  const patchEntry = usePatchGeneratorEntry();
  const [selectedKey, setSelectedKey] = useState<string>("combat_type");
  const [editingRoll, setEditingRoll] = useState<number | null>(null);

  const table = tables.find((t) => t.key === selectedKey);
  const result = roll.data;

  return (
    <div className="generator-panel">
      <div className="generator-panel-controls">
        <select value={selectedKey} onChange={(e) => setSelectedKey(e.target.value)}>
          {tables.map((t) => (
            <option key={t.key} value={t.key}>{t.label} ({t.die})</option>
          ))}
        </select>
        <button className="btn-secondary" onClick={() => roll.mutate(selectedKey)}>Roll</button>
      </div>

      {result && (
        <div className="generator-panel-result">
          <strong>{result.name}</strong>
          <p>{result.description}</p>
          {onCopyToEncounter && (
            <button className="btn-secondary" onClick={() => onCopyToEncounter(result)}>
              Copy into Encounters row
            </button>
          )}
        </div>
      )}

      {table && (
        <table className="generator-panel-entries">
          <tbody>
            {table.entries.map((entry) => (
              <tr key={entry.roll}>
                <td>{entry.roll}</td>
                {editingRoll === entry.roll ? (
                  <td>
                    <input
                      defaultValue={entry.name}
                      onBlur={(e) => {
                        patchEntry.mutate({ key: selectedKey, roll: entry.roll, name: e.target.value });
                        setEditingRoll(null);
                      }}
                      autoFocus
                    />
                  </td>
                ) : (
                  <td onClick={() => setEditingRoll(entry.roll)}>{entry.name}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
