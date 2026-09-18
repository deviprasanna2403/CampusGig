import asyncio
from datetime import date, time, timedelta
from decimal import Decimal

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.applications.models import Application
from apps.communication.models import Conversation, Message
from apps.jobs.models import Job, JobCategory
from apps.notifications.models import Notification
from apps.profiles.models import BusinessProfile, Campus, StudentProfile
from config.asgi import application as asgi_application

User = get_user_model()


class Phase7FixtureMixin:
    def make_fixture(self):
        self.student_user = User.objects.create_user(email="student7@example.com", password="C@mpusGig-Str0ng!", role=User.Role.STUDENT)
        self.business_user = User.objects.create_user(email="business7@example.com", password="C@mpusGig-Str0ng!", role=User.Role.BUSINESS)
        campus = Campus.objects.create(name="Phase 7 Campus", city="Bengaluru", location=Point(77.5946, 12.9716, srid=4326))
        BusinessProfile.objects.create(user=self.business_user, business_name="Business 7", campus=campus)
        self.student = StudentProfile.objects.create(user=self.student_user, full_name="Student 7", campus=campus)
        self.category = JobCategory.objects.get(name__iexact="events")
        self.job = Job.objects.create(
            business=self.business_user.business_profile,
            title="Phase 7 Gig",
            description="Test job",
            category=self.category,
            location=Point(77.5946, 12.9716, srid=4326),
            start_date=date(2026, 10, 20), end_date=date(2026, 10, 20),
            start_time=time(9), end_time=time(17), payment_amount=Decimal("500"),
            payment_type=Job.PaymentType.HOURLY, workers_required=1,
            application_deadline=date(2026, 10, 18), eligibility_notes="Students welcome.",
            status=Job.Status.PUBLISHED,
        )


