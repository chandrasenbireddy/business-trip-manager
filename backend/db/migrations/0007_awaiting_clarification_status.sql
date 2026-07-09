-- Fix: trip intake flow (missing origin/departure city) — a session pauses
-- here between creation and research dispatch when origin is absent from
-- the request and no home_city preference is on file yet. Distinct from
-- awaiting_approval (traveler reviewing a built itinerary) and
-- pending_approval (org-policy threshold pause before booking) — this one
-- is about missing input, not a decision point.

ALTER TABLE sessions DROP CONSTRAINT sessions_status_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_status_check
    CHECK (status IN ('in_progress', 'awaiting_clarification', 'awaiting_approval', 'pending_approval', 'confirmed', 'closed', 'abandoned'));

-- home_city (agents/models/memory.py's PREFERENCE_TYPES) needs the matching
-- DB-level CHECK too — found the hard way when store_preference's real
-- INSERT hit CheckViolationError despite the Python-level tuple already
-- allowing it; the two lists aren't derived from each other.
ALTER TABLE semantic_memories DROP CONSTRAINT semantic_memories_type_check;
ALTER TABLE semantic_memories ADD CONSTRAINT semantic_memories_type_check
    CHECK (type IN ('seat', 'hotel_proximity', 'dietary', 'preferred_airline', 'budget_pattern', 'home_city'));
