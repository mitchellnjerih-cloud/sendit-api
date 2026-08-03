from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class Webhook(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    webhook_url: str

    event_type: str
    # document.enriched
    # document.uploaded

    is_active: bool = Field(
        default=True
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )