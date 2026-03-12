from .settings import *  # noqa


# Debug toolbar is not compatible with Django test mode.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]
MIDDLEWARE = [mw for mw in MIDDLEWARE if "debug_toolbar" not in mw]

# Channels tests should not depend on Redis.
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}
