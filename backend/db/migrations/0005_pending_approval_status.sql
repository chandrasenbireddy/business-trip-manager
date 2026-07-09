-- US4 (spec FR-019): a confirmed itinerary above the tenant's approval
-- threshold pauses before booking executes, distinct from "awaiting_approval"
-- (the traveler's own pre-confirmation itinerary review, a different concept).

ALTER TABLE sessions DROP CONSTRAINT sessions_status_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_status_check
    CHECK (status IN ('in_progress', 'awaiting_approval', 'pending_approval', 'confirmed', 'closed', 'abandoned'));
