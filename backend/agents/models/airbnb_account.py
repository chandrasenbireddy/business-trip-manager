"""AirbnbAccountContext (data-model.md).

Not its own durable table — functionally a cache refreshed at each session
start from the live Airbnb account tool (PRD AR-07), and persisted only
insofar as past stays feed episodic memory and preferences feed Traveler
Preference (both elsewhere). This is just the fetch result's shape.
"""

from dataclasses import dataclass, field


@dataclass
class AirbnbAccountContext:
    user_id: str
    upcoming_reservations: list[dict] = field(default_factory=list)
    past_stays: list[dict] = field(default_factory=list)
    wishlist: list[dict] = field(default_factory=list)
    cookie_status: str = "expired"  # "valid" | "expired" — spec FR-029
    connected: bool = False  # no credential on file at all — distinct from an expired one at the API layer
