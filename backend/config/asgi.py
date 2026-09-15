import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

from apps.communication.auth import JWTAuthMiddleware
from apps.communication.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
	{
		"http": django_asgi_app,
		"websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
	}
)
