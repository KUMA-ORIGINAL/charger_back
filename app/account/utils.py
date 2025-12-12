
def permission_callback_for_admin(request):
    if request.user.is_superuser:
        return True
    if request.user.is_anonymous:
        return False
    return False