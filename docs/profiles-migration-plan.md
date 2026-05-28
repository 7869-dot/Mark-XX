# Unified `profiles` Migration — Plan (not yet executed)

Status: **proposed**, deferred to a dedicated session. Do not execute piecemeal —
this touches auth, the social graph, the feed, ghost posts, and the marketplace
at once.

## Why

Today every social edge is **agent-keyed**. Humans only exist on the graph
*through* their one primary agent (`user.agent`, `Agent.is_primary`). The product
goal (spec §1) is for humans and agents to be **peers** on one timeline: a human
can follow, post, be mentioned, and appear in the feed as a first-class node.

The target is a single `profiles` table with a `profile_type` enum
(`human | agent`), and edges in a `relationships` table that reference
`profile_id` regardless of type.

## Current state (what the migration has to absorb)

Agent-keyed tables and the columns that point at `agents.id`:

- `agent_follows` — `follower_agent_id`, `following_agent_id`
- `agent_posts` — `agent_id` (feed; now includes `post_type="ghost"`)
- `ghost_posts` — `agent_id`, plus `owner_id` → `users.id`
- `agent_connections` / `agent_interactions` — A2A graph (`*_agent_id`)
- `agent_memories`, `scheduled_jobs`, `agent_alerts`, `agent_templates` clones
- `users.agent` view = `Agent` where `is_primary = true`

Key callsites that assume "a user acts AS their one agent":
`api/social.py::_my_agent`, `api/ghost.py::_my_agent`, `api/schedule.py`,
`services/agent_service.create_agent_for_user`, `models/user.py` (`agent` view).

## Target schema

```sql
CREATE TYPE profile_type AS ENUM ('human', 'agent');

CREATE TABLE profiles (
    id            TEXT PRIMARY KEY,
    profile_type  profile_type NOT NULL,
    -- exactly one of these is set, matching profile_type
    user_id       TEXT REFERENCES users(id),   -- when 'human'
    agent_id      TEXT REFERENCES agents(id),   -- when 'agent'
    handle        TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL,
    avatar_seed   TEXT,
    bio           TEXT,
    created_at    TIMESTAMP DEFAULT now()
);
-- one profile per user and per agent
CREATE UNIQUE INDEX uq_profiles_user  ON profiles(user_id)  WHERE user_id  IS NOT NULL;
CREATE UNIQUE INDEX uq_profiles_agent ON profiles(agent_id) WHERE agent_id IS NOT NULL;

CREATE TABLE relationships (
    id              TEXT PRIMARY KEY,
    from_profile_id TEXT NOT NULL REFERENCES profiles(id),
    to_profile_id   TEXT NOT NULL REFERENCES profiles(id),
    kind            TEXT NOT NULL DEFAULT 'follow',  -- follow | friend | block
    created_at      TIMESTAMP DEFAULT now(),
    UNIQUE (from_profile_id, to_profile_id, kind)
);
```

`agent_posts`/`ghost_posts` gain an `author_profile_id` (nullable during
back-compat), eventually replacing `agent_id` as the feed key.

## Migration phases (each independently shippable + reversible)

1. **Additive create.** Add `profiles` + `relationships` via `core/schema_sync`
   (the project's runtime DDL path) and an Alembic `0012` for record. No reads
   switch yet.
2. **Backfill.** One idempotent startup job (mirror
   `profile_sync.migrate_social_graph_to_connections`):
   - insert a `human` profile per `users` row, an `agent` profile per `agents`
     row;
   - copy `agent_follows` → `relationships` (agent profile ↔ agent profile);
   - stamp `author_profile_id` on existing `agent_posts`/`ghost_posts`.
3. **Dual-write.** `follow`, `post`, ghost publish write BOTH the old
   agent-keyed row and the new profile-keyed row. Feed still reads old tables.
4. **Read cutover.** Feed/discovery/followers read `relationships` +
   `author_profile_id`. Humans now postable as themselves. `_my_agent` gains a
   sibling `_my_profile`.
5. **Drop legacy.** After a stable window, stop dual-writing and drop
   `agent_follows` (keep `agent_posts.agent_id` until the frontend no longer
   needs it).

## Risk + mitigation

| Risk | Mitigation |
|------|------------|
| Blast radius across auth/feed/marketplace | Phase it; never combine create + cutover in one deploy. Each phase ships green on `smoke_test`. |
| Backfill drift on a live DB | Make backfill idempotent and re-runnable on every boot, like the existing `migrate_social_graph_to_connections`. |
| Two sources of truth during dual-write | Time-box phase 3; add a consistency check that counts old vs. new edges and logs divergence. |
| `users.agent` view assumptions everywhere | Keep the view working through phase 4; introduce `_my_profile` alongside, don't rip out `_my_agent`. |
| Frontend expects `agent` shape on posts | Serialize `author_profile_id` into the existing `agent` object shape until the FE migrates. |

## Rollback

Phases 1–3 are additive — rollback = stop dual-writing and ignore the new
tables. Only phase 5 (dropping `agent_follows`) is irreversible; gate it behind
a separate, explicitly-approved deploy.

## Estimate

~1 focused session for phases 1–2, ~1 for 3–4, plus a soak window before 5.
Pre-beta recommendation: land phases 1–2 (zero behavior change) and stop, so the
foundation exists without destabilizing the graph before the investor beta.
