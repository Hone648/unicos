import shutil
import tempfile

from attachments.admin import AttachmentAdmin
from attachments.models import Attachment
from customers.models import Customer
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def make_superuser(username="root"):
    return get_user_model().objects.create_superuser(
        username=username, password="pw-test-12345", email="root@example.com"
    )


def make_customer():
    return Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name="Customer",
    )


def make_vehicle(customer):
    return Vehicle.objects.create(
        customer=customer, vin=VALID_VIN, make="Honda", model="Civic", year=2021
    )


def make_repair_order(customer, vehicle):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number="RO-ATT-ADM-001"
    )


def make_request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


class AttachmentAdminRegistrationTests(TestCase):
    def test_attachment_admin_is_registered(self):
        self.assertIn(Attachment, admin.site._registry)
        self.assertIs(admin.site._registry[Attachment].__class__, AttachmentAdmin)


class AttachmentAdminFieldProtectionTests(TestCase):
    def setUp(self):
        self.admin_instance = AttachmentAdmin(Attachment, admin.site)

    def test_file_metadata_fields_are_readonly(self):
        for field in (
            "repair_order",
            "file",
            "original_filename",
            "content_type",
            "size_bytes",
            "uploaded_by",
            "created_at",
        ):
            self.assertIn(field, self.admin_instance.readonly_fields)

    def test_category_and_description_are_not_readonly(self):
        self.assertNotIn("category", self.admin_instance.readonly_fields)
        self.assertNotIn("description", self.admin_instance.readonly_fields)

    def test_delete_permission_disabled(self):
        request = make_request(make_superuser())
        self.assertFalse(self.admin_instance.has_delete_permission(request))
        self.assertFalse(self.admin_instance.has_delete_permission(request, obj=object()))


class AttachmentAdminChangeFormTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._media_settings = self.settings(MEDIA_ROOT=self._tmpdir)
        self._media_settings.__enter__()
        self.client.force_login(make_superuser())
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        self.attachment = Attachment.objects.create(
            repair_order=ro,
            file=SimpleUploadedFile("photo.jpg", b"fake-jpeg-content", content_type="image/jpeg"),
            original_filename="photo.jpg",
            content_type="image/jpeg",
            size_bytes=17,
            category=Attachment.Category.OTHER,
            description="Original description",
        )

    def tearDown(self):
        self._media_settings.__exit__(None, None, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_change_form_loads(self):
        url = reverse("admin:attachments_attachment_change", args=[self.attachment.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "photo.jpg")

    def test_change_form_does_not_render_file_input(self):
        url = reverse("admin:attachments_attachment_change", args=[self.attachment.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'type="file"')

    def test_post_cannot_change_protected_fields(self):
        url = reverse("admin:attachments_attachment_change", args=[self.attachment.pk])
        self.client.post(
            url,
            data={
                "original_filename": "tampered.jpg",
                "content_type": "application/x-tampered",
                "size_bytes": "999999",
                "category": Attachment.Category.PHOTO,
                "description": "Updated description",
                "_continue": "Save and continue editing",
            },
        )
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.original_filename, "photo.jpg")
        self.assertEqual(self.attachment.content_type, "image/jpeg")
        self.assertEqual(self.attachment.size_bytes, 17)

    def test_post_can_change_category_and_description(self):
        url = reverse("admin:attachments_attachment_change", args=[self.attachment.pk])
        self.client.post(
            url,
            data={
                "category": Attachment.Category.PHOTO,
                "description": "Updated description",
                "_continue": "Save and continue editing",
            },
        )
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.category, Attachment.Category.PHOTO)
        self.assertEqual(self.attachment.description, "Updated description")

    def test_delete_view_is_forbidden(self):
        url = reverse("admin:attachments_attachment_delete", args=[self.attachment.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
