"""Project-scoped authorization. Django staff/superuser flags confer no app role."""
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Project


def accessible_projects(user):
    return Project.objects.filter(Q(owner=user) | Q(memberships__user=user)).distinct()


def project_and_role(user, project_id):
    project = get_object_or_404(accessible_projects(user), pk=project_id)
    if project.owner_id == user.pk:
        return project, "owner"
    role = project.memberships.filter(user=user).values_list("role", flat=True).first()
    if role is None:
        raise Http404
    return project, role
