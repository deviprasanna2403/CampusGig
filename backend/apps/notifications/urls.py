from django.urls import path

from apps.notifications.views import NotificationListView, NotificationReadView

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="list"),
    path("<uuid:pk>/read/", NotificationReadView.as_view(), name="read"),
]
