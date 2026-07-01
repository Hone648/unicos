import io
import os
import shutil
import tempfile

from accounts.authorization import (
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
)
from attachments.forms import AttachmentForm
from attachments.models import Attachment
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"
CSV_BYTES = b"column,value\none,two\n"
GIF_BYTES = b"GIF89a"
JPEG_BYTES = b"\xff\xd8\xff\xe0minimal-jpeg"
PDF_BYTES = b"%PDF-1.4\nminimal pdf"
PNG_BYTES = b"\x89PNG\r\n\x1a\nminimal-png"
TXT_BYTES = b"plain text"
WEBP_BYTES = b"RIFF\x0c\x00\x00\x00WEBPminimal"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assign_role(user, role_name):
    group, _ = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


def make_user(username="staffer", role_name=ROLE_MANAGER, **kwargs):
    user = get_user_model().objects.create_user(
        username=username, password="pw-test-12345", **kwargs
    )
    if role_name:
        assign_role(user, role_name)
    return user


def make_customer(**kwargs):
    defaults = {
        "customer_type": Customer.CustomerType.INDIVIDUAL,
        "first_name": "Jane",
        "last_name": "Smith",
    }
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def make_vehicle(customer, vin=VALID_VIN, **kwargs):
    return Vehicle.objects.create(
        customer=customer, vin=vin, make="Honda", model="Civic", year=2021, **kwargs
    )


def make_repair_order(customer, vehicle, number="RO-0001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number, **kwargs
    )


def make_small_jpg():
    return SimpleUploadedFile("photo.jpg", JPEG_BYTES, content_type="image/jpeg")


def make_upload(name, content, content_type):
    return SimpleUploadedFile(name, content, content_type=content_type)


def make_suspicious_upload(name):
    uploaded = make_upload("photo.jpg", JPEG_BYTES, "image/jpeg")
    uploaded._name = name
    return uploaded


def make_oversized_file():
    return InMemoryUploadedFile(
        file=io.BytesIO(b"x"),
        field_name="file",
        name="big.jpg",
        content_type="image/jpeg",
        size=26 * 1024 * 1024,
        charset=None,
    )


def upload_url(repair_order_pk):
    return reverse(
        "attachments:upload_for_repair_order", kwargs={"repair_order_pk": repair_order_pk}
    )


def download_url(pk):
    return reverse("attachments:download", kwargs={"pk": pk})


def delete_url(pk):
    return reverse("attachments:delete", kwargs={"pk": pk})


def detail_url(pk):
    return reverse("repair_orders:detail", kwargs={"pk": pk})


# ---------------------------------------------------------------------------
# Form / model tests (no file storage needed)
# ---------------------------------------------------------------------------


