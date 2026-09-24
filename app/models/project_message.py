"""Project chat message model.

Messages exchanged with the AI assistant about a single project. Kept separate
from the general-purpose ``Message`` table because project chat always runs
through bounded, project-aware context retrieval rather than free-form history.
"""

from datetime import UTC, datetime

from app.extensions import db


class ProjectMessage(db.Model):
    """A single user/assistant message within a project chat."""

    __tablename__ = "project_messages"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id = db.Column(
        db.Integer, db.ForeignKey("project_sessions.id", ondelete="SET NULL"), nullable=True
    )
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    attached_files = db.Column(db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    project = db.relationship("Project", back_populates="messages")
    session = db.relationship("ProjectSession", back_populates="messages")

    def to_dict(self) -> dict:
        """Serialize the message for JSON API responses."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "attached_files": self.attached_files,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ProjectMessage id={self.id} role={self.role!r}>"
