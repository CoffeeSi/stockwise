# HTTP API StockWise

Состояние контракта после реализации P0–P2. Исполняемый контракт — `/openapi.json`; маршруты подключены в `backend/infrastructure/api/main.py`.

## Доступ и ошибки

Все бизнес-маршруты требуют проверенный Bearer JWT. Next.js хранит его в HttpOnly cookie и добавляет заголовок на сервере; токен не возвращается браузерному JavaScript и не сохраняется в localStorage. Открыты регистрация, вход и `/health`, `/health/db`, `/api/v1/health`.

`viewer` читает результаты, рассчитывает превью и скачивает уже созданный экспорт. `buyer` и `admin` импортируют, запускают расчёты, корректируют, принимают рекомендации, создают, утверждают и экспортируют заказы. Только `admin` назначает роли. Автор изменений берётся из проверенного пользователя. Произвольные `user_id` в теле или заголовке не принимаются.

Ошибки: `{ detail: { code, message, ... }, request_id }`. Статусы: 401 — требуется вход; 403 — недостаточно прав; 404 — ресурс отсутствует; 409 — конфликт статуса, версии, выбора или ключа идемпотентности; 422 — входные данные или условия поставки неверны; 503 — сервис/БД недоступны. Ошибка массовой операции содержит конфликтующие `recommendation_ids`; ни одна строка операции не сохраняется частично.

Количество и деньги сериализуются десятичными строками. Неизвестные цены/суммы/остатки наблюдений — `null`, а не 0. JSON-команды запрещают лишние поля.

## Учётные записи

- POST `/api/auth/register`: `username`, `display_name`, `password` (12–256 символов). Создаёт только `viewer`, ответ 201 с ID, логином, именем и ролью. Поле role не принимается.
- POST `/api/auth/login`: `username`, `password`; FastAPI возвращает access_token, token_type, expires_in. BFF устанавливает cookie, в браузер возвращает только тип и срок сессии.
- GET `/api/auth/me`: текущий активный пользователь.
- POST `/api/auth/logout`: отзывает все текущие токены пользователя повышением token_version; BFF удаляет cookie.
- GET `/api/auth/users?limit=50&offset=0`: список сотрудников, только admin.
- POST `/api/auth/users`: администратор создаёт покупателя по username/display_name/password.
- PATCH `/api/auth/users/{id}/role`: `{role: viewer|buyer|admin}`; только admin, изменение собственной роли запрещено.

Настройка первого администратора: [authentication.md](authentication.md).

## Импорт и фоновая обработка

POST `/api/imports` принимает multipart `source_type` и `file` (.xlsx, не более 25 МиБ). Типы: sales, monthly_sales, inventory, stockout, in_transit, seasonality, supplier_terms, growth, material_requirements. Ответ 202 содержит сохранённый batch_id, статус pending, checksum и progress.

GET `/api/imports/{batch_id}` возвращает pending/processing/completed/failed, число строк, безопасные validation_errors и progress `{stage, processed_rows, total_rows}`. Стадии: uploaded, validating, persisting, completed. До завершения атомарной записи processed_rows равен 0; обработанные строки считаются после commit. Процент передачи HTTP относится только к загрузке файла.

Импорт распознаёт шесть шаблонов ИЭК: транзакционные продажи, помесячные продажи, помесячные остатки, товары в пути, сезонность и MOQ. Колонки с месяцами и заказами преобразуются в отдельные записи; строки заголовков и «Итого» не импортируются. В месячных продажах, остатках и товарах в пути исходный склад отсутствует, поэтому записи получают код `__ALL_WAREHOUSES__` («Все склады (агрегированные данные)»). Общая сезонность получает категорию `__ALL_PRODUCTS__` и применяется только при отсутствии более точного коэффициента. Эти агрегаты нельзя трактовать как данные конкретного склада.

Если известные заголовки не подошли, OpenAI по `OPENAI_API_KEY` предлагает соответствие столбцов и строку заголовка. Запрос содержит не более шести предполагаемых строк заголовков, типы трёх соседних строк и до двух сокращённых примеров на столбец; полная таблица и клиентские идентификаторы в модель не передаются. Ответ модели проверяется по существующим колонкам и типам перед импортом. Без доступного OpenAI нестандартный файл получает ошибку валидации, а известные шаблоны продолжают обрабатываться локально. В MOQ ИЭК строки с отсутствующим значением `#N/A` пропускаются; успешный статус содержит `warnings: [{code: "missing_moq", count}]`.

Необработанный Excel временно хранится в защищённом spool, а не в БД. После успешной/неуспешной обработки временный файл удаляется. Проверка структуры и приватности выполняется до сохранения фактов. Исходные клиентские ФИО, телефоны и email запрещены. При ошибке Excel сохраняется только безопасная диагностика партии.

## Расчёты

POST `/api/calculation-runs` требует заголовок `Idempotency-Key` (1–128 символов) и тело demand_source transactions|monthly_sales, horizon_days>0, необязательные warehouse_id/category_id, budget_limit>0 (decimal-string), currency (три заглавные буквы). Ответ 202 — сохранённый pending запуск. Повтор того же ключа и тела тем же пользователем возвращает тот же run_id; изменённое тело с прежним ключом — 409.

Завершение импорта не создаёт расчёт: закупщик запускает его отдельной командой после загрузки нужных источников. При отсутствии условий поставщика для товара запуск сохраняется со статусом failed и кодом `supplier_terms_missing`; после загрузки MOQ требуется новый запуск.

