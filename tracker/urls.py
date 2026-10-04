from django.urls import path
from . import views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("projects/new/", views.project_create, name="project_create"),
    path("projects/<int:project_id>/", views.project_detail, name="project_detail"),
    path("projects/<int:project_id>/delete/", views.project_delete, name="project_delete"),
    path("projects/<int:project_id>/members/", views.members, name="members"),
    path("projects/<int:project_id>/members/<int:membership_id>/remove/",
         views.member_remove, name="member_remove"),
    path("projects/<int:project_id>/tasks/new/", views.task_create, name="task_create"),
    path("projects/<int:project_id>/tasks/<int:task_id>/", views.task_detail, name="task_detail"),
    path("projects/<int:project_id>/tasks/<int:task_id>/edit/", views.task_edit, name="task_edit"),
    path("projects/<int:project_id>/tasks/<int:task_id>/delete/", views.task_delete, name="task_delete"),
    path("projects/<int:project_id>/tasks/<int:task_id>/comments/", views.comment_add, name="comment_add"),
]
