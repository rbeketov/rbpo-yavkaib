from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import CommentForm, MemberForm, ProjectForm, TaskForm
from .models import Membership, Task
from .permissions import accessible_projects, project_and_role


def require_role(role, *allowed):
    if role not in allowed:
        raise PermissionDenied


@login_required
@require_http_methods(["GET"])
def project_list(request):
    projects = accessible_projects(request.user).select_related("owner")
    return render(request, "tracker/project_list.html", {"projects": projects})


@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    form = ProjectForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        messages.success(request, "Проект создан.")
        return redirect("project_detail", project_id=project.pk)
    return render(request, "tracker/form.html", {"form": form, "heading": "Новый проект"})


@login_required
@require_http_methods(["GET"])
def project_detail(request, project_id):
    project, role = project_and_role(request.user, project_id)
    tasks = list(project.tasks.all())
    columns = [(value, label, [task for task in tasks if task.status == value])
               for value, label in Task.Status.choices]
    return render(request, "tracker/project_detail.html", {
        "project": project, "role": role, "columns": columns,
        "can_write": role in ("owner", "editor"),
    })


@login_required
@require_http_methods(["GET", "POST"])
def project_delete(request, project_id):
    project, role = project_and_role(request.user, project_id)
    require_role(role, "owner")
    if request.method == "POST":
        project.delete()
        messages.success(request, "Проект удалён.")
        return redirect("project_list")
    return render(request, "tracker/confirm_delete.html", {
        "project": project, "heading": "Удалить проект?",
        "detail": "Все задачи, комментарии и участники этого проекта будут удалены.",
    })


@login_required
@require_http_methods(["GET", "POST"])
def members(request, project_id):
    project, role = project_and_role(request.user, project_id)
    require_role(role, "owner")
    form = MemberForm(request.POST if request.method == "POST" else None, project=project)
    if request.method == "POST" and form.is_valid():
        Membership.objects.update_or_create(
            project=project, user=form.member_user, defaults={"role": form.cleaned_data["role"]})
        messages.success(request, "Права участника сохранены.")
        return redirect("members", project_id=project.pk)
    return render(request, "tracker/members.html", {
        "project": project, "form": form,
        "memberships": project.memberships.select_related("user").order_by("user__username"),
    })


@login_required
@require_POST
def member_remove(request, project_id, membership_id):
    project, role = project_and_role(request.user, project_id)
    require_role(role, "owner")
    member = get_object_or_404(project.memberships, pk=membership_id)
    member.delete()
    messages.success(request, "Доступ участника отозван.")
    return redirect("members", project_id=project.pk)


@login_required
@require_http_methods(["GET", "POST"])
def task_create(request, project_id):
    project, role = project_and_role(request.user, project_id)
    require_role(role, "owner", "editor")
    form = TaskForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.project = project
        task.created_by = request.user
        task.save()
        return redirect("task_detail", project_id=project.pk, task_id=task.pk)
    return render(request, "tracker/form.html", {
        "project": project, "form": form, "heading": "Новая задача"})


@login_required
@require_http_methods(["GET"])
def task_detail(request, project_id, task_id):
    project, role = project_and_role(request.user, project_id)
    task = get_object_or_404(project.tasks, pk=task_id)
    return render(request, "tracker/task_detail.html", {
        "project": project, "task": task, "role": role,
        "can_write": role in ("owner", "editor"), "form": CommentForm(),
        "comments": task.comments.select_related("author"),
    })


@login_required
@require_http_methods(["GET", "POST"])
def task_edit(request, project_id, task_id):
    project, role = project_and_role(request.user, project_id)
    require_role(role, "owner", "editor")
    task = get_object_or_404(project.tasks, pk=task_id)
    form = TaskForm(request.POST if request.method == "POST" else None, instance=task)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("task_detail", project_id=project.pk, task_id=task.pk)
    return render(request, "tracker/form.html", {
        "project": project, "form": form, "heading": "Изменить задачу"})


@login_required
@require_http_methods(["GET", "POST"])
def task_delete(request, project_id, task_id):
    project, role = project_and_role(request.user, project_id)
    require_role(role, "owner")
    task = get_object_or_404(project.tasks, pk=task_id)
    if request.method == "POST":
        task.delete()
        return redirect("project_detail", project_id=project.pk)
    return render(request, "tracker/confirm_delete.html", {
        "project": project, "heading": "Удалить задачу?", "detail": task.title})


@login_required
@require_POST
def comment_add(request, project_id, task_id):
    project, role = project_and_role(request.user, project_id)
    require_role(role, "owner", "editor")
    task = get_object_or_404(project.tasks, pk=task_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.task = task
        comment.author = request.user
        comment.save()
        return redirect("task_detail", project_id=project.pk, task_id=task.pk)
    return render(request, "tracker/task_detail.html", {
        "project": project, "task": task, "role": role, "can_write": True,
        "form": form, "comments": task.comments.select_related("author"),
    }, status=400)