GET `/api/calculation-runs` фильтрует status, warehouse_id, category_id, limit=1..100, offset>=0. Сортировка started_at desc, ID как стабильный дополнительный ключ. Ответ `{items,total,limit,offset}`. UI находит последний completed запуск этим маршрутом.

GET `/api/calculation-runs/{id}` отдаёт pending/running/completed/failed, параметры, снимок ID импортов, версию алгоритма, количество рекомендаций, ошибку и реальный сохранённый progress `{phase,completed,total}`. Текущий прогресс отражает стадии целого запуска (0/1 до сохранения, 1/1 после), а не предполагаемый процент SKU.

Задания хранятся в background_jobs (миграция 0003). Worker использует возобновляемую аренду и токен владения: прерванная задача подхватывается после истечения аренды, устаревший исполнитель не может записать результат. Снимок импортов и условий поставщиков фиксируется перед возвратом 202. Завершённые результаты не пересчитываются при чтении.

При бюджете применяется `risk_priority_whole_pack/v1`: сначала больший риск, затем стабильный порядок поставщика/товара/ID; выделяется доступное количество целых упаковок, MOQ соблюдается. Это воспроизводимая жадная эвристика. Неизвестные цены или разные валюты дают failed с безопасным кодом budget_price_missing/budget_currency_mismatch/budget_currency_missing. В parameters и верхнем уровне ответа сохранены budget_limit, allocated_amount, unmet_need_amount, optimization_method. Каждый запуск независим.

## Рекомендации и заказы

GET `/api/calculation-runs/{run_id}/recommendations`: supplier_id, warehouse_id, category_id, urgency, status, search по SKU/названию; sort_by risk_score|recommended_quantity|created_at|urgency|product_id, descending; limit=1..500, offset>=0. Поиск и фильтры применяются до пагинации. Ответ `{items,total,limit,offset}`.

Строка содержит все поля RecommendationResponse, SKU, наименование, единицу, названия поставщика/склада/категории, category_id и nullable unit_price/currency/estimated_total. Цена берётся только из supplier_terms_snapshot данного запуска; старые результаты без снимка не подменяются текущей ценой.

GET `/api/recommendations/{id}/explain`: сохранённые компоненты, формула, прогноз, аномалии этой позиции и evidence. При бюджетном ограничении components.budget_allocation показывает количество до и после выделения бюджета.

PATCH `/api/recommendations/{id}`: new_quantity>=0, reason (1–2000), version>0. Допустим 0 либо количество не меньше MOQ и кратное package_size. Нарушение — 422 с moq/package_size; округление на сервере не выполняется. Изменение сохраняет историю, автора, время и новую версию, статус adjusted.

POST `/api/recommendations/{id}/accept`: version. POST `/api/recommendations/bulk/accept`: calculation_run_id и непустой items[{recommendation_id,version}] до 500 уникальных ID. Проверяются принадлежность завершённому запуску, suggested/adjusted, версии, положительное количество, MOQ и упаковка. Сохраняются автор/время принятия. Массовая операция атомарна.

POST `/api/orders/bulk`: calculation_run_id и непустой recommendation_ids до 500 уникальных ID. Только выбранные accepted позиции одного запуска; группировка по поставщику и складу. Ответ 201 `{orders,consumed_recommendation_ids}`. Повторно включить позицию невозможно. Конфликт любой строки отменяет весь набор.

POST `/api/orders`: `{calculation_run_id}` — отдельная команда «все принятые, ещё не заказанные строки». Возвращает массив новых черновиков, повтор после расходования всех строк — пустой массив.

GET `/api/orders`: calculation_run_id, supplier_id, status draft|approved|exported|cancelled, limit=1..100, offset. Ответ `{items,total,limit,offset}` с названиями, количеством строк и nullable total_amount/currency. Смешанные валюты или неполные цены не выдаются за известный итог.

GET `/api/orders/{id}` — сохранённый заказ и строки. POST `/{id}/approve` — явное утверждение сотрудником. POST `/{id}/export` создаёт XLSX утверждённого заказа и возвращает метаданные. GET `/{id}/export` скачивает уже готовый Blob без изменения состояния. Отправки поставщику нет.

## Справочники, аналитика и превью

GET `/api/v1/suppliers`: active_only=true, search, limit=1..500, offset; ответ `{items,total,limit,offset}`. GET `/api/v1/warehouses` и `/api/v1/categories`: active_only/search; ответ `{items}`. Элементы id/code/name/is_active, категория также parent_id.

GET `/api/recommendations/{id}/history?months=24` — месяцы продаж и остатков из точного набора импортов запуска. GET `/api/v1/analytics/outliers`, `/demand-series`, `/abc-xyz` требуют calculation_run_id; доступны фильтры и метаданные методов. Подробности и ограничения окна: [analytics-api.md](analytics-api.md). Пустые/недоступные данные явно показаны в интерфейсе.

POST `/api/v1/scenarios/preview`: base_run_id завершённого расчёта; growth_multiplier>0, service_level (0,1], supplier_delay_days>=0, include_anomalies, budget_limit>0. Ответ is_preview=true, assumptions, totals, items, method и limitations. Использует сохранённый прогноз, запасы и цены. Изменений заказов/запуска нет. Метод `saved_forecast_linear_safety/v1` линейно масштабирует страховой запас от базовых 0.95; это предположение сценария, а не статистическая гарантия уровня сервиса. Превью не имеет команды утверждения.

AI-маршруты: POST `/api/v1/ai/sku-analysis`, `/supplier-summary`, `/supplier-letter`. Старое демонстрационное `/api/v1/procurement/*` не подключено и не используется UI.
