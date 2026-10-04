"""Executable checks of the published role matrix and trust boundaries."""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Comment, Membership, Project, Task


@override_settings(SECURE_SSL_REDIRECT=False)
class AuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {role: get_user_model().objects.create_user(username=role)
                     for role in ("owner", "editor", "viewer", "outsider")}
        cls.project = Project.objects.create(name="Team secret project", owner=cls.users["owner"])
        cls.other = Project.objects.create(name="Other project", owner=cls.users["outsider"])
        cls.editor_member = Membership.objects.create(project=cls.project, user=cls.users["editor"], role="editor")
        cls.viewer_member = Membership.objects.create(project=cls.project, user=cls.users["viewer"], role="viewer")
        cls.task = Task.objects.create(project=cls.project, title="Original task", created_by=cls.users["owner"])
        cls.other_task = Task.objects.create(project=cls.other, title="Foreign task", created_by=cls.users["outsider"])

    def url(self, name, **kwargs):
        return reverse(name, kwargs={"project_id": self.project.pk, **kwargs})

    def test_read_matrix_and_project_list_isolation(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                expected = 404 if role == "outsider" else 200
                self.assertEqual(self.client.get(self.url("project_detail")).status_code, expected)
                self.assertEqual(self.client.get(self.url("task_detail", task_id=self.task.pk)).status_code, expected)
                listing = self.client.get(reverse("project_list"))
                if role == "outsider":
                    self.assertNotContains(listing, "Team secret project")
                else:
                    self.assertContains(listing, "Team secret project")
                    self.assertNotContains(listing, "Other project")

    def test_task_create_matrix_and_forged_ownership(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                before = Task.objects.count()
                response = self.client.post(self.url("task_create"), {
                    "title": f"By {role}", "status": "todo", "description": "A task",
                    "project": self.other.pk, "created_by": self.users["outsider"].pk,
                })
                allowed = role in ("owner", "editor")
                self.assertEqual(response.status_code, 302 if allowed else 404 if role == "outsider" else 403)
                self.assertEqual(Task.objects.count(), before + int(allowed))
                if allowed:
                    task = Task.objects.get(title=f"By {role}")
                    self.assertEqual(task.project_id, self.project.pk)
                    self.assertEqual(task.created_by_id, user.pk)

    def test_task_update_matrix(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.task.title = "Original task"
                self.task.status = "todo"
                self.task.save()
                self.client.force_login(user)
                response = self.client.post(self.url("task_edit", task_id=self.task.pk),
                                            {"title": "Updated", "status": "done"})
                allowed = role in ("owner", "editor")
                self.assertEqual(response.status_code, 302 if allowed else 404 if role == "outsider" else 403)
                self.task.refresh_from_db()
                self.assertEqual(self.task.title, "Updated" if allowed else "Original task")

    def test_comment_matrix_and_forged_author(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                before = Comment.objects.count()
                response = self.client.post(self.url("comment_add", task_id=self.task.pk),
                    {"body": f"Comment by {role}", "author": self.users["outsider"].pk,
                     "task": self.other_task.pk})
                allowed = role in ("owner", "editor")
                self.assertEqual(response.status_code, 302 if allowed else 404 if role == "outsider" else 403)
                self.assertEqual(Comment.objects.count(), before + int(allowed))
                if allowed:
                    comment = Comment.objects.get(body=f"Comment by {role}")
                    self.assertEqual(comment.author_id, user.pk)
                    self.assertEqual(comment.task_id, self.task.pk)

    def test_delete_task_matrix(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                task = Task.objects.create(project=self.project, title="Delete probe", created_by=self.users["owner"])
                self.client.force_login(user)
                response = self.client.post(self.url("task_delete", task_id=task.pk))
                self.assertEqual(response.status_code, 302 if role == "owner" else 404 if role == "outsider" else 403)
                self.assertEqual(Task.objects.filter(pk=task.pk).exists(), role != "owner")

    def test_delete_project_matrix(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                project = Project.objects.create(name="Delete probe", owner=self.users["owner"])
                for member_role in ("editor", "viewer"):
                    Membership.objects.create(project=project, user=self.users[member_role], role=member_role)
                self.client.force_login(user)
                response = self.client.post(reverse("project_delete", kwargs={"project_id": project.pk}))
                self.assertEqual(response.status_code, 302 if role == "owner" else 404 if role == "outsider" else 403)
                self.assertEqual(Project.objects.filter(pk=project.pk).exists(), role != "owner")

    def test_members_management_matrix(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                response = self.client.post(self.url("members"), {"username": "viewer", "role": "viewer"})
                self.assertEqual(response.status_code, 302 if role == "owner" else 404 if role == "outsider" else 403)
                page = self.client.get(self.url("members"))
                self.assertEqual(page.status_code, 200 if role == "owner" else 404 if role == "outsider" else 403)

    def test_remove_member_matrix(self):
        for role in ("editor", "viewer", "outsider", "owner"):
            with self.subTest(role=role):
                self.client.force_login(self.users[role])
                response = self.client.post(self.url("member_remove", membership_id=self.viewer_member.pk))
                self.assertEqual(response.status_code, 302 if role == "owner" else 404 if role == "outsider" else 403)
                self.assertEqual(Membership.objects.filter(pk=self.viewer_member.pk).exists(), role != "owner")

    def test_cross_project_object_ids_do_not_bypass_access(self):
        foreign_member = Membership.objects.create(project=self.other, user=self.users["viewer"], role="viewer")
        self.client.force_login(self.users["owner"])
        for name, method, data in (
            ("task_detail", "get", {}), ("task_edit", "post", {"title": "Hijacked", "status": "done"}),
            ("task_delete", "post", {}), ("comment_add", "post", {"body": "Hijacked"}),
        ):
            with self.subTest(endpoint=name):
                response = getattr(self.client, method)(self.url(name, task_id=self.other_task.pk), data)
                self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.post(self.url("member_remove", membership_id=foreign_member.pk)).status_code, 404)
        self.other_task.refresh_from_db()
        self.assertEqual(self.other_task.title, "Foreign task")
        self.assertEqual(self.other_task.comments.count(), 0)
        self.assertTrue(Membership.objects.filter(pk=foreign_member.pk).exists())

    def test_revoked_membership_takes_effect_on_next_request(self):
        self.client.force_login(self.users["editor"])
        self.assertEqual(self.client.get(self.url("project_detail")).status_code, 200)
        self.editor_member.delete()
        self.assertEqual(self.client.get(self.url("project_detail")).status_code, 404)
        self.assertEqual(self.client.post(self.url("task_create"), {"title": "Denied", "status": "todo"}).status_code, 404)
        self.assertFalse(Task.objects.filter(title="Denied").exists())

    def test_role_change_takes_effect_without_new_login(self):
        self.client.force_login(self.users["editor"])
        self.editor_member.role = "viewer"
        self.editor_member.save()
        self.assertEqual(self.client.post(self.url("task_edit", task_id=self.task.pk),
            {"title": "Denied", "status": "done"}).status_code, 403)

    def test_owner_is_immutable_and_cannot_be_granted_in_member_form(self):
        self.client.force_login(self.users["owner"])
        for data in ({"username": "owner", "role": "viewer"},
                     {"username": "editor", "role": "owner"}):
            with self.subTest(data=data):
                response = self.client.post(self.url("members"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.project.refresh_from_db()
        self.editor_member.refresh_from_db()
        self.assertEqual(self.project.owner_id, self.users["owner"].pk)
        self.assertEqual(self.editor_member.role, "editor")
        self.assertFalse(self.project.memberships.filter(user=self.users["owner"]).exists())

    def test_superuser_does_not_bypass_project_membership(self):
        self.users["outsider"].is_superuser = True
        self.users["outsider"].is_staff = True
        self.users["outsider"].save()
        self.client.force_login(self.users["outsider"])
        self.assertEqual(self.client.get(self.url("project_detail")).status_code, 404)

    def test_any_authenticated_user_can_create_owned_project(self):
        self.client.force_login(self.users["viewer"])
        response = self.client.post(reverse("project_create"),
            {"name": "Mine", "description": "New", "owner": self.users["owner"].pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Project.objects.get(name="Mine").owner_id, self.users["viewer"].pk)

    def test_anonymous_requests_do_not_read_or_mutate(self):
        for name, params in (("project_detail", {}), ("task_detail", {"task_id": self.task.pk}),
                             ("task_create", {}), ("task_edit", {"task_id": self.task.pk}),
                             ("task_delete", {"task_id": self.task.pk}), ("project_delete", {}),
                             ("members", {}), ("member_remove", {"membership_id": self.viewer_member.pk}),
                             ("comment_add", {"task_id": self.task.pk})):
            with self.subTest(endpoint=name):
                for method in ("get", "post"):
                    response = getattr(self.client, method)(self.url(name, **params))
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith(reverse("login")))
        self.assertEqual(Task.objects.count(), 2)
        self.assertEqual(Comment.objects.count(), 0)
        self.assertEqual(Membership.objects.count(), 2)

    def test_get_does_not_delete_or_comment_or_logout(self):
        self.client.force_login(self.users["owner"])
        self.assertEqual(self.client.get(self.url("task_delete", task_id=self.task.pk)).status_code, 200)
        self.assertEqual(self.client.get(self.url("project_delete")).status_code, 200)
        self.assertEqual(self.client.get(self.url("member_remove", membership_id=self.viewer_member.pk)).status_code, 405)
        self.assertEqual(self.client.get(self.url("comment_add", task_id=self.task.pk)).status_code, 405)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertEqual(Comment.objects.count(), 0)

    def test_real_csrf_enforcement_rejects_mutation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.users["owner"])
        cases = [("project_create", {}, {"name": "CSRF"}),
                 ("task_create", {"project_id": self.project.pk}, {"title": "CSRF", "status": "todo"}),
                 ("task_edit", {"project_id": self.project.pk, "task_id": self.task.pk}, {"title": "CSRF", "status": "done"}),
                 ("task_delete", {"project_id": self.project.pk, "task_id": self.task.pk}, {}),
                 ("project_delete", {"project_id": self.project.pk}, {}),
                 ("members", {"project_id": self.project.pk}, {"username": "outsider", "role": "editor"}),
                 ("member_remove", {"project_id": self.project.pk, "membership_id": self.viewer_member.pk}, {}),
                 ("comment_add", {"project_id": self.project.pk, "task_id": self.task.pk}, {"body": "CSRF"}),
                 ("logout", {}, {})]
        for name, kwargs, data in cases:
            with self.subTest(endpoint=name):
                self.assertEqual(client.post(reverse(name, kwargs=kwargs), data).status_code, 403)
        self.assertEqual(Task.objects.count(), 2)
        self.assertEqual(Project.objects.count(), 2)
        self.assertEqual(Comment.objects.count(), 0)

    def test_valid_csrf_form_can_create_task(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.users["editor"])
        url = self.url("task_create")
        client.get(url)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, {"title": "Valid CSRF", "status": "todo",
            "csrfmiddlewaretoken": token}).status_code, 302)

    def test_stored_html_is_escaped_in_title_description_and_comment(self):
        payload = '<script>alert("test")</script>'
        self.task.title = payload
        self.task.description = payload
        self.task.save()
        Comment.objects.create(task=self.task, author=self.users["owner"], body=payload)
        self.client.force_login(self.users["viewer"])
        response = self.client.get(self.url("task_detail", task_id=self.task.pk))
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;", count=4)

    def test_invalid_and_oversized_task_inputs_leave_database_unchanged(self):
        self.client.force_login(self.users["editor"])
        for data in ({"title": "x" * 161, "status": "todo"}, {"title": "Valid", "status": "admin"},
                     {"title": "Valid", "status": "todo", "description": "x" * 4001},
                     {"title": "   ", "status": "todo"}):
            with self.subTest(fields=list(data)):
                response = self.client.post(self.url("task_create"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(Task.objects.count(), 2)

    def test_empty_and_oversized_comment_rejected(self):
        self.client.force_login(self.users["editor"])
        for body in ("   ", "x" * 2001):
            self.assertEqual(self.client.post(self.url("comment_add", task_id=self.task.pk), {"body": body}).status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

    def test_viewer_has_no_write_buttons(self):
        self.client.force_login(self.users["viewer"])
        response = self.client.get(self.url("project_detail"))
        self.assertNotContains(response, self.url("task_create"))
        self.assertNotContains(response, self.url("members"))
        self.assertContains(response, "Доступ только для чтения")

    def test_login_logout_and_external_redirect_rejected(self):
        user = self.users["editor"]
        user.set_password("Synthetic-test-password-394!")
        user.save()
        response = self.client.post(reverse("login"), {"username": "editor",
            "password": "Synthetic-test-password-394!", "next": "https://example.org/"})
        self.assertRedirects(response, reverse("project_list"))
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(self.client.get(self.url("project_detail")).status_code, 302)

    def test_unknown_user_and_inactive_member_rejected(self):
        self.client.force_login(self.users["owner"])
        self.users["outsider"].is_active = False
        self.users["outsider"].save()
        for username in ("does-not-exist", "outsider"):
            response = self.client.post(self.url("members"), {"username": username, "role": "editor"})
            self.assertTrue(response.context["form"].errors)

    def test_security_headers_on_authenticated_page(self):
        self.client.force_login(self.users["owner"])
        response = self.client.get(self.url("project_detail"))
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")


class DemoCommandTests(TestCase):
    @override_settings(DEBUG=True)
    @patch.dict("os.environ", {"TASKFLOW_DEMO_PASSWORD": "Synthetic-demo-test-394!"})
    def test_seed_is_repeatable_and_preserves_existing_passwords(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        editor = get_user_model().objects.get(username="demo-editor")
        editor.set_password("Changed-test-password-394!")
        editor.save()
        call_command("seed_demo", stdout=output)
        editor.refresh_from_db()
        self.assertEqual(get_user_model().objects.count(), 4)
        self.assertEqual(Project.objects.count(), 2)
        self.assertEqual(Task.objects.count(), 3)
        self.assertTrue(editor.check_password("Changed-test-password-394!"))
        self.assertNotIn("Synthetic-demo-test-394!", output.getvalue())

    @override_settings(DEBUG=False)
    def test_seed_refuses_non_debug_environment(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        self.assertEqual(get_user_model().objects.count(), 0)
