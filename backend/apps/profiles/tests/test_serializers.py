from django.test import TestCase

from apps.profiles.serializers import CampusSerializer, SkillSerializer
from apps.profiles.tests.helpers import BENGALURU_CAMPUS_A, make_campus


class CampusSerializerTests(TestCase):
    def test_valid_payload_builds_point(self):
        serializer = CampusSerializer(
            data={
                "name": "Delta Institute",
                "city": "Pune",
                "state": "Maharashtra",
                "country": "India",
                "latitude": 18.5204,
                "longitude": 73.8567,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        campus = serializer.save()
        self.assertAlmostEqual(campus.location.y, 18.5204, places=4)
        self.assertAlmostEqual(campus.location.x, 73.8567, places=4)

    def test_output_includes_latitude_longitude_not_raw_geometry(self):
        campus = make_campus(**BENGALURU_CAMPUS_A)
        data = CampusSerializer(campus).data
        self.assertIn("latitude", data)
        self.assertIn("longitude", data)
        self.assertNotIn("location", data)
        self.assertAlmostEqual(data["latitude"], BENGALURU_CAMPUS_A["latitude"], places=4)

    def test_latitude_out_of_range_rejected(self):
        serializer = CampusSerializer(
            data={"name": "Bad Campus", "city": "X", "latitude": 91, "longitude": 0}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("latitude", serializer.errors)

    def test_longitude_out_of_range_rejected(self):
        serializer = CampusSerializer(
            data={"name": "Bad Campus 2", "city": "X", "latitude": 0, "longitude": 200}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("longitude", serializer.errors)

    def test_duplicate_name_case_insensitive_rejected(self):
        make_campus(**BENGALURU_CAMPUS_A)
        serializer = CampusSerializer(
            data={
                "name": BENGALURU_CAMPUS_A["name"].upper(),
                "city": "Bengaluru",
                "latitude": 12.9,
                "longitude": 77.6,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)


class SkillSerializerTests(TestCase):
    def test_duplicate_name_case_insensitive_rejected(self):
        serializer = SkillSerializer(data={"name": "Python"})
        self.assertTrue(serializer.is_valid())
        serializer.save()

        dup_serializer = SkillSerializer(data={"name": "python"})
        self.assertFalse(dup_serializer.is_valid())
        self.assertIn("name", dup_serializer.errors)

    def test_blank_name_rejected(self):
        serializer = SkillSerializer(data={"name": "   "})
        self.assertFalse(serializer.is_valid())
