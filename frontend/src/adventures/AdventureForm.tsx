import { useState } from "react";
import {
  useAdventureQuery,
  usePatchAdventure,
  useApplySpinePreset,
  castHooks,
  rewardHooks,
  encounterHooks,
  pcPressureHooks,
  clockLinkHooks,
} from "../api/adventures";
import { useNPCsQuery, usePCsQuery } from "../api/npcs";
import { useClocksQuery } from "../api/clocks";
import { useThreadsQuery } from "../api/threads";
import GeneratorPanel from "./GeneratorPanel";

interface Props {
  adventureId: number;
  onBack: () => void;
}

const CLUE_MAP_LANES = ["core", "superior", "optional", "false_leads", "back_doors"] as const;

export default function AdventureForm({ adventureId, onBack }: Props) {
  const { data: adventure, isLoading } = useAdventureQuery(adventureId);
  const patchAdventure = usePatchAdventure();
  const applySpinePreset = useApplySpinePreset();
  const createCast = castHooks.useCreate();
  const patchCast = castHooks.usePatch();
  const deleteCast = castHooks.useDelete();
  const createReward = rewardHooks.useCreate();
  const patchReward = rewardHooks.usePatch();
  const deleteReward = rewardHooks.useDelete();
  const createEncounter = encounterHooks.useCreate();
  const patchEncounter = encounterHooks.usePatch();
  const deleteEncounter = encounterHooks.useDelete();
  const createPcPressure = pcPressureHooks.useCreate();
  const patchPcPressure = pcPressureHooks.usePatch();
  const deletePcPressure = pcPressureHooks.useDelete();
  const createClockLink = clockLinkHooks.useCreate();
  const patchClockLink = clockLinkHooks.usePatch();
  const deleteClockLink = clockLinkHooks.useDelete();

  const { data: npcs = [] } = useNPCsQuery();
  const { data: pcs = [] } = usePCsQuery();
  const { data: clocks = [] } = useClocksQuery();
  const { data: threads = [] } = useThreadsQuery();

  const [showGenerator, setShowGenerator] = useState(false);
  const [selectedNpcId, setSelectedNpcId] = useState("");
  const [selectedPcId, setSelectedPcId] = useState("");
  const [linkTargetType, setLinkTargetType] = useState<"clock" | "thread">("clock");
  const [linkTargetId, setLinkTargetId] = useState("");

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
          <thead><tr><th>PC</th><th>Pressure</th><th>Growth</th><th>Cost</th><th /></tr></thead>
          <tbody>
            {adventure.pc_pressure.map((row) => (
              <tr key={row.id}>
                <td>{pcs.find((pc) => pc.id === row.pc_id)?.name ?? row.pc_id}</td>
                <td>
                  <input
                    defaultValue={row.pressure}
                    onBlur={(e) => patchPcPressure.mutate({ adventureId, rowId: row.id, pressure: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.growth}
                    onBlur={(e) => patchPcPressure.mutate({ adventureId, rowId: row.id, growth: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.cost}
                    onBlur={(e) => patchPcPressure.mutate({ adventureId, rowId: row.id, cost: e.target.value })}
                  />
                </td>
                <td>
                  <button onClick={() => deletePcPressure.mutate({ adventureId, rowId: row.id })}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="adventure-form-picker">
          <select value={selectedPcId} onChange={(e) => setSelectedPcId(e.target.value)}>
            <option value="">Select PC…</option>
            {pcs.map((pc) => (
              <option key={pc.id} value={pc.id}>{pc.name}</option>
            ))}
          </select>
          <button
            className="btn-secondary"
            disabled={!selectedPcId}
            onClick={() => {
              createPcPressure.mutate({ adventureId, pc_id: Number(selectedPcId), pressure: "" });
              setSelectedPcId("");
            }}
          >
            Add PC Pressure Row
          </button>
        </div>
      </section>

      <section className="adventure-form-section">
        <h3>Cast</h3>
        <table>
          <thead><tr><th>NPC</th><th>Role</th><th>Wants Now</th><th>Hides</th><th>If Helped</th><th>If Crossed</th><th /></tr></thead>
          <tbody>
            {adventure.cast.map((row) => (
              <tr key={row.id}>
                <td>{npcs.find((npc) => npc.id === row.npc_id)?.name ?? row.npc_id}</td>
                <td>
                  <input
                    defaultValue={row.role}
                    onBlur={(e) => patchCast.mutate({ adventureId, rowId: row.id, role: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.wants_now}
                    onBlur={(e) => patchCast.mutate({ adventureId, rowId: row.id, wants_now: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.hides}
                    onBlur={(e) => patchCast.mutate({ adventureId, rowId: row.id, hides: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.if_helped}
                    onBlur={(e) => patchCast.mutate({ adventureId, rowId: row.id, if_helped: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.if_crossed}
                    onBlur={(e) => patchCast.mutate({ adventureId, rowId: row.id, if_crossed: e.target.value })}
                  />
                </td>
                <td>
                  <button onClick={() => deleteCast.mutate({ adventureId, rowId: row.id })}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="adventure-form-picker">
          <select value={selectedNpcId} onChange={(e) => setSelectedNpcId(e.target.value)}>
            <option value="">Select NPC…</option>
            {npcs.map((npc) => (
              <option key={npc.id} value={npc.id}>{npc.name}</option>
            ))}
          </select>
          <button
            className="btn-secondary"
            disabled={!selectedNpcId}
            onClick={() => {
              createCast.mutate({ adventureId, npc_id: Number(selectedNpcId) });
              setSelectedNpcId("");
            }}
          >
            Add Cast Row
          </button>
        </div>
      </section>

      <section className="adventure-form-section">
        <h3>Clock &amp; Thread Links</h3>
        <table>
          <thead><tr><th>Target</th><th>How It Appears</th><th>Advance Trigger</th><th>Visible Impact</th><th /></tr></thead>
          <tbody>
            {adventure.clock_links.map((row) => {
              const targetLabel = row.clock_id
                ? clocks.find((c) => c.id === row.clock_id)?.name ?? row.clock_id
                : threads.find((t) => t.id === row.thread_id)?.title ?? row.thread_id;
              return (
                <tr key={row.id}>
                  <td>{targetLabel}</td>
                  <td>
                    <input
                      defaultValue={row.how_it_appears}
                      onBlur={(e) => patchClockLink.mutate({ adventureId, rowId: row.id, how_it_appears: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      defaultValue={row.advance_trigger}
                      onBlur={(e) => patchClockLink.mutate({ adventureId, rowId: row.id, advance_trigger: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      defaultValue={row.visible_impact}
                      onBlur={(e) => patchClockLink.mutate({ adventureId, rowId: row.id, visible_impact: e.target.value })}
                    />
                  </td>
                  <td>
                    <button onClick={() => deleteClockLink.mutate({ adventureId, rowId: row.id })}>Remove</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="adventure-form-picker">
          <select
            value={linkTargetType}
            onChange={(e) => {
              setLinkTargetType(e.target.value as "clock" | "thread");
              setLinkTargetId("");
            }}
          >
            <option value="clock">Clock</option>
            <option value="thread">Thread</option>
          </select>
          <select value={linkTargetId} onChange={(e) => setLinkTargetId(e.target.value)}>
            <option value="">Select {linkTargetType}…</option>
            {linkTargetType === "clock"
              ? clocks.map((clock) => (
                  <option key={clock.id} value={clock.id}>{clock.name}</option>
                ))
              : threads.map((thread) => (
                  <option key={thread.id} value={thread.id}>{thread.title}</option>
                ))}
          </select>
          <button
            className="btn-secondary"
            disabled={!linkTargetId}
            onClick={() => {
              createClockLink.mutate(
                linkTargetType === "clock"
                  ? { adventureId, clock_id: linkTargetId }
                  : { adventureId, thread_id: linkTargetId },
              );
              setLinkTargetId("");
            }}
          >
            Add Link
          </button>
        </div>
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
                <td>
                  <input
                    defaultValue={row.name}
                    onBlur={(e) => patchEncounter.mutate({ adventureId, rowId: row.id, name: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.objective}
                    onBlur={(e) => patchEncounter.mutate({ adventureId, rowId: row.id, objective: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.opposition}
                    onBlur={(e) => patchEncounter.mutate({ adventureId, rowId: row.id, opposition: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.terrain_constraint}
                    onBlur={(e) => patchEncounter.mutate({ adventureId, rowId: row.id, terrain_constraint: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.what_changes}
                    onBlur={(e) => patchEncounter.mutate({ adventureId, rowId: row.id, what_changes: e.target.value })}
                  />
                </td>
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
                <td>
                  <input
                    defaultValue={row.name}
                    onBlur={(e) => patchReward.mutate({ adventureId, rowId: row.id, name: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.type}
                    onBlur={(e) => patchReward.mutate({ adventureId, rowId: row.id, type: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.who_cares}
                    onBlur={(e) => patchReward.mutate({ adventureId, rowId: row.id, who_cares: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.mechanical_note}
                    onBlur={(e) => patchReward.mutate({ adventureId, rowId: row.id, mechanical_note: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    defaultValue={row.future_hook}
                    onBlur={(e) => patchReward.mutate({ adventureId, rowId: row.id, future_hook: e.target.value })}
                  />
                </td>
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
        {CLUE_MAP_LANES.map((lane) => (
          <label key={lane}>
            {lane.replace(/_/g, " ")}
            <textarea
              value={((adventure.clue_map[lane] as string[]) || []).join("\n")}
              placeholder="One clue per line"
              onChange={(e) =>
                patchAdventure.mutate({
                  id: adventureId,
                  clue_map: { ...adventure.clue_map, [lane]: e.target.value.split("\n") },
                })
              }
            />
          </label>
        ))}
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
