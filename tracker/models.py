from django.conf import settings
from django.db import models


class Project(models.Model):
    name = models.CharField("Название", max_length=120)
    description = models.TextField("Описание", max_length=2000, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="owned_projects")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        EDITOR = "editor", "Редактор"
        VIEWER = "viewer", "Наблюдатель"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="memberships")
    role = models.CharField("Роль", max_length=10, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_member"),
            models.CheckConstraint(condition=models.Q(role__in=["editor", "viewer"]),
                                   name="valid_member_role"),
        ]


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "К выполнению"
        DOING = "doing", "В работе"
        DONE = "done", "Завершена"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField("Название", max_length=160)
    description = models.TextField("Описание", max_length=4000, blank=True)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.TODO)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.CheckConstraint(
            condition=models.Q(status__in=["todo", "doing", "done"]), name="valid_task_status")]


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField("Комментарий", max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
