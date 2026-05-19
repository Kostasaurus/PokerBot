-- One registration per user per tournament.
-- Run once against the database before deploying the updated model.

DELETE FROM tournaments_registration AS a
    USING tournaments_registration AS b
WHERE a.tg_id = b.tg_id
  AND a.tournament_id = b.tournament_id
  AND a.id > b.id;

ALTER TABLE tournaments_registration
    ADD CONSTRAINT uq_tournament_registration_user UNIQUE (tg_id, tournament_id);
