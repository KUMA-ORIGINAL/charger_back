import json
from common.models import PageText  # замените на имя вашего приложения

# Открываем JSON
with open('fixtures/page_texts_ky.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

updated = 0
not_found = []

for key, text in data.items():
    # Обновляем только существующие объекты
    updated_count = PageText.objects.filter(key=key).update(text_ky=text)
    if updated_count:
        updated += 1
    else:
        not_found.append(key)

print(f'Обновлено записей: {updated}')
if not_found:
    print('Не найдены ключи:', not_found)
