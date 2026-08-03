from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User

class Document(SQLModel, table=True):

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    filename: str

    original_filename: str

    # Exercise 2: Document Versioning
    version: int = Field(
        default=1
    )

    file_size: int  # in bytes

    file_type: str  # MIME type

    status: str = Field(
        default="uploaded"
    )
    # uploaded, processing, enriched, failed

    # Location data
    city: str = Field(
        index=True
    )

    country: str = Field(
        default="Kenya"
    )

    # Weather data
    weather_data: Optional[str] = Field(
        default=None
    )

    weather_fetched_at: Optional[datetime] = Field(default=None)

    # Metadata
    description: Optional[str] = Field(default=None)

    uploader_id: int = Field(
        foreign_key="user.id"
    )

    uploader: "User" = Relationship(
        back_populates="documents"
    )

    uploaded_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    # File path on server
    file_path: str


class DocumentCreate(SQLModel):

    city: str = Field(
        min_length=2,
        max_length=100
    )

    country: str = Field(
        default="Kenya",
        min_length=2,
        max_length=100
    )

    description: Optional[str] = None


class DocumentUpdate(SQLModel):

    city: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100
    )

    country: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100
    )

    description: Optional[str] = None