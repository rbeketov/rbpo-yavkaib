from django import forms
from django.contrib.auth import get_user_model

from .models import Comment, Membership, Project, Task


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description"]


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "status"]


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}


class MemberForm(forms.Form):
    username = forms.CharField(label="Имя пользователя", max_length=150)
    role = forms.ChoiceField(label="Роль", choices=Membership.Role.choices)

    def __init__(self, *args, project, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)

    def clean_username(self):
        name = self.cleaned_data["username"]
        self.member_user = get_user_model().objects.filter(username=name, is_active=True).first()
        if self.member_user is None:
            raise forms.ValidationError("Активный пользователь с таким именем не найден.")
        if self.member_user.pk == self.project.owner_id:
            raise forms.ValidationError("Роль владельца нельзя менять этой формой.")
        return name
