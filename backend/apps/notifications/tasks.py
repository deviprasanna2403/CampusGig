from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from apps.notifications.models import Notification
from apps.applications.models import Application


@shared_task
def send_pending_notification_emails():
    notifications = Notification.objects.filter(email_sent_at__isnull=True).select_related("recipient")[:100]
    sent = 0
    for notification in notifications:
        send_mail(notification.title, notification.body, settings.DEFAULT_FROM_EMAIL, [notification.recipient.email], fail_silently=True)
        notification.email_sent_at = timezone.now()
        notification.save(update_fields=["email_sent_at", "updated_at"])
        sent += 1
    return sent


@shared_task
def send_job_deadline_reminders():
    from datetime import timedelta

    from django.utils import timezone

    tomorrow = timezone.localdate() + timedelta(days=1)
    applications = Application.objects.filter(
        job__application_deadline=tomorrow,
        status__in=[Application.Status.SUBMITTED, Application.Status.SHORTLISTED, Application.Status.INTERVIEW],
    ).select_related("student__user", "job")
    created = 0
    for application in applications:
        notification = Notification.objects.filter(
            recipient=application.student.user,
            event=Notification.Event.JOB_DEADLINE_REMINDER,
            payload__application_id=str(application.id),
        ).first()
        if notification is None:
            create = Notification.objects.create(
                recipient=application.student.user,
                event=Notification.Event.JOB_DEADLINE_REMINDER,
                title="Job deadline tomorrow",
                body=f"Applications for {application.job.title} close tomorrow.",
                payload={"application_id": str(application.id), "job_id": str(application.job_id)},
            )
            created += 1
    return created
