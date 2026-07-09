-- US2 (spec FR-007/FR-008/FR-008a): tracks how many shown-and-rejectable
-- batches a category has had, to enforce the 3-attempt reject cap.
-- Zero-result silent broadened retries (FR-008a) never create a batch here —
-- they happen before a batch is persisted, so they don't consume the cap.

ALTER TABLE research_options ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 1;
