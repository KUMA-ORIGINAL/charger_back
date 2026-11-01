# AGENTS.md — admin-ui (React-админка Charger)

Инструкции для агентов и разработчиков, работающих в `admin-ui/`. Бэкенд этой
админки — Django-приложение `app/staff/` в этом же репозитории.

## Что это

SPA-замена Django admin (`/admin/`) для сотрудников зарядной сети. Живёт по адресу **`/panel/`** того же
домена, что и бэкенд. Django admin остаётся рядом как запасной вариант; разделы
переезжают в React постепенно.

Главная идея: **экраны строятся из метаданных**. Бэкенд описывает модель классом
`StaffResource` (аналог `ModelAdmin`), отдаёт описание в `GET /api/staff/v1/meta/`,
а фронт по нему рисует меню, список, фильтры, форму, инлайны и действия.
Новый раздел обычно не требует кода на фронте.

## Стек

| Слой       | Технология                                                                           |
| ---------- | ------------------------------------------------------------------------------------ |
| Сборка     | Vite 8, React 19, TypeScript (strict)                                                |
| Маршруты   | TanStack Router, файловые маршруты в `src/routes/` (`routeTree.gen.ts` генерируется) |
| Данные     | TanStack Query 5                                                                     |
| Таблицы    | TanStack Table 8                                                                     |
| UI         | shadcn/ui (Radix) + Tailwind CSS 4, иконки lucide-react                              |
| Формы      | React Hook Form (+ Zod для форм с фиксированной схемой, например логина)             |
| API-клиент | Orval: типы и функции из OpenAPI staff-API (`src/shared/api/generated/`)             |
| Графики    | Recharts через `shared/ui/chart`                                                     |
| i18n       | i18next (пока только ru)                                                             |
| Качество   | Biome 2 (линтер и форматтер), Vitest + Testing Library + MSW, Playwright             |
| Пакеты     | pnpm (через `corepack pnpm …`)                                                       |

## Команды

```bash
corepack pnpm install
corepack pnpm dev            # http://localhost:5173/panel/, прокси на Django :8000
corepack pnpm typecheck
corepack pnpm lint           # biome check; автоисправление: corepack pnpm exec biome check --write .
corepack pnpm test           # vitest (unit + интеграция на MSW)
corepack pnpm build          # tsc + vite build → dist/
corepack pnpm e2e            # Playwright по живому бэкенду (см. «Тесты»)
corepack pnpm api:generate   # пересобрать клиент из openapi/staff.yaml
```

Бэкенд для разработки: `python app/manage.py runserver 127.0.0.1:8000` с
`DEBUG=1`, затем `python app/manage.py createsuperuser`.

## Структура

```
admin-ui/
  openapi/staff.yaml        схема staff-API (генерируется бэкендом, коммитится)
  orval.config.ts           генерация клиента
  e2e/                      Playwright-смоук
  src/
    main.tsx                точка входа
    app/                    провайдеры, QueryClient, роутер, глобальные стили
    routes/                 ТОНКИЕ файлы маршрутов: параметры, loader, вызов компонента фичи
      __root.tsx
      login.tsx
      _app.tsx              защищённый лейаут: проверка сессии и загрузка /meta/
      _app/index.tsx        дашборд
      _app/r/$resource/     список, new, $id (карточка) любого ресурса
    features/
      auth/                 сессия (meQuery, requireSession), страница входа
      layout/               сайдбар (из /meta/), палитра команд (Ctrl+K), лейаут
      dashboard/            дашборд
      resources/            движок ресурсов: api, meta, list-search, components/, fields/
    shared/
      api/http.ts           единственный fetch: cookie-сессия, CSRF, ApiError, файлы
      api/generated/        Orval — НЕ править руками
      ui/                   компоненты shadcn (свои правки допустимы, это наш код)
      lib/                  format (деньги, даты по Бишкеку), theme, utils (cn)
      i18n/
    test/                   setup Vitest, MSW-сервер, фикстуры, renderApp/signIn
```

Правила зависимостей: `routes → features → shared`. `shared` не импортирует
из `features`; фичи не импортируют друг из друга внутренности, кроме
публичных модулей (`features/resources/components/*`, `fields/value-view`,
`auth/session`). Маршрут содержит минимум логики, всё остальное — в фиче.

## Как устроены данные

- **Авторизация**: Django-сессия в httpOnly-cookie, общая с `/admin/`.
  Токены в браузере не храним. Перед входом вызываем `GET auth/csrf/`, дальше
  `http.ts` сам кладёт `X-CSRFToken` в POST/PATCH/DELETE. Маршрут `_app`
  проверяет сессию в `beforeLoad` (`requireSession`), без неё отправляет на `/login?redirect=…`.
