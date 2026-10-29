from django.forms import ModelForm, Select, Textarea, TextInput

from .models import Ticket, TicketMessage


class TicketForm(ModelForm):
    class Meta:
        model = Ticket
        fields = ["subject", "description", "priority"]

        widgets = {
            "subject": TextInput(attrs={"class": "form-control"}),
            "description": Textarea(attrs={"class": "form-control"}),
            "priority": Select(attrs={"class": "form-control"}),
        }


class AgentUpdateTicketForm(ModelForm):
    class Meta:
        model = Ticket
        fields = ["status", "priority", "assigned_to"]

        widgets = {
            "status": Select(attrs={"class": "form-control"}),
            "priority": Select(attrs={"class": "form-control"}),
            "assigned_to": Select(attrs={"class": "form-control"}),
        }


class TicketMessageForm(ModelForm):
    class Meta:
        model = TicketMessage
        fields = ["message"]

        widgets = {
            "message": Textarea(attrs={"class": "form-control"}),
        }
