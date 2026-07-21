from django.conf import settings


def shop_identity(request):
    return {
        "shop_identity": {
            "display_name": settings.SHOP_DISPLAY_NAME,
        }
    }
