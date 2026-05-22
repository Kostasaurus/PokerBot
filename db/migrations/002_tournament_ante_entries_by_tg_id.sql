-- Migrate from registration_id-based ante table (if 002 was applied earlier).

DROP TABLE IF EXISTS registration_ante_entries;

CREATE TABLE IF NOT EXISTS tournament_ante_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    tg_id BIGINT NOT NULL REFERENCES users_info(tg_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tournament_ante_entries_tournament_tg
    ON tournament_ante_entries (tournament_id, tg_id);
