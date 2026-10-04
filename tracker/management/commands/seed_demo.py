import getpass
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tracker.models import Comment, Membership, Project, Task


class Command(BaseCommand):
    help = "Create local synthetic demo users and projects without removing existing data."

    def add_arguments(self, parser):
        parser.add_argument("--reset-passwords", action="store_true",
                            help="Explicitly reset passwords of existing demo users.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo seeding is allowed only with TASKFLOW_DEBUG=1.")
        password = os.environ.get("TASKFLOW_DEMO_PASSWORD") or getpass.getpass("Demo password (12+ chars): ")
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        users = {}
        for name in ("owner", "editor", "viewer", "outsider"):
            user, created = get_user_model().objects.get_or_create(username=f"demo-{name}")
            if created or options["reset_passwords"]:
                user.set_password(password)
                user.save()
            users[name] = user
        project, _ = Project.objects.get_or_create(
            name="Запуск TaskFlow", owner=users["owner"],
            defaults={"description": "Учебный проект: задачи команды и проверка трёх ролей."})
        for name in ("editor", "viewer"):
            Membership.objects.get_or_create(project=project, user=users[name], defaults={"role": name})
        for title, status in (("Проверить границы проекта", "todo"),
                              ("Подготовить демонстрацию", "doing"),
                              ("Согласовать роли пользователей", "done")):
            task, _ = Task.objects.get_or_create(project=project, title=title,
                defaults={"status": status, "created_by": users["owner"],
                          "description": "Только синтетические данные для локальной демонстрации."})
            Comment.objects.get_or_create(task=task, author=users["editor"],
                                          body="Готово к совместному обсуждению.")
        Project.objects.get_or_create(name="Отдельный проект", owner=users["outsider"],
                                      defaults={"description": "Не доступен участникам первого проекта."})
        self.stdout.write(self.style.SUCCESS(
            "Demo data ready: demo-owner, demo-editor, demo-viewer, demo-outsider. "
            "Passwords are not printed. Existing passwords stay unchanged unless --reset-passwords is used."
        ))