- **Права решает бэкенд.** Фронт только прячет кнопки по `meta.permissions`
  и `meta.actions`; любую проверку дублировать на фронте не нужно и нельзя на неё полагаться.
- **Ответы staff-API в snake_case**, имена полей совпадают с полями модели и
  с `meta.fields[].name`. Не переводите их в camelCase.
- **Связи** приходят как `{id, label}`, уходят как id (или массив id).
  Варианты для выбора — `GET resources/<key>/lookup/<поле>/?search=&ids=`,
  уже отфильтрованные по правам пользователя.
- **Типизированный клиент (Orval)** — для эндпоинтов с фиксированной формой:
  auth, meta, dashboard. CRUD ресурсов — через `features/resources/api.ts`
  с общим типом `Row`, потому что форма строки задаётся `/meta/`, а не OpenAPI.
- **Кэш**: ключи ресурсов — `resourceKeys` в `features/resources/api.ts`;
  после изменения данных инвалидируйте `resourceKeys.all(key)`.
  `/meta/` кэшируется на всю сессию; при выходе `queryClient.clear()`.
- **Состояние списка живёт в URL**: `?page=2&ordering=-total_price&status=3&created_at__gte=2026-10-01`.
  Ключи кроме `page/page_size/search/ordering` — фильтры в синтаксисе API.
  Парсинг и обратное преобразование — `list-search.ts` (числа кладутся в URL
  числами, иначе роутер пишет `%223%22`).

- **Переключатель заведений**: суперпользователь сужает всю панель до одного
  заведения. Выбор хранится в `shared/lib/organization.ts` (localStorage) и уходит
  в каждый запрос заголовком `X-Organization`; бэкенд (`staff.resources.selected_organization`)
  учитывает его только у суперпользователя. После смены заведения запросы
  сбрасываются (`resetQueries`), профиль и `/meta/` — нет.
- **Переводы** (`*_ru`, `*_ky`, `*_en` из modeltranslation) форма сама собирает
  в одно поле с вкладками языков (`fields/translated-field.tsx`).
- **Подписи колонок и фильтров** короче `verbose_name` задаются на бэкенде:
  `labels = {"product_photo": "Фото"}` в `StaffResource`.
- **Фильтры**: первый «выбор» до 8 вариантов показывается быстрыми кнопками над
  таблицей (`QuickFilter`); выборы до 4 вариантов и «да/нет» в панели — кнопками,
  длиннее — селектом; у дат есть готовые периоды. Фильтр может идти через связи:
  `list_filter = ("transaction__order__spot",)` — параметр URL и API так и называется.
- **Умолчания**: поле с `default` в модели приходит в `/meta/` с `default`; форма
  создания начинается с него (новая скидка создаётся активной, а не выключенной).
- **Действия по объекту**: в карточке приходит `_actions` — какие detail-действия
  доступны именно этому объекту и с какой формой (`form`). Нет ключа — кнопку
  не показываем. В списке `_actions` нет (считать по строке дорого).
- **Вкладки над списком**: `list_tabs = "status"` в ресурсе (поле из `list_filter`
  с choices) — над таблицей вкладки «Все · Оформлен 12 · …», а ответ списка несёт
  `tab_counts` (с поиском и прочими фильтрами, без фильтра самой вкладки).
- **Цвета статусов**: `badges = {"status": {значение: тон}}`, тоны — `violet`,
  `amber`, `cyan`, `green`, `orange`, `red`, `gray` (старые `success`/`warning`/
  `danger`/`info` — их синонимы). Цвета — переменные `--tone-*` в `styles.css`.
- **Бейджи меню**: `/nav-badges/` — число проблем по разделам (непробитые чеки,
  холодильники, нет в наличии); меню спрашивает раз в минуту.
- **Скрытые ресурсы** (`hidden: true`) в меню и палитре не показываются: это
  строки инлайнов (модификаторы, дни графика), их правят из карточки родителя.
- **Диалоги внутри формы карточки** (действие, инлайн) рендерятся в портале, но
  события React всплывают по дереву компонентов: их `onSubmit` обязан делать
  `event.stopPropagation()`, иначе сохранится и карточка.

## Типовые задачи

### Добавить раздел (новую модель)

Только бэкенд. В `app/<приложение>/staff.py`:

```python
@staff_site.register(Banner)
class BannerResource(StaffResource):
    group = "Заведение"            # секция меню
    icon = "image"                 # имя иконки lucide — добавьте её в resource-icon.tsx
    scope = Scope(organization="organization")
    list_display = ("id", "title", "status", "banner")
    list_filter = ("status",)
    search_fields = ("title",)
```