class AttachmentFormTests(TestCase):
    def test_accepts_allowed_extensions_with_matching_content_types(self):
        cases = [
            ("jpg", JPEG_BYTES, "image/jpeg"),
            ("jpeg", JPEG_BYTES, "image/jpeg"),
            ("png", PNG_BYTES, "image/png"),
            ("gif", GIF_BYTES, "image/gif"),
            ("webp", WEBP_BYTES, "image/webp"),
            ("pdf", PDF_BYTES, "application/pdf"),
            ("txt", TXT_BYTES, "text/plain"),
            ("csv", CSV_BYTES, "text/csv"),
        ]
        for ext, content, content_type in cases:
            uploaded = make_upload(f"doc.{ext}", content, content_type)
            form = AttachmentForm(
                data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
            )
            self.assertTrue(form.is_valid(), f"Expected valid for .{ext}: {form.errors}")

    def test_accepts_csv_browser_content_type_variants(self):
        for content_type in ("text/csv", "application/vnd.ms-excel", "text/plain"):
            uploaded = make_upload("data.csv", CSV_BYTES, content_type)
            form = AttachmentForm(
                data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
            )
            self.assertTrue(form.is_valid(), f"Expected valid for {content_type}: {form.errors}")

    def test_accepts_blank_content_type(self):
        uploaded = make_upload("doc.pdf", PDF_BYTES, "")
        form = AttachmentForm(
            data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_disallowed_extension(self):
        for ext in ("exe", "sh", "zip", "docx", "html"):
            uploaded = make_upload(f"file.{ext}", b"content", "application/octet-stream")
            form = AttachmentForm(
                data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
            )
            self.assertFalse(form.is_valid(), f"Expected invalid for .{ext}")
            self.assertIn("file", form.errors)

    def test_rejects_oversized_file(self):
        uploaded = make_oversized_file()
        form = AttachmentForm(
            data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertIn("25 MB", form.errors["file"][0])

    def test_accepts_file_at_size_limit(self):
        content = b"x" * (25 * 1024 * 1024)
        uploaded = make_upload("doc.txt", content, "text/plain")
        form = AttachmentForm(
            data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_path_like_filenames(self):
        for name in ("../photo.jpg", "folder/photo.jpg", r"folder\photo.jpg"):
            uploaded = make_suspicious_upload(name)
            form = AttachmentForm(
                data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
            )
            self.assertFalse(form.is_valid(), f"Expected invalid for {name}")
            self.assertIn("path separators", form.errors["file"][0])

    def test_rejects_too_long_filename(self):
        uploaded = make_suspicious_upload(f"{'a' * 256}.jpg")
        form = AttachmentForm(
            data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("255 characters", form.errors["file"][0])

    def test_rejects_content_type_mismatch(self):
        cases = [
            ("doc.pdf", PDF_BYTES, "image/jpeg"),
            ("photo.jpg", JPEG_BYTES, "application/pdf"),
        ]
        for name, content, content_type in cases:
            uploaded = make_upload(name, content, content_type)
            form = AttachmentForm(
                data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
            )
            self.assertFalse(form.is_valid(), f"Expected invalid for {name}")
            self.assertIn("content type", form.errors["file"][0])

    def test_rejects_binary_magic_byte_mismatch(self):
        uploaded = make_upload("doc.pdf", JPEG_BYTES, "application/pdf")
        form = AttachmentForm(
            data={"category": Attachment.Category.OTHER}, files={"file": uploaded}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("content does not match", form.errors["file"][0])


# ---------------------------------------------------------------------------
# Upload view tests
# ---------------------------------------------------------------------------


class AttachmentUploadViewTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._media_settings = self.settings(MEDIA_ROOT=self._tmpdir)
        self._media_settings.__enter__()
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def tearDown(self):
        self._media_settings.__exit__(None, None, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(upload_url(self.ro.pk))
        self.assertRedirects(response, f"/accounts/login/?next={upload_url(self.ro.pk)}")

    def test_read_only_cannot_upload(self):
        user = make_user(username="ro_user", role_name=ROLE_READ_ONLY)
        self.client.force_login(user)
        response = self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.OTHER},
        )
        self.assertEqual(response.status_code, 403)

    def test_technician_cannot_upload(self):
        tech = make_user(username="tech", role_name=ROLE_TECHNICIAN)
        self.ro.assigned_to = tech
        self.ro.save()
        self.client.force_login(tech)
        response = self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.OTHER},
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_upload_and_redirects_to_detail(self):
        manager = make_user(username="mgr", role_name=ROLE_MANAGER)
        self.client.force_login(manager)
        response = self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.PHOTO},
        )
        self.assertRedirects(response, detail_url(self.ro.pk))
        self.assertEqual(Attachment.objects.filter(repair_order=self.ro).count(), 1)

    def test_upload_sets_metadata(self):
        manager = make_user(username="mgr2", role_name=ROLE_MANAGER)
        self.client.force_login(manager)
        uploaded = SimpleUploadedFile("receipt.pdf", PDF_BYTES, content_type="application/pdf")
        self.client.post(
            upload_url(self.ro.pk),
            data={
                "file": uploaded,
                "category": Attachment.Category.INVOICE,
                "description": "Final receipt",
            },
        )
        att = Attachment.objects.get(repair_order=self.ro)
        self.assertEqual(att.original_filename, "receipt.pdf")
        self.assertEqual(att.size_bytes, len(PDF_BYTES))
        self.assertEqual(att.description, "Final receipt")
        self.assertEqual(att.uploaded_by, manager)

    def test_front_desk_can_upload(self):
        fd = make_user(username="fd", role_name=ROLE_FRONT_DESK)
        self.client.force_login(fd)
        response = self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.OTHER},
        )
        self.assertRedirects(response, detail_url(self.ro.pk))
        self.assertEqual(Attachment.objects.filter(repair_order=self.ro).count(), 1)

    def test_attachment_appears_in_ro_detail(self):
        manager = make_user(username="mgr3", role_name=ROLE_MANAGER)
        self.client.force_login(manager)
        self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.PHOTO},
        )
        response = self.client.get(detail_url(self.ro.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn("photo.jpg", response.content.decode())

    def test_invalid_extension_shows_form_error(self):
        manager = make_user(username="mgr4", role_name=ROLE_MANAGER)
        self.client.force_login(manager)
        bad_file = SimpleUploadedFile("virus.exe", b"bad", content_type="application/octet-stream")
        response = self.client.post(
            upload_url(self.ro.pk),
            data={"file": bad_file, "category": Attachment.Category.OTHER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("not allowed", response.content.decode())
        self.assertEqual(Attachment.objects.count(), 0)

    def test_stored_path_remains_under_media_root_repair_order_directory(self):
        manager = make_user(username="mgr5", role_name=ROLE_MANAGER)
        self.client.force_login(manager)
        self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.PHOTO},
        )
        attachment = Attachment.objects.get(repair_order=self.ro)
        expected_dir = os.path.join(self._tmpdir, "repair_orders", str(self.ro.pk))

        self.assertEqual(os.path.commonpath([expected_dir, attachment.file.path]), expected_dir)


# ---------------------------------------------------------------------------
# Download view tests
# ---------------------------------------------------------------------------


class AttachmentDownloadViewTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._media_settings = self.settings(MEDIA_ROOT=self._tmpdir)
        self._media_settings.__enter__()
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.manager = make_user(username="mgr", role_name=ROLE_MANAGER)
        self.client.force_login(self.manager)
        self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.PHOTO},
        )
        self.attachment = Attachment.objects.get(repair_order=self.ro)

    def tearDown(self):
        self._media_settings.__exit__(None, None, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_unauthenticated_redirects(self):
        self.client.logout()
        response = self.client.get(download_url(self.attachment.pk))
        self.assertEqual(response.status_code, 302)

    def test_manager_can_download(self):
        response = self.client.get(download_url(self.attachment.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="photo.jpg"')

    def test_read_only_can_download(self):
        ro_user = make_user(username="ro_user", role_name=ROLE_READ_ONLY)
        self.client.force_login(ro_user)
        response = self.client.get(download_url(self.attachment.pk))
        self.assertEqual(response.status_code, 200)

    def test_assigned_technician_can_download(self):
        tech = make_user(username="tech", role_name=ROLE_TECHNICIAN)
        self.ro.assigned_to = tech
        self.ro.save()
        self.client.force_login(tech)
        response = self.client.get(download_url(self.attachment.pk))
        self.assertEqual(response.status_code, 200)

    def test_unassigned_technician_cannot_download(self):
        tech = make_user(username="tech2", role_name=ROLE_TECHNICIAN)
        self.client.force_login(tech)
        response = self.client.get(download_url(self.attachment.pk))
        self.assertEqual(response.status_code, 403)

    def test_missing_stored_file_returns_404(self):
        os.remove(self.attachment.file.path)

        response = self.client.get(download_url(self.attachment.pk))

        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Delete view tests
# ---------------------------------------------------------------------------


class AttachmentDeleteViewTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._media_settings = self.settings(MEDIA_ROOT=self._tmpdir)
        self._media_settings.__enter__()
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.manager = make_user(username="mgr", role_name=ROLE_MANAGER)
        self.client.force_login(self.manager)
        self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.PHOTO},
        )
        self.attachment = Attachment.objects.get(repair_order=self.ro)
        self.stored_path = self.attachment.file.path

    def tearDown(self):
        self._media_settings.__exit__(None, None, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_get_returns_405(self):
        response = self.client.get(delete_url(self.attachment.pk))
        self.assertEqual(response.status_code, 405)

    def test_manager_can_delete(self):
        response = self.client.post(delete_url(self.attachment.pk))
        self.assertRedirects(response, detail_url(self.ro.pk))
        self.assertFalse(Attachment.objects.filter(pk=self.attachment.pk).exists())
        self.assertFalse(os.path.exists(self.stored_path))

    def test_missing_stored_file_delete_removes_database_row(self):
        os.remove(self.stored_path)

        response = self.client.post(delete_url(self.attachment.pk))

        self.assertRedirects(response, detail_url(self.ro.pk))
        self.assertFalse(Attachment.objects.filter(pk=self.attachment.pk).exists())

    def test_front_desk_cannot_delete(self):
        fd = make_user(username="fd", role_name=ROLE_FRONT_DESK)
        self.client.force_login(fd)
        response = self.client.post(delete_url(self.attachment.pk))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Attachment.objects.filter(pk=self.attachment.pk).exists())

    def test_unauthenticated_redirects(self):
        self.client.logout()
        response = self.client.post(delete_url(self.attachment.pk))
        self.assertEqual(response.status_code, 302)

    def test_unauthorized_user_gets_403(self):
        ro_user = make_user(username="ro_user", role_name=ROLE_READ_ONLY)
        self.client.force_login(ro_user)
        response = self.client.post(delete_url(self.attachment.pk))
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# Repair order detail integration tests
# ---------------------------------------------------------------------------


class AttachmentRODetailIntegrationTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._media_settings = self.settings(MEDIA_ROOT=self._tmpdir)
        self._media_settings.__enter__()
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.manager = make_user(username="mgr", role_name=ROLE_MANAGER)

    def tearDown(self):
        self._media_settings.__exit__(None, None, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_attachment_list_appears_in_ro_detail(self):
        self.client.force_login(self.manager)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Attachments", response.content.decode())

    def test_upload_button_shown_for_manager(self):
        self.client.force_login(self.manager)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertIn("Add Attachment", response.content.decode())

    def test_upload_button_hidden_for_read_only(self):
        ro_user = make_user(username="ro_user", role_name=ROLE_READ_ONLY)
        self.client.force_login(ro_user)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotIn("Add Attachment", response.content.decode())

    def test_delete_button_shown_for_manager_when_attachment_exists(self):
        self.client.force_login(self.manager)
        self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.PHOTO},
        )
        response = self.client.get(detail_url(self.ro.pk))
        self.assertIn("Delete", response.content.decode())

    def test_delete_button_hidden_for_front_desk(self):
        self.client.force_login(self.manager)
        self.client.post(
            upload_url(self.ro.pk),
            data={"file": make_small_jpg(), "category": Attachment.Category.PHOTO},
        )
        fd = make_user(username="fd", role_name=ROLE_FRONT_DESK)
        self.client.force_login(fd)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotIn("attachments:delete", response.content.decode())
