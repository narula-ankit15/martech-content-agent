from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UsageSummary(BaseModel):
    """Reflects requests this app itself made to Gemini, not a live pull
    from Google -- the Gemini API has no endpoint that exposes your
    account's actual quota/usage, so `daily_cap` is a number you supply
    yourself (see PUT /usage/cap) rather than something fetched.
    """

    requests_today: int
    rate_limited_today: bool
    daily_cap: Optional[int] = None
    remaining_today: Optional[int] = None
    requests_by_purpose: dict[str, int]
    last_request_at: Optional[datetime] = None