Если нужна новая иконка, добавьте её в `features/resources/components/resource-icon.tsx`.
Права даются стандартными permissions Django (группа «Владелец»).

### Новый тип поля

1. Бэкенд: `app/staff/fields.py` (`FIELD_TYPES`, `model_field_type`) и, если
   меняется форма meta, сериализаторы в `app/staff/meta.py`.
2. Перегенерировать схему и клиент (см. ниже).
3. Фронт: отображение в `fields/value-view.tsx`, ввод и преобразования
   в `fields/field-input.tsx` (`toFormValue`/`toApiValue`), тест в `field-input.test.ts`.

### Действие над объектом или выбранными строками

Только бэкенд: метод с `@action(...)` в ресурсе. Фронт сам покажет кнопку,
спросит подтверждение (`confirm`), скачает файл или покажет сообщение
(`{message, level}`).
- Нужен ввод (точка для QR, причина) — `form=[{"name", "label", "type", "required", "choices"}]`
  или имя метода `(self, request, obj) -> поля`, если варианты зависят от объекта.
  Функция получает введённое последним аргументом, бэкенд проверяет его сам
  (`staff.views.clean_action_data`).
- Кнопка уместна не везде (повтор чека — только у «Не пробит») —
  `available="метод"`; запуск у неподходящего объекта бэкенд отклонит.

### Редактируемый инлайн

Зарегистрируйте модель строк скрытым ресурсом (`hidden = True`, свой `scope`)
и укажите его у инлайна: `Inline("modificators", "Модификаторы", (...), resource="modificator", fk="product")`.
Права, проверки и scope — этого ресурса; поле `fk` подставляется само.

### Ссылка на связанный список или экран

Вычисляемое поле `@display("…", type="link")` возвращает
`{"label", "resource", "filters"}` (список с фильтром), `{"label", "resource", "id"}`
(карточка) или `{"label", "to", "search"}` (особый экран), можно списком.
Ссылки на недоступные пользователю разделы фронт не показывает. Кнопки над
списком на особые экраны — `links = (("Подпись", "/путь", "иконка"),)` в ресурсе.

### Поле, которого нет в модели (пароль)

`extra_fields = {"new_password": {"label": …, "type": "password"}}` и
`save_extra(request, obj, values, created)` в ресурсе; проверка — в
`validate(request, data, instance)`. В ответах API такого поля нет.

### Права на отдельный объект, график, автообновление

- Модель можно менять, а конкретную строку — нет (владелец и чужой владелец):
  `can_modify(request, obj)` в ресурсе возвращает `True` или текст отказа (403).
- График во времени — `@display("…", type="series")`, значение
  `{"unit", "normal": [min, max], "points": [{"t", "v"}]}` (температура точки).
- Список, который меняется сам (заказы, телеметрия), — `auto_refresh = 30` (секунды).
- Строка списка и выгрузки — только `id` и колонки `list_display`: остальных полей
  формы, полей только карточки (таблицы, графики) и `inlines` в ней нет. Нужна
  колонка — добавьте поле в `list_display`.
- Связи из ответа (FK — `select_related`, M2M — `prefetch_related`) движок
  подгружает сам, и связи в колонках инлайнов тоже; число запросов не растёт с
  числом строк — это проверяет `staff/tests/test_queries.py`.
- Значение зависит от того, что видит пользователь (остатки только его точек), —
  `@display(..., with_request=True)`, метод получает `(obj, request)`.
- Дорогие аннотации для колонок (остаток, последняя температура) — в
  `annotate_rows(request, qs)`, а не в `get_queryset`: так они считаются только
  в списке, карточке и выгрузке раздела, а не в выпадашках связей и на дашборде.
- Подпись объекта в связях короче `__str__` — `label_for(self, obj)` в ресурсе
  (сотрудник — ФИО или телефон вместо «None - …»).

### Журнал и сессия

- Создание, правка (только реально изменённые поля), удаление и запуск
  действий из панели пишутся в `LogEntry` Django (`staff/audit.py`) — история
  объекта в /admin/ видит и правки из панели. Скачивания файлов не пишутся.
  Раздел «Журнал действий» — только суперпользователю.
- Ответ 401/403 посреди работы: `checkSessionAfter` перепроверяет профиль; если
  сессии нет — `queryClient.clear()` и вход с возвратом на ту же страницу.

### Особый экран вместо generic

Сделайте компонент в `features/<фича>/` и отдельный файловый маршрут
(например `routes/_app/spots/$id.tsx`). Generic-маршрут `r/$resource` не
трогайте. Расширяйте движок, только если поведение нужно многим ресурсам.

### Изменился API бэкенда

