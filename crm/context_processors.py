from django.conf import settings


def resort(request):
    return {"RESORT_NAME": settings.RESORT_NAME}
