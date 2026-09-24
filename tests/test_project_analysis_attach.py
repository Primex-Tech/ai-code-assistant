"""Tests for attaching specific files to constrain chat context."""

from contextlib import contextmanager

from flask_login import login_user

from app.extensions import db
from app.models import Project, ProjectFile, User, Workspace
from app.models.project import SOURCE_ARCHIVE, STATUS_READY
from app.services import project_analysis


@contextmanager
def _authorized_context(app, project):
    """Push a request context with the project owner logged in."""
    with app.test_request_context("/"):
        login_user(db.session.get(User, project.user_id))
        yield


def _ready_project(files):
    user = User(username="anauser", email="anauser@example.com")
    user.set_password("supersecret123")
    db.session.add(user)
    db.session.commit()
    workspace = Workspace(user_id=user.id, name="Analysis workspace")
    db.session.add(workspace)
    db.session.commit()
    project = Project(
        workspace_id=workspace.id,
        user_id=user.id,
        name="Analysis project",
        source=SOURCE_ARCHIVE,
        status=STATUS_READY,
    )
    db.session.add(project)
    db.session.commit()

    for path, content in files:
        db.session.add(
            ProjectFile(
                project_id=project.id,
                path=path,
                size=len(content),
                is_binary=False,
                content=content,
            )
        )
    db.session.commit()
    project.file_count = len(files)
    project.total_size_bytes = sum(len(content) for _, content in files)
    db.session.commit()
    return project


class TestAttachedFilesInBuildContext:
    def test_attached_files_selected_before_keyword_scoring(self, app):
        project = _ready_project(
            [
                ("unrelated.py", "x = 1\n"),
                ("target.py", "def answer(): return 42\n"),
            ]
        )
        with _authorized_context(app, project):
            context = project_analysis.build_context(
                project,
                "what is x",
                attached_files=["target.py"],
            )
        assert "target.py" in context["paths"]

    def test_empty_attached_files_behaves_like_before(self, app):
        project = _ready_project(
            [
                ("app.py", "def main(): pass\n"),
            ]
        )
        with _authorized_context(app, project):
            context = project_analysis.build_context(
                project,
                "what does main do",
                attached_files=None,
            )
        assert context["paths"]

    def test_attached_files_still_respect_budget(self, app):
        big = "line = 'x' * 10\n" * 2000
        project = _ready_project(
            [
                ("attached.py", big),
                ("other.py", "y = 2\n"),
            ]
        )
        with _authorized_context(app, project):
            context = project_analysis.build_context(
                project,
                "question",
                attached_files=["attached.py"],
            )
        budget = app.config["PROJECT_MAX_CONTEXT_CHARS"]
        assert len(context["blocks"]) <= budget

    def test_attached_files_count_toward_max_context_files(self, app):
        files = [(f"file_{i}.py", "x\n") for i in range(15)]
        files.append(("attached.py", "attached content\n"))
        project = _ready_project(files)
        with _authorized_context(app, project):
            context = project_analysis.build_context(
                project,
                "question",
                attached_files=["attached.py"],
            )
        assert len(context["paths"]) <= project_analysis.MAX_CONTEXT_FILES


class TestAttachedFilesInBuildMessages:
    def test_build_messages_passes_attached_files(self, app):
        project = _ready_project(
            [
                ("target.py", "def f(): return 1\n"),
                ("other.py", "g = 2\n"),
            ]
        )
        with _authorized_context(app, project):
            messages = project_analysis.build_messages(
                project,
                "hello",
                [],
                attached_files=["target.py"],
            )
        assert messages[0]["role"] == "system"
        assert "target.py" in messages[-1]["content"]


class TestAttachedFilesInChatWithProject:
    def test_chat_with_project_accepts_attached_files(self, app):
        project = _ready_project(
            [
                ("target.py", "def f(): return 1\n"),
                ("other.py", "g = 2\n"),
            ]
        )
        with _authorized_context(app, project):
            result = project_analysis.chat_with_project(
                project,
                "hello",
                attached_files=["target.py"],
            )
        assert result["context_paths"]
        assert "target.py" in result["context_paths"]