class Phase7HTTPTests(Phase7FixtureMixin, APITestCase):
    def setUp(self):
        self.make_fixture()

    def test_student_application_creates_notifications_and_business_can_shortlist(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.post(reverse("applications:student-list"), {"job_id": str(self.job.id), "cover_note": "Ready."}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = Application.objects.get()
        self.assertTrue(Notification.objects.filter(event=Notification.Event.APPLICATION_SUBMITTED, recipient=self.student_user).exists())
        self.assertTrue(Notification.objects.filter(event=Notification.Event.NEW_APPLICATION, recipient=self.business_user).exists())

        self.client.force_authenticate(self.business_user)
        response = self.client.patch(reverse("applications:business-detail", kwargs={"pk": application.id}), {"status": "SHORTLISTED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Notification.objects.filter(event=Notification.Event.APPLICATION_SHORTLISTED).exists())

    def test_chat_requires_shortlisted_stage_and_scopes_participants(self):
        application = Application.objects.create(job=self.job, student=self.student)
        self.client.force_authenticate(self.student_user)
        response = self.client.post(reverse("communication:conversation-list"), {"application_id": str(application.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        application.status = Application.Status.SHORTLISTED
        application.save(update_fields=["status", "updated_at"])
        response = self.client.post(reverse("communication:conversation-list"), {"application_id": str(application.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        conversation = Conversation.objects.get()

        outsider = User.objects.create_user(email="outsider7@example.com", password="C@mpusGig-Str0ng!", role=User.Role.STUDENT)
        self.client.force_authenticate(outsider)
        response = self.client.get(reverse("communication:conversation-detail", kwargs={"pk": conversation.id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_message_read_state_and_notification(self):
        application = Application.objects.create(job=self.job, student=self.student, status=Application.Status.SHORTLISTED)
        conversation = Conversation.objects.create(application=application, student=self.student_user, business=self.business_user)
        self.client.force_authenticate(self.student_user)
        response = self.client.post(reverse("communication:message-list", kwargs={"conversation_id": conversation.id}), {"body": "Hello"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = Message.objects.get()
        self.assertTrue(Notification.objects.filter(recipient=self.business_user, title="New chat message").exists())
        self.client.force_authenticate(self.business_user)
        response = self.client.patch(reverse("communication:message-read", kwargs={"pk": message.id}), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_interview_requires_shortlisted_application_and_notifies_both_parties(self):
        application = Application.objects.create(job=self.job, student=self.student, status=Application.Status.SUBMITTED)
        self.client.force_authenticate(self.business_user)
        payload = {"application_id": str(application.id), "starts_at": "2026-10-19T09:00:00+05:30", "ends_at": "2026-10-19T10:00:00+05:30"}
        response = self.client.post(reverse("interviews:list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        application.status = Application.Status.SHORTLISTED
        application.save(update_fields=["status", "updated_at"])
        response = self.client.post(reverse("interviews:list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Notification.objects.filter(event=Notification.Event.INTERVIEW_SCHEDULED).count(), 2)

    def test_notifications_are_private_and_mark_read(self):
        notification = Notification.objects.create(recipient=self.student_user, event=Notification.Event.SELECTED, title="Selected", body="Selected")
        self.client.force_authenticate(self.business_user)
        response = self.client.patch(reverse("notifications:read", kwargs={"pk": notification.id}), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.student_user)
        response = self.client.patch(reverse("notifications:read", kwargs={"pk": notification.id}), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)


class Phase7WebsocketTests(Phase7FixtureMixin, TransactionTestCase):
    def setUp(self):
        self.make_fixture()

    def test_authenticated_participant_can_send_and_receive_chat(self):
        application = Application.objects.create(job=self.job, student=self.student, status=Application.Status.SHORTLISTED)
        conversation = Conversation.objects.create(application=application, student=self.student_user, business=self.business_user)
        token = str(RefreshToken.for_user(self.student_user).access_token)

        async def run():
            communicator = WebsocketCommunicator(asgi_application, f"/ws/conversations/{conversation.id}/?token={token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({"body": "Realtime hello"})
            event = await communicator.receive_json_from()
            self.assertEqual(event["body"], "Realtime hello")
            await communicator.disconnect()

        asyncio.run(run())
        self.assertTrue(Message.objects.filter(conversation=conversation, body="Realtime hello").exists())


class RestBroadcastTests(Phase7FixtureMixin, APITestCase):
    """REST-created messages must reach open sockets (the F6 broadcast contract).

    The WS consumer and the REST create view funnel through
    communication.broadcast so every client observes identical updates;
    this pins the REST side of that promise.
    """

    def setUp(self):
        self.make_fixture()

    def test_rest_created_message_broadcasts_exactly_one_event_to_the_group(self):
        application = Application.objects.create(job=self.job, student=self.student, status=Application.Status.SHORTLISTED)
        conversation = Conversation.objects.create(application=application, student=self.student_user, business=self.business_user)
        layer = get_channel_layer()
        group = f"conversation_{conversation.id}"

        async def join_group():
            channel_name = await layer.new_channel()
            await layer.group_add(group, channel_name)
            return channel_name

        observer = asyncio.run(join_group())

        self.client.force_authenticate(self.student_user)
        response = self.client.post(
            reverse("communication:message-list", kwargs={"conversation_id": conversation.id}),
            {"body": "Push over REST"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        async def collect():
            return await asyncio.wait_for(layer.receive(observer), timeout=2)

        event = asyncio.run(collect())
        self.assertEqual(event["type"], "chat.message")
        self.assertEqual(event["message"]["body"], "Push over REST")
        self.assertEqual(event["message"]["sender_id"], str(self.student_user.id))
        self.assertEqual(event["message"]["id"], response.data["id"])

        # Exactly one event: no duplicates, no spurious traffic on the group.
        with self.assertRaises(asyncio.TimeoutError):
            asyncio.run(asyncio.wait_for(layer.receive(observer), timeout=0.2))
