"""Adventure layer: adventures, child tables, session links, generator tables

Revision ID: 018
Revises: 017
Create Date: 2026-07-05 00:00:00.000000

"""
from alembic import op


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS adventures (
          id                serial PRIMARY KEY,
          graph_endpoint_id text NOT NULL DEFAULT '',
          title             text NOT NULL DEFAULT '',
          status            text NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'ready', 'played', 'archived')),
          current_arc       text NOT NULL DEFAULT '',
          pitch             text NOT NULL DEFAULT '',
          mode              text NOT NULL DEFAULT '',
          tone_rule         text NOT NULL DEFAULT '',
          safety_flags      text NOT NULL DEFAULT '',
          feel_target       text NOT NULL DEFAULT '',
          feel_avoid        text NOT NULL DEFAULT '',
          stakes            jsonb NOT NULL DEFAULT '{}'::jsonb,
          location          jsonb NOT NULL DEFAULT '{}'::jsonb,
          spine             jsonb NOT NULL DEFAULT '[]'::jsonb,
          clue_map          jsonb NOT NULL DEFAULT '{}'::jsonb,
          foundry_needs     jsonb NOT NULL DEFAULT '{}'::jsonb,
          rules_notes       jsonb NOT NULL DEFAULT '{}'::jsonb,
          source_path       text NOT NULL DEFAULT '',
          source_hash       text NOT NULL DEFAULT '',
          source_mtime      timestamptz,
          visibility        text NOT NULL DEFAULT 'gm',
          freshness_state   text NOT NULL DEFAULT 'unknown',
          review_status     text NOT NULL DEFAULT 'accepted',
          created_at        timestamptz NOT NULL DEFAULT now(),
          updated_at        timestamptz NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_adventures_graph_endpoint_id
          ON adventures(graph_endpoint_id);

        DROP TRIGGER IF EXISTS set_adventures_graph_endpoint_id ON adventures;
        CREATE TRIGGER set_adventures_graph_endpoint_id
        BEFORE INSERT ON adventures
        FOR EACH ROW
        EXECUTE FUNCTION set_graph_endpoint_id('adventure');

        CREATE TABLE IF NOT EXISTS adventure_pc_pressure (
          id           serial PRIMARY KEY,
          adventure_id integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
          pc_id        integer NOT NULL REFERENCES pcs(id),
          pressure     text NOT NULL DEFAULT '',
          growth       text NOT NULL DEFAULT '',
          cost         text NOT NULL DEFAULT '',
          sort_order   integer NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_adventure_pc_pressure_adventure
          ON adventure_pc_pressure(adventure_id, sort_order);

        CREATE TABLE IF NOT EXISTS adventure_rewards (
          id               serial PRIMARY KEY,
          adventure_id     integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
          name             text NOT NULL DEFAULT '',
          type             text NOT NULL DEFAULT '',
          who_cares        text NOT NULL DEFAULT '',
          mechanical_note  text NOT NULL DEFAULT '',
          future_hook      text NOT NULL DEFAULT '',
          sort_order       integer NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_adventure_rewards_adventure
          ON adventure_rewards(adventure_id, sort_order);

        CREATE TABLE IF NOT EXISTS adventure_clock_links (
          id               serial PRIMARY KEY,
          adventure_id     integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
          clock_id         uuid REFERENCES clocks(id) ON DELETE SET NULL,
          thread_id        text REFERENCES threads(id) ON DELETE SET NULL,
          how_it_appears   text NOT NULL DEFAULT '',
          advance_trigger  text NOT NULL DEFAULT '',
          visible_impact   text NOT NULL DEFAULT '',
          CONSTRAINT adventure_clock_links_target_check
            CHECK (clock_id IS NOT NULL OR thread_id IS NOT NULL)
        );
        CREATE INDEX IF NOT EXISTS idx_adventure_clock_links_adventure
          ON adventure_clock_links(adventure_id);

        CREATE TABLE IF NOT EXISTS adventure_encounters (
          id                  serial PRIMARY KEY,
          adventure_id        integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
          name                text NOT NULL DEFAULT '',
          objective           text NOT NULL DEFAULT '',
          opposition          text NOT NULL DEFAULT '',
          terrain_constraint  text NOT NULL DEFAULT '',
          what_changes        text NOT NULL DEFAULT '',
          sort_order          integer NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_adventure_encounters_adventure
          ON adventure_encounters(adventure_id, sort_order);

        CREATE TABLE IF NOT EXISTS adventure_cast (
          id           serial PRIMARY KEY,
          adventure_id integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
          npc_id       integer NOT NULL REFERENCES npcs(id),
          role         text NOT NULL DEFAULT '',
          wants_now    text NOT NULL DEFAULT '',
          hides        text NOT NULL DEFAULT '',
          if_helped    text NOT NULL DEFAULT '',
          if_crossed   text NOT NULL DEFAULT '',
          sort_order   integer NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_adventure_cast_adventure
          ON adventure_cast(adventure_id, sort_order);

        CREATE TABLE IF NOT EXISTS session_adventures (
          session_id   integer NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          adventure_id integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
          PRIMARY KEY (session_id, adventure_id)
        );

        CREATE TABLE IF NOT EXISTS generator_tables (
          id    serial PRIMARY KEY,
          key   text NOT NULL UNIQUE,
          label text NOT NULL,
          die   text NOT NULL
        );

        CREATE TABLE IF NOT EXISTS generator_entries (
          id          serial PRIMARY KEY,
          table_id    integer NOT NULL REFERENCES generator_tables(id) ON DELETE CASCADE,
          roll        integer NOT NULL,
          name        text NOT NULL DEFAULT '',
          description text NOT NULL DEFAULT '',
          sort_order  integer NOT NULL DEFAULT 0,
          UNIQUE (table_id, roll)
        );
        """
    )

    _seed_generator_tables()


def _seed_generator_tables():
    op.execute(
        """
        INSERT INTO generator_tables (key, label, die) VALUES
          ('combat_type', 'Combat Type', 'd8'),
          ('combat_objective', 'Combat Objective', 'd12'),
          ('combat_tricks', 'Combat Tricks', 'd10'),
          ('mode_tag', 'Adventure Mode', 'd10')
        ON CONFLICT (key) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO generator_entries (table_id, roll, name, description, sort_order)
        SELECT t.id, v.roll, v.name, v.description, v.roll
        FROM generator_tables t
        JOIN (VALUES
          (1, 'Skirmish', 'The most common and reliable type of combat. Fun and straightforward, but can become repetitive without clear objectives.'),
          (2, 'Ambush', 'Enemies find the party first, forcing a sudden, unpredictable adaptation.'),
          (3, 'Target Strike', 'The party gets the drop on a powerful foe; makes an otherwise impossible fight feel achievable.'),
          (4, 'Horde of Bad Guys', 'Massive numbers of weak enemies force resource-management decisions.'),
          (5, 'Elite Team', 'Named, powerful villains with unique roles; a bridge between skirmishes and boss battles.'),
          (6, 'Stomping Ground', 'An opportunity for the party to feel powerful and see how far they''ve come.'),
          (7, 'Boss Battle', 'High-stakes climax; maximally difficult, multi-phase.'),
          (8, 'Puzzle', 'Combat that is really a puzzle in disguise — disable a trap or race to an objective under fire.')
        ) AS v(roll, name, description) ON t.key = 'combat_type'
        ON CONFLICT (table_id, roll) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO generator_entries (table_id, roll, name, description, sort_order)
        SELECT t.id, v.roll, v.name, v.description, v.roll
        FROM generator_tables t
        JOIN (VALUES
          (1, 'Deathmatch', 'The fight ends only when one side is defeated.'),
          (2, 'Stop the Ritual', 'Interrupt a ritual before it completes.'),
          (3, 'Daring Escape', 'Navigate through enemies to reach a safe point.'),
          (4, 'Hold the Fort', 'Defend a location for a set number of turns.'),
          (5, 'Waves of Bad Guys', 'Survive increasingly difficult or numerous waves.'),
          (6, 'Save the NPC', 'Protect an NPC the enemy may prioritize attacking.'),
          (7, 'Sabotage', 'Disable an enemy asset to ease a future encounter.'),
          (8, 'Escort the Thing', 'Move a precious or heavy item/NPC to a destination under threat.'),
          (9, 'Base Defense', 'Prevent the enemy from destroying or stealing key assets.'),
          (10, 'Yoink and Skedaddle', 'Steal an item and escape before raising an alarm.'),
          (11, 'Peace Makers', 'Stop a conflict between two hostile sides without becoming combatants.'),
          (12, 'The Arrest', 'Capture an enemy alive rather than killing them.')
        ) AS v(roll, name, description) ON t.key = 'combat_objective'
        ON CONFLICT (table_id, roll) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO generator_entries (table_id, roll, name, description, sort_order)
        SELECT t.id, v.roll, v.name, v.description, v.roll
        FROM generator_tables t
        JOIN (VALUES
          (1, 'Red Barrels', 'Explosive hazards that encourage tactical positioning and area-of-effect combos.'),
          (2, 'Siege Weapons', 'Stationary cannons/ballistae that become a struggle for control.'),
          (3, 'Ammo Boxes', 'Crates with instantly usable loot or magic items.'),
          (4, 'Big Drops', 'Pits or cliffs for verticality and environmental kills.'),
          (5, 'Doors', 'Heavy, interactive doors that require an action, creating choke points.'),
          (6, 'Interactables', 'Levers or generic items that trigger map-wide changes.'),
          (7, 'Terrain', 'Difficult ground or hazards that force navigation choices.'),
          (8, 'Platforms', 'Moving elements that change the battlefield layout.'),
          (9, 'Lair Actions', 'Environmental boss-specific effects that work in synergy with antagonists.'),
          (10, '-', 'No trick this time.')
        ) AS v(roll, name, description) ON t.key = 'combat_tricks'
        ON CONFLICT (table_id, roll) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO generator_entries (table_id, roll, name, description, sort_order)
        SELECT t.id, v.roll, v.name, v.description, v.roll
        FROM generator_tables t
        JOIN (VALUES
          (1, 'Mission', 'Time, orders, terrain, and consequences matter.'),
          (2, 'Training', 'The challenge reveals who the PC is becoming.'),
          (3, 'Investigation', 'Core clues surface; rolls change leverage, speed, and cost.'),
          (4, 'Social/Court', 'Words have witnesses and future prices.'),
          (5, 'City Pressure', 'Violence is constrained by law, rank, clan, and rumor.'),
          (6, 'Underworld Favor', 'Access is useful, but every favor creates ownership pressure.'),
          (7, 'Clan Drama', 'Public identity and private desire collide.'),
          (8, 'Shadowlands Horror', 'Wonder and threat coexist; safety is never assumed.'),
          (9, 'Exam/Tournament', 'Skill matters, but interpretation by observers matters too.'),
          (10, 'Downtime Complication', 'The world moves while PCs optimize.')
        ) AS v(roll, name, description) ON t.key = 'mode_tag'
        ON CONFLICT (table_id, roll) DO NOTHING;
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS generator_entries;
        DROP TABLE IF EXISTS generator_tables;
        DROP TABLE IF EXISTS session_adventures;
        DROP TABLE IF EXISTS adventure_cast;
        DROP TABLE IF EXISTS adventure_encounters;
        DROP TABLE IF EXISTS adventure_clock_links;
        DROP TABLE IF EXISTS adventure_rewards;
        DROP TABLE IF EXISTS adventure_pc_pressure;
        DROP TABLE IF EXISTS adventures;
        """
    )
