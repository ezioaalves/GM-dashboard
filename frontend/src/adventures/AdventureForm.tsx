import { useState } from "react";
import {
  useAdventureQuery,
  usePatchAdventure,
  useApplySpinePreset,
  castHooks,
  rewardHooks,
  encounterHooks,
  pcPressureHooks,
} from "../api/adventures";
import GeneratorPanel from "./GeneratorPanel";

interface Props {
  adventureId: number;
  onBack: () => void;
}

export default function AdventureForm({ adventureId, onBack }: Props) {
  const { data: adventure, isLoading } = useAdventureQuery(adventureId);
  const patchAdventure = usePatchAdventure();
  const applySpinePreset = useApplySpinePreset();
  const createCast = castHooks.useCreate();
  const deleteCast = castHooks.useDelete();
  const createReward = rewardHooks.useCreate();
  const deleteReward = rewardHooks.useDelete();
  const createEncounter = encounterHooks.useCreate();
  const deleteEncounter = encounterHooks.useDelete();
  const createPcPressure = pcPressureHooks.useCreate();
  const deletePcPressure = pcPressureHooks.useDelete();

  const [showGenerator, setShowGenerator] = useState(false);

  if (isLoading || !adventure) {
    return <p>Loading adventure…</p>;
  }

  return (
    <div className="adventure-form">
      <button className="btn-secondary" onClick={onBack}>Back to Adventure Deck</button>

      <section className="adventure-form-header">
        <input
          className="adventure-title-input"
          value={adventure.title}
          onChange={(e) => patchAdventure.mutate({ id: adventureId, title: e.target.value })}
          placeholder="Adventure title"
        />
        <select
          value={adventure.status}
          onChange={(e) => patchAdventure.mutate({ id: adventureId, status: e.target.value as typeof adventure.status })}
        >
          <option value="draft">Draft</option>
          <option value="ready">Ready</option>
          <option value="played">Played</option>
          <option value="archived">Archived</option>
        </select>
        <textarea
          value={adventure.pitch}
          onChange={(e) => patchAdventure.mutate({ id: adventureId, pitch: e.target.value })}
          placeholder="The 13th Tanto must ___ before ___, but ___ makes the obvious solution costly."
        />
        <input
          value={adventure.mode}
          onChange={(e) => patchAdventure.mutate({ id: adventureId, mode: e.target.value })}
          placeholder="Mode (mission, investigation, social/court, ...)"
        />
        <input
          value={adventure.tone_rule}
          onChange={(e) => patchAdventure.mutate({ id: adventureId, tone_rule: e.target.value })}
          placeholder="Tone rule"
        />
      </section>

      <section className="adventure-form-section">
        <h3>Stakes</h3>
        {(["immediate", "personal", "village", "if_ignore", "if_fail", "if_succeed"] as const).map((field) => (
          <label key={field}>
            {field.replace(/_/g, " ")}
            <textarea
              value={(adventure.stakes[field] as string) || ""}
              onChange={(e) =>
                patchAdventure.mutate({ id: adventureId, stakes: { ...adventure.stakes, [field]: e.target.value } })
              }
            />
          </label>
        ))}
      </section>

      <section className="adventure-form-section">
        <h3>PC Lane Pressure</h3>
        <table>
          <thead><tr><th>PC ID</th><th>Pressure</th><th>Growth</th><th>Cost</th><th /></tr></thead>
          <tbody>
            {adventure.pc_pressure.map((row) => (
              <tr key={row.id}>
                <td>{row.pc_id}</td>
                <td>{row.pressure}</td>
                <td>{row.growth}</td>
                <td>{row.cost}</td>
                <td>
                  <button onClick={() => deletePcPressure.mutate({ adventureId, rowId: row.id })}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          className="btn-secondary"
          onClick={() => createPcPressure.mutate({ adventureId, pc_id: 0, pressure: "" })}
        >
          Add PC Pressure Row
        </button>
      </section>

      <section className="adventure-form-section">
        <h3>Cast</h3>
        <table>
          <thead><tr><th>NPC ID</th><th>Role</th><th>Wants Now</th><th>Hides</th><th>If Helped</th><th>If Crossed</th><th /></tr></thead>
          <tbody>
            {adventure.cast.map((row) => (
              <tr key={row.id}>
                <td>{row.npc_id}</td>
                <td>{row.role}</td>
                <td>{row.wants_now}</td>
                <td>{row.hides}</td>
                <td>{row.if_helped}</td>
                <td>{row.if_crossed}</td>
                <td>
                  <button onClick={() => deleteCast.mutate({ adventureId, rowId: row.id })}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button className="btn-secondary" onClick={() => createCast.mutate({ adventureId, npc_id: 0 })}>
          Add Cast Row
        </button>
      </section>

      <section className="adventure-form-section">
        <h3>Location</h3>
        {(
          ["core_activity", "public_authority", "private_authority", "recurring_local",
            "current_dispute", "locals_fear", "locals_gossip", "useful_service", "hidden_pressure"] as const
        ).map((field) => (
          <label key={field}>
            {field.replace(/_/g, " ")}
            <input
              value={(adventure.location[field] as string) || ""}
              onChange={(e) =>
                patchAdventure.mutate({ id: adventureId, location: { ...adventure.location, [field]: e.target.value } })
              }
            />
          </label>
        ))}
      </section>

      <section className="adventure-form-section">
        <h3>Spine</h3>
        <div className="spine-preset-buttons">
          <button className="btn-secondary" onClick={() => applySpinePreset.mutate({ id: adventureId, preset: "six_beat" })}>
            Apply 6-Beat Spine
          </button>
          <button className="btn-secondary" onClick={() => applySpinePreset.mutate({ id: adventureId, preset: "five_room" })}>
            Apply 5-Room Dungeon
          </button>
        </div>
        {adventure.spine.map((beat, idx) => (
          <label key={idx}>
            {beat.label}
            <textarea
              value={beat.text}
              onChange={(e) => {
                const nextSpine = adventure.spine.map((b, i) => (i === idx ? { ...b, text: e.target.value } : b));
                patchAdventure.mutate({ id: adventureId, spine: nextSpine });
              }}
            />
          </label>
        ))}
      </section>

      <section className="adventure-form-section">
        <h3>Encounters</h3>
        <table>
          <thead><tr><th>Name</th><th>Objective</th><th>Opposition</th><th>Terrain</th><th>What Changes</th><th /></tr></thead>
          <tbody>
            {adventure.encounters.map((row) => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td>{row.objective}</td>
                <td>{row.opposition}</td>
                <td>{row.terrain_constraint}</td>
                <td>{row.what_changes}</td>
                <td>
                  <button onClick={() => deleteEncounter.mutate({ adventureId, rowId: row.id })}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button className="btn-secondary" onClick={() => createEncounter.mutate({ adventureId, name: "New Encounter" })}>
          Add Encounter
        </button>
        <button className="btn-secondary" onClick={() => setShowGenerator((v) => !v)}>
          {showGenerator ? "Hide Generator" : "Roll from Generator"}
        </button>
        {showGenerator && (
          <GeneratorPanel
            onCopyToEncounter={(entry) =>
              createEncounter.mutate({ adventureId, name: entry.name, what_changes: entry.description })
            }
          />
        )}
      </section>

      <section className="adventure-form-section">
        <h3>Rewards And Costs</h3>
        <table>
          <thead><tr><th>Name</th><th>Type</th><th>Who Cares</th><th>Note</th><th>Future Hook</th><th /></tr></thead>
          <tbody>
            {adventure.rewards.map((row) => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td>{row.type}</td>
                <td>{row.who_cares}</td>
                <td>{row.mechanical_note}</td>
                <td>{row.future_hook}</td>
                <td>
                  <button onClick={() => deleteReward.mutate({ adventureId, rowId: row.id })}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button className="btn-secondary" onClick={() => createReward.mutate({ adventureId, name: "New Reward" })}>
          Add Reward
        </button>
      </section>

      <section className="adventure-form-section">
        <h3>Clue Map</h3>
        <label>
          Question
          <textarea
            value={(adventure.clue_map.question as string) || ""}
            onChange={(e) =>
              patchAdventure.mutate({ id: adventureId, clue_map: { ...adventure.clue_map, question: e.target.value } })
            }
          />
        </label>
      </section>

      <details className="adventure-form-collapsible">
        <summary>Foundry Needs</summary>
        {(["scene_map", "actors", "items", "journal_entries", "handouts", "music", "automation_checks"] as const).map(
          (field) => (
            <label key={field}>
              {field.replace(/_/g, " ")}
              <input
                value={(adventure.foundry_needs[field] as string) || ""}
                onChange={(e) =>
                  patchAdventure.mutate({
                    id: adventureId,
                    foundry_needs: { ...adventure.foundry_needs, [field]: e.target.value },
                  })
                }
              />
            </label>
          ),
        )}
      </details>

      <details className="adventure-form-collapsible">
        <summary>Rules Notes</summary>
        {(["likely_rules", "house_rules", "rulings_to_prepare", "mechanics_files"] as const).map((field) => (
          <label key={field}>
            {field.replace(/_/g, " ")}
            <textarea
              value={(adventure.rules_notes[field] as string) || ""}
              onChange={(e) =>
                patchAdventure.mutate({
                  id: adventureId,
                  rules_notes: { ...adventure.rules_notes, [field]: e.target.value },
                })
              }
            />
          </label>
        ))}
      </details>

      <section className="adventure-form-section">
        <h3>Sessions</h3>
        <ul>
          {adventure.sessions.map((s) => (
            <li key={s.id}>{s.title}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