```bash
python app/manage.py staff_openapi --file admin-ui/openapi/staff.yaml
cd admin-ui && corepack pnpm api:generate && corepack pnpm typecheck
```
Коммитьте `openapi/staff.yaml` вместе с `src/shared/api/generated/`.

## Соглашения

- Импорты через алиас `@/…`. Порядок импортов и форматирование — Biome, не спорить с ним.
- Тексты интерфейса — на русском. Строки для i18n-словаря держим в
  `shared/i18n/ru.ts`, когда текст переиспользуется; разовые подписи допустимы прямо в JSX.
- Деньги — только `formatMoney` («1 020 сом»), даты — `formatDate`/`formatDateTime`
  (часовой пояс Asia/Bishkek, а не браузера).
- Комментарии по-русски и объясняют «почему», а не «что».
- Компоненты — функции с именованным экспортом, без default export
  (кроме файлов маршрутов, где экспорт `Route` требует роутер).
- Никаких `localStorage` для данных и токенов, только для мелких
  предпочтений (тема).
- **CSP на проде**: `script-src 'self'`. Нельзя inline-скрипты, `eval`,
  внешние CDN, шрифты и картинки с чужих доменов. Шрифты — через `@fontsource`.
  Поэтому тема сделана своим провайдером (`shared/lib/theme.tsx`), а не next-themes.
- Доступность: у полей есть `<Label htmlFor>`, у иконок-кнопок `aria-label`;
  тесты ищут элементы по ролям и подписям, это заодно проверяет a11y.
- Мобильная вёрстка: ключевые экраны (дашборд, точки, карточки) должны
  работать на ширине 375px; таблицы прокручиваются горизонтально.

## Тесты

- **Unit/интеграция (Vitest + MSW)**: `*.test.ts(x)` рядом с кодом. MSW-сервер
  общий (`src/test/msw-server.ts`), непойманный запрос — ошибка теста.
  Интеграционные тесты рендерят всё приложение с memory-историей (`src/app/app.test.tsx`)
  — так проверяются и маршруты, и данные.
- **E2E (Playwright)**: `e2e/smoke.spec.ts` против живого бэкенда (суперпользователь в `E2E_PHONE`/`E2E_PASSWORD`, в базе станция, сессия и платёж).
  Вход один раз в `e2e/auth.setup.ts`, сессия переиспользуется (`e2e/.auth/`,
  не коммитится): параллельные входы одним номером упрутся в защиту от перебора.
  Перед первым запуском: `corepack pnpm exec playwright install chromium`
  или `E2E_CHANNEL=msedge` / `chrome` для системного браузера.
  Другой стенд — `E2E_BASE_URL`, `E2E_PHONE`, `E2E_PASSWORD`.
- Бэкенд staff-API: `python app/manage.py test staff -t . --settings=config.test_settings`
  (из `app/`). Там проверены изоляция заведений, права и действия.

Готово = `typecheck`, `lint`, `test`, `build` зелёные; при изменениях API
перегенерированы схема и клиент; новый тип поля или действие покрыты тестом.

## Деплой

`nginx/Dockerfile` собирает `admin-ui` (стадия `node:22-alpine`) и кладёт `dist/`
в `/usr/share/nginx/panel`. nginx отдаёт `/panel/assets/*` с вечным кэшем,
остальные `/panel/*` — `index.html` (SPA) без кэша. Контекст сборки nginx — корень
репозитория (`docker-compose.prod.yml`), лишнее отсекает `.dockerignore`.
`vite.config.ts` → `base: '/panel/'`, роутер → `basepath: '/panel'`; их нужно менять вместе.

## Подводные камни

- `routeTree.gen.ts` генерирует плагин роутера при `dev`/`build`. Если
  `typecheck` ругается на маршруты, сначала запустите `corepack pnpm build` или `dev`.
- `router.state.location.pathname` не содержит `/panel` (basepath).
- Параметр `$id` в маршруте карточки — число (`params.parse`); в `Link` передавайте number.
- В Orval-хуки не передавайте `useSuspenseQuery`: их `queryFn` типизирован
  со `skipToken`. Для suspense делайте свои `queryOptions` (см. `meQuery`, `metaQuery`).
- Ошибки валидации DRF приходят как `{field: [msg]}`; `ApiError.fieldErrors`
  раскладывает их, форма показывает под полями.
- Сетка в одну колонку — `grid-cols-[minmax(0,1fr)]`, а не просто `grid`: иначе
  неявная колонка растягивается по самой широкой таблице и страница едет вбок.
- Windows: `admin-ui/.gitattributes` держит LF — Biome на CRLF ругается на каждый файл.
  В клоне, сделанном до этого файла, файлы ещё с CRLF: `corepack pnpm exec biome format --write .`
  переведёт их в LF, git разницы не увидит.
