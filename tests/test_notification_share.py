"""Tests for the share notification type (#54)."""

from app.extensions import db
from app.models import Notification, NotificationPreference, Project, User
from app.services.notifications import notify


def _create_user(username, email):
    user = User(username=username, email=email)
    user.set_password("supersecret123")
    db.session.add(user)
    db.session.commit()
    return user


class TestShareNotificationType:
    def test_share_is_defined(self):
        from app.models.notification import NOTIF_SHARE, NOTIF_TYPES

        assert NOTIF_SHARE == "share"
        assert NOTIF_SHARE in NOTIF_TYPES

    def test_notify_share_creates_notification(self, client, make_user, login):
        sender = _create_user("sender", "sender@example.com")
        recipient = _create_user("recipient", "recipient@example.com")
        login(email="sender@example.com")

        notification = notify(
            recipient,
            "share",
            actor=sender,
            payload={"title": "Project shared"},
        )
        assert notification is not None
        assert notification.type == "share"
        assert notification.is_read is False

    def test_notify_share_respects_preferences(self, client, app, make_user, login):
        user = make_user()
        login()
        client.put(
            "/workspaces/api/notifications/preferences",
            json={"shares": False},
        )
        sender = _create_user("sender2", "sender2@example.com")
        created = notify(user, "share", actor=sender, payload={"title": "Test"})
        assert created is None

    def test_share_allows_by_default(self, client, make_user, login):
        user = make_user()
        login()
        client.put(
            "/workspaces/api/notifications/preferences",
            json={"shares": False},
        )
        sender = _create_user("sender3", "sender3@example.com")
        created = notify(user, "share", actor=sender, payload={"title": "Test"})
        assert created is None

        client.put(
            "/workspaces/api/notifications/preferences",
            json={"shares": True},
        )
        created = notify(user, "share", actor=sender, payload={"title": "Test"})
        assert created is not None


class TestSharePreferenceModel:
    def test_shares_column_defaults_true(self, client, make_user, login):
        make_user()
        login()
        data = client.get("/workspaces/api/notifications/preferences").get_json()
        assert data["shares"] is True

    def test_preference_allows_share_when_on(self, client, make_user, login):
        user = make_user()
        login()
        client.get("/workspaces/api/notifications/preferences")
        pref = NotificationPreference.query.filter_by(user_id=user.id).first()
        assert pref is not None
        assert pref.allows("share") is True

    def test_preference_rejects_share_when_off(self, client, make_user, login):
        user = make_user()
        login()
        client.put(
            "/workspaces/api/notifications/preferences",
            json={"shares": False},
        )
        pref = NotificationPreference.query.filter_by(user_id=user.id).first()
        assert pref.allows("share") is False


class TestShareEndpoint:
    def test_share_project_creates_notification(self, client, make_user, login, app):
        sender = _create_user("share_sender", "share_sender@example.com")
        recipient = _create_user("share_recipient", "share_recipient@example.com")
        login(email="share_sender@example.com")

        project = Project(name="Test Project", workspace_id=1, user_id=sender.id)
        db.session.add(project)
        db.session.commit()

        response = client.post(
            f"/workspaces/api/projects/{project.id}/share",
            json={"user_id": recipient.id},
        )
        assert response.status_code == 200
        assert response.get_json()["ok"] is True

        notifications = Notification.query.filter_by(user_id=recipient.id, type="share").all()
        assert len(notifications) == 1
        assert notifications[0].payload["title"] == "share_sender shared Test Project with you"

        db.session.delete(project)
        db.session.commit()

    def test_share_project_self_share_denied(self, client, make_user, login, app):
        user = make_user()
        login()

        project = Project(name="Test Project", workspace_id=1, user_id=user.id)
        db.session.add(project)
        db.session.commit()

        response = client.post(
            f"/workspaces/api/projects/{project.id}/share",
            json={"user_id": user.id},
        )
        assert response.status_code == 400
        assert "cannot share" in response.get_json()["error"].lower()

        db.session.delete(project)
        db.session.commit()

    def test_share_project_missing_user_id(self, client, make_user, login, app):
        user = make_user()
        login()

        project = Project(name="Test Project", workspace_id=1, user_id=user.id)
        db.session.add(project)
        db.session.commit()

        response = client.post(
            f"/workspaces/api/projects/{project.id}/share",
            json={},
        )
        assert response.status_code == 400
        assert "user_id" in response.get_json()["error"].lower()

        db.session.delete(project)
        db.session.commit()

    def test_share_project_nonexistent_user(self, client, make_user, login, app):
        sender = _create_user("share_sender2", "share_sender2@example.com")
        login(email="share_sender2@example.com")

        project = Project(name="Test Project", workspace_id=1, user_id=sender.id)
        db.session.add(project)
        db.session.commit()

        response = client.post(
            f"/workspaces/api/projects/{project.id}/share",
            json={"user_id": 99999},
        )
        assert response.status_code == 404

        db.session.delete(project)
        db.session.commit()

    def test_share_preference_type_in_map(self):
        from app.models.notification_preference import PREF_SHARES, TYPE_PREFERENCE_MAP

        assert "share" in TYPE_PREFERENCE_MAP
        assert TYPE_PREFERENCE_MAP["share"] == PREF_SHARES

    def test_preference_types_includes_shares(self):
        from app.models.notification_preference import PREF_SHARES, PREFERENCE_TYPES

        assert PREF_SHARES in PREFERENCE_TYPES

    def test_data_migration_adds_shares_column(self, client, make_user, login):
        user = make_user()
        login()
        client.get("/workspaces/api/notifications/preferences")
        pref = NotificationPreference.query.filter_by(user_id=user.id).first()
        assert pref is not None
        assert hasattr(pref, "shares")
        assert pref.shares is True

    def test_mark_read_works_for_share_notification(self, client, make_user, login, app):
        sender = _create_user("mark_sender", "mark_sender@example.com")
        recipient = _create_user("mark_recipient", "mark_recipient@example.com")
        login(email="mark_sender@example.com")

        project = Project(name="Mark Project", workspace_id=1, user_id=sender.id)
        db.session.add(project)
        db.session.commit()

        response = client.post(
            f"/workspaces/api/projects/{project.id}/share",
            json={"user_id": recipient.id},
        )
        assert response.status_code == 200

        notification = Notification.query.filter_by(user_id=recipient.id, type="share").first()
        assert notification is not None

        login(email="mark_recipient@example.com")
        mark_response = client.post(f"/workspaces/api/notifications/{notification.id}/read")
        assert mark_response.status_code == 200
        assert mark_response.get_json()["is_read"] is True

        db.session.delete(project)
        db.session.commit()
