export interface Thread {
  id: string;
  title: string;
  status: "active" | "dormant" | "resolved" | "introduced";
  arc: string | null;
  next_move: string | null;
  clock_label: string | null;
  clock_value: number | null;
  clock_max: number | null;
  factions: string[];
  sessions: number[];
  vault_path: string | null;
  body: string | null;
}

export interface ThreadCreate {
  id: string;
  title: string;
  status: Thread["status"];
  arc?: string;
  next_move?: string;
  clock_label?: string;
  clock_value?: number;
  clock_max?: number;
  factions?: string[];
  sessions?: number[];
  body?: string;
}

export type ThreadUpdate = Partial<Omit<ThreadCreate, "id">>;
