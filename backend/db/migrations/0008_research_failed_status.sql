ALTER TABLE sessions DROP CONSTRAINT sessions_status_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_status_check
    CHECK (
        status IN (
            'in_progress',
            'awaiting_clarification',
            'research_failed',
            'awaiting_approval',
            'pending_approval',
            'confirmed',
            'closed',
            'abandoned'
        )
    );
