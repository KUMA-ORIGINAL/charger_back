# import io
#
# import cv2
# import numpy as np
# from PIL import Image
# from django.contrib.auth import get_user_model
# from django.db.models import F
#
# User = get_user_model()
#
#
# def handle_referral(user, referral_code):
#     if referral_code and not user.inviter:
#         if str(user.id) == str(referral_code):
#             raise ValueError("Вы не можете указать свой собственный код.")
#         try:
#             inviter = User.objects.get(id=referral_code)
#             user.inviter = inviter
#             user.save(update_fields=["inviter"])
#             inviter.agents_count = F("agents_count") + 1
#             inviter.save(update_fields=["agents_count"])
#         except User.DoesNotExist:
#             raise ValueError("Реферальный код не найден.")
#
#
# def crop_face(input_file):
#     """
#     input_file: Django File object or file-like object
#     Returns: BytesIO with JPEG face or None
#     """
#     try:
#         # Открываем изображение через PIL
#         img = Image.open(input_file)
#         if img.mode in ('RGBA', 'LA', 'P'):
#             white_bg = Image.new('RGB', img.size, (255, 255, 255))
#             if img.mode == 'P':
#                 img = img.convert('RGBA')
#             white_bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
#             img = white_bg
#         else:
#             img = img.convert('RGB')
#
#         cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
#         gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
#
#         face_cascade = cv2.CascadeClassifier(
#             cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
#         )
#         faces = face_cascade.detectMultiScale(gray, 1.1, 5)
#         if len(faces) == 0:
#             # return None
#
#         x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
#         pad = int(w * 0.2)
#         x1 = max(0, x - pad)
#         y1 = max(0, y - pad)
#         x2 = min(img.width, x + w + pad)
#         y2 = min(img.height, y + h + pad)
#         cropped = img.crop((x1, y1, x2, y2))
#
#         size = max(cropped.size)
#         square = Image.new('RGB', (size, size), (255, 255, 255))
#         paste_x = (size - cropped.width) // 2
#         paste_y = (size - cropped.height) // 2
#         square.paste(cropped, (paste_x, paste_y))
#         result = square.resize((300, 300), Image.Resampling.LANCZOS)
#
#         # Сохраняем в BytesIO
#         output = io.BytesIO()
#         result.save(output, format="JPEG", quality=95)
#         output.seek(0)
#         return output
#     except Exception as e:
#         # Логировать ошибку!
#         import logging
#         logging.exception("Face crop error: %s", e)
#         return None