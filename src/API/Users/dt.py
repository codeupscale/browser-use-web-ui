from datetime import datetime, timezone
from pydantic import BaseModel
class DatetimeUtil(BaseModel):
    created_at: datetime
    updated_at: datetime
    def __init__(self):
        super().__init__(
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    def update_timestamp(self, field_name: str) -> datetime:
        if field_name == "created_at":
            self.created_at = datetime.now(timezone.utc)
            return self.created_at
        elif field_name == "updated_at":
            self.updated_at = datetime.now(timezone.utc)
            return self.updated_at
        else:
            raise ValueError("Invalid field name. Must be 'created_at' or 'updated_at'.")

    def get_timestamps(self) -> dict:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

