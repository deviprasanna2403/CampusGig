from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.notifications.models import Notification


def create_notification(*, recipient, event, title, body, payload=None, send_email=True):
    notification = Notification.objects.create(
        recipient=recipient,
        event=event,
        title=title,
        body=body,
        payload=payload or {},
    )
    if send_email and getattr(settings, "PHASE7_EMAIL_NOTIFICATIONS", False):
        send_mail(title, body, settings.DEFAULT_FROM_EMAIL, [recipient.email], fail_silently=True)
        notification.email_sent_at = timezone.now()
        notification.save(update_fields=["email_sent_at", "updated_at"])
    return notification


def notify_application_submitted(application):
    create_notification(
        recipient=application.job.business.user,
        event=Notification.Event.NEW_APPLICATION,
        title="New application received",
        body=f"A student applied for {application.job.title}.",
        payload={"application_id": str(application.id), "job_id": str(application.job_id)},
    )
    return create_notification(
        recipient=application.student.user,
        event=Notification.Event.APPLICATION_SUBMITTED,
        title="Application submitted",
        body=f"Your application for {application.job.title} was submitted.",
        payload={"application_id": str(application.id), "job_id": str(application.job_id)},
    )


def notify_application_status(application, old_status):
    event_map = {
        "SHORTLISTED": Notification.Event.APPLICATION_SHORTLISTED,
        "SELECTED": Notification.Event.SELECTED,
        "REJECTED": Notification.Event.REJECTED,
    }
    event = event_map.get(application.status)
    if not event:
        return None
    return create_notification(
        recipient=application.student.user,
        event=event,
        title=f"Application {application.status.lower()}",
        body=f"Your application for {application.job.title} is now {application.status.lower()}.",
        payload={"application_id": str(application.id), "previous_status": old_status},
    )


def notify_application_withdrawn(application):
    return create_notification(
        recipient=application.job.business.user,
        event=Notification.Event.APPLICATION_WITHDRAWN,
        title="Application withdrawn",
        body=f"An application for {application.job.title} was withdrawn.",
        payload={"application_id": str(application.id), "job_id": str(application.job_id)},
    )


def notify_interview(interview, event=Notification.Event.INTERVIEW_SCHEDULED):
    application = interview.application
    payload = {"interview_id": str(interview.id), "application_id": str(application.id)}
    for recipient in (application.student.user, application.job.business.user):
        create_notification(
            recipient=recipient,
            event=event,
            title="Interview updated" if event != Notification.Event.INTERVIEW_SCHEDULED else "Interview scheduled",
            body=f"An interview for {application.job.title} is scheduled at {interview.starts_at.isoformat()}.",
            payload=payload,
        )
