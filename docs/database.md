# Проектирование базы данных

## 1. Назначение

База данных хранит нормализованные данные из входных Excel-файлов, параметры и результаты запусков расчета, рекомендации по пополнению, историю ручных корректировок и утвержденные заказы.

Главные требования к модели:

- исходные данные не изменяются алгоритмом расчета;
- каждый результат связан с конкретным запуском и набором импортов;
- завершенный расчет можно воспроизвести и объяснить;
- рассчитанное и вручную измененное количество не смешиваются;
- заказ нельзя считать утвержденным без явного действия пользователя;
- идентификаторы клиентов хранятся только в обезличенном виде.

Основная СУБД — PostgreSQL. SQLite разрешен только для упрощенного локального демо и не является целевой СУБД.

## 2. Общие соглашения

- Первичные ключи: `UUID`.
- Дата и время: `TIMESTAMPTZ`, хранение в UTC.
- Календарная дата без времени: `DATE`.
- Количество и деньги: `NUMERIC(18, 4)`, не `FLOAT`.
- Коэффициенты и оценки: `NUMERIC(12, 6)`.
- Валюта: код ISO 4217 в `VARCHAR(3)`.
- Все внешние ключи индексируются.
- Бизнес-статусы хранятся как `VARCHAR` с обязательным `CHECK`. Это защищает от опечаток на уровне БД так же, как PostgreSQL `ENUM`, но проще расширяется миграциями и сохраняет совместимость с SQLite для локального демо. В application-коде этим полям должны соответствовать Python Enum. Переход на PostgreSQL `ENUM` допустим позднее, если набор статусов стабилизирован и проект окончательно отказался от SQLite.
- Физическое удаление записей, участвовавших в расчете или заказе, запрещено. Для справочников используется `is_active`.
- `created_at` обязателен для изменяемых и аудируемых сущностей; для изменяемых записей также используется `updated_at`.

## 3. Связи верхнего уровня

```text
Category 1 ── N Product
Product  N ── M Supplier          через SupplierProduct
Product  1 ── N SalesTransaction
Product  1 ── N InventorySnapshot
Product  1 ── N StockoutPeriod
Product  1 ── N InTransitItem

ImportBatch     N ── M CalculationRun   через CalculationRunImport
CalculationRun  1 ── N DemandForecast
CalculationRun  1 ── N DetectedAnomaly
CalculationRun  1 ── N Recommendation

Recommendation  1 ── N RecommendationAdjustment
PurchaseOrder   1 ── N PurchaseOrderItem
Recommendation  1 ── 0..1 PurchaseOrderItem
PurchaseOrder   1 ── N OrderExport
```

## 4. Пользователи и справочники

### `users`

Минимальный справочник пользователей для аудита действий. Полноценная система авторизации может быть подключена позднее.

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `external_id` | VARCHAR(255) | UNIQUE, NOT NULL |
| `display_name` | VARCHAR(255) | NOT NULL |
| `role` | VARCHAR(32) | CHECK: `buyer`, `admin`, `viewer` |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |
| `created_at` | TIMESTAMPTZ | NOT NULL |

### `categories`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `parent_id` | UUID | FK → `categories.id`, NULL для корня |
| `code` | VARCHAR(100) | UNIQUE, NOT NULL |
| `name` | VARCHAR(255) | NOT NULL |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |

### `products`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `sku` | VARCHAR(100) | UNIQUE, NOT NULL |
| `name` | VARCHAR(500) | NOT NULL |
| `category_id` | UUID | FK → `categories.id`, NULL допустим при неполном импорте |
| `unit` | VARCHAR(32) | NOT NULL |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

### `warehouses`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `code` | VARCHAR(100) | UNIQUE, NOT NULL |
| `name` | VARCHAR(255) | NOT NULL |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |

### `suppliers`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `code` | VARCHAR(100) | UNIQUE, NOT NULL |
| `name` | VARCHAR(255) | NOT NULL |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |
| `created_at` | TIMESTAMPTZ | NOT NULL |

### `supplier_products`

Условия поставки конкретного товара конкретным поставщиком.

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `supplier_id` | UUID | FK → `suppliers.id`, NOT NULL |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `moq` | NUMERIC(18,4) | NOT NULL, CHECK > 0 |
| `package_size` | NUMERIC(18,4) | NOT NULL, DEFAULT 1, CHECK > 0 |
| `lead_time_days` | INTEGER | NOT NULL, CHECK >= 0 |
| `purchase_price` | NUMERIC(18,4) | NULL, CHECK >= 0 |
| `currency` | VARCHAR(3) | NULL |
| `priority` | INTEGER | NOT NULL, DEFAULT 100 |
| `is_primary` | BOOLEAN | NOT NULL, DEFAULT false |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |

Ограничения:

- `UNIQUE(supplier_id, product_id)`;
- не более одного активного `is_primary = true` поставщика на товар — частичный уникальный индекс.

## 5. Импорт и исходные факты

### `import_batches`

Одна запись соответствует одной попытке импорта одного файла.

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `source_type` | VARCHAR(50) | NOT NULL |
| `file_name` | VARCHAR(500) | NOT NULL |
| `file_checksum` | VARCHAR(64) | NOT NULL |
| `status` | VARCHAR(20) | CHECK: `pending`, `processing`, `completed`, `failed` |
| `row_count` | INTEGER | NOT NULL, DEFAULT 0 |
| `imported_by` | UUID | FK → `users.id`, NOT NULL |
| `imported_at` | TIMESTAMPTZ | NOT NULL |
| `error_details` | JSONB | NULL |

`source_type`: `sales`, `monthly_sales`, `inventory`, `stockout`, `in_transit`, `seasonality`, `supplier_terms`, `growth`, `material_requirements`.

Обязательная защита от повторной загрузки успешно обработанного файла — частичный уникальный индекс по контрольной сумме:

```sql
CREATE UNIQUE INDEX uq_import_batches_completed_checksum
    ON import_batches (file_checksum)
    WHERE status = 'completed';
```

Неуспешный импорт можно повторить. Перед началом обработки application-слой также должен проверить наличие завершенного импорта с тем же хэшем и вернуть понятную ошибку, а не доводить операцию до ошибки уникальности. Индекс остается последней защитой от двух одновременных загрузок одного файла.

### `sales_transactions`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `import_batch_id` | UUID | FK → `import_batches.id`, NOT NULL |
| `source_row_number` | INTEGER | NOT NULL |
| `external_document_number` | VARCHAR(255) | NULL |
| `sold_at` | TIMESTAMPTZ | NOT NULL |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NOT NULL |
| `anonymous_customer_id` | VARCHAR(255) | NULL |
| `transaction_type` | VARCHAR(20) | NOT NULL, CHECK: `sale`, `return` |
| `original_transaction_id` | UUID | self FK → `sales_transactions.id`, NULL |
| `quantity` | NUMERIC(18,4) | NOT NULL |
| `unit_price` | NUMERIC(18,4) | NULL, CHECK >= 0 |
| `total_amount` | NUMERIC(18,4) | NULL |

Правила нормализации продаж и возвратов:

- обычная продажа хранится как `transaction_type = 'sale'` и `quantity > 0`;
- возврат хранится как `transaction_type = 'return'` и `quantity < 0`;
- если исходный файл передает возврат положительным числом или отдельным видом документа, импортер обязан нормализовать знак;
- если известна исходная продажа, возврат ссылается на нее через `original_transaction_id`;
- `original_transaction_id` разрешен только для `return` и должен ссылаться на запись типа `sale`;
- возврат не является новым отрицательным спросом и не участвует в поиске крупных заказов как отдельная продажа.

Проверка знака и типа:

```sql
CHECK (
    (transaction_type = 'sale' AND quantity > 0)
    OR
    (transaction_type = 'return' AND quantity < 0)
)
```

Ссылку на запись типа `sale` невозможно полностью проверить обычным `CHECK`; это правило контролируется application/domain-слоем или constraint trigger в PostgreSQL.

Правила подготовки спроса для расчета:

1. Связанный возврат уменьшает количество исходной продажи и относится к периоду исходной продажи, даже если физически возврат проведен позднее.
2. Несвязанные возвраты агрегируются отдельно по `product_id + warehouse_id + период` и уменьшают валовые продажи этого периода.
3. Итоговый спрос периода не может стать отрицательным: после применения несвязанных возвратов используется `max(0, gross_sales + returns)`.
4. Размер корректировки возвратами сохраняется в `demand_forecasts.return_adjustment` и в `details`.
5. Метод обработки возвратов фиксируется в `calculation_runs.parameters.return_handling` для воспроизводимости.

Индексы:

- `(product_id, warehouse_id, sold_at)`;
- `(anonymous_customer_id, sold_at)` при наличии клиентского идентификатора;
- `(original_transaction_id)` для поиска связанной продажи;
- `(import_batch_id, source_row_number)` UNIQUE.

### `monthly_sales`

Агрегированная помесячная история хранится отдельно от транзакционных продаж, поскольку у нее нет документа и клиента и ее нельзя смешивать с отдельными продажами без риска двойного учета.

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `import_batch_id` | UUID | FK → `import_batches.id`, NOT NULL |
| `source_row_number` | INTEGER | NOT NULL |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NULL, если исходный отчет не содержит склад |
| `period_start` | DATE | NOT NULL |
| `period_end` | DATE | NOT NULL |
| `quantity` | NUMERIC(18,4) | NOT NULL |

Ограничения и индексы:

- `UNIQUE(import_batch_id, source_row_number)`;
- `CHECK(period_end >= period_start)`;
- индекс `(product_id, warehouse_id, period_start, period_end)`.

Транзакционные и агрегированные продажи нельзя суммировать между собой за один период. Алгоритм обязан зафиксировать выбранный источник в `calculation_runs.parameters`: транзакции являются приоритетным источником для очистки выбросов, а агрегированные данные используются как fallback и для проверки сезонности/тренда.

### `inventory_snapshots`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `import_batch_id` | UUID | FK → `import_batches.id`, NOT NULL |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NOT NULL |
| `snapshot_at` | TIMESTAMPTZ | NOT NULL |
| `quantity_on_hand` | NUMERIC(18,4) | NOT NULL |
| `quantity_reserved` | NUMERIC(18,4) | NOT NULL, DEFAULT 0 |
| `quantity_available` | NUMERIC(18,4) | NOT NULL |

Ограничение: `UNIQUE(import_batch_id, product_id, warehouse_id, snapshot_at)`.

### `stockout_periods`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `import_batch_id` | UUID | FK → `import_batches.id`, NULL для вычисленного периода |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NOT NULL |
| `started_at` | TIMESTAMPTZ | NOT NULL |
| `ended_at` | TIMESTAMPTZ | NULL для продолжающегося stockout |
| `source` | VARCHAR(20) | CHECK: `imported`, `inferred`, `manual` |
| `confidence` | NUMERIC(5,4) | NULL, CHECK BETWEEN 0 AND 1 |

Проверка: `ended_at IS NULL OR ended_at > started_at`.

### `in_transit_items`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `import_batch_id` | UUID | FK → `import_batches.id`, NOT NULL |
| `external_order_number` | VARCHAR(255) | NULL |
| `supplier_id` | UUID | FK → `suppliers.id`, NOT NULL |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `destination_warehouse_id` | UUID | FK → `warehouses.id`, NOT NULL |
| `quantity` | NUMERIC(18,4) | NOT NULL, CHECK > 0 |
| `expected_at` | TIMESTAMPTZ | NULL |
| `status` | VARCHAR(20) | CHECK: `planned`, `in_transit`, `received`, `cancelled` |

В расчете участвуют только `planned` и `in_transit` на дату среза запуска.

### `seasonality_coefficients`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `import_batch_id` | UUID | FK → `import_batches.id`, NOT NULL |
| `product_id` | UUID | FK → `products.id`, NULL |
| `category_id` | UUID | FK → `categories.id`, NULL |
| `month` | SMALLINT | CHECK BETWEEN 1 AND 12 |
| `coefficient` | NUMERIC(12,6) | NOT NULL, CHECK > 0 |
| `valid_from` | DATE | NOT NULL |
| `valid_to` | DATE | NULL |
| `version` | INTEGER | NOT NULL |

Проверка: задан ровно один уровень — `product_id` или `category_id`. Коэффициент товара имеет приоритет над коэффициентом категории.

### `growth_assumptions`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `import_batch_id` | UUID | FK → `import_batches.id`, NULL для вычисленного значения |
| `product_id` | UUID | FK → `products.id`, NULL |
| `category_id` | UUID | FK → `categories.id`, NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NULL |
| `growth_rate` | NUMERIC(12,6) | NOT NULL |
| `valid_from` | DATE | NOT NULL |
| `valid_to` | DATE | NULL |
| `source` | VARCHAR(20) | CHECK: `calculated`, `imported`, `manual` |

Проверка: задан `product_id` или `category_id`. Значение `0.08` означает рост на 8%.

### `material_requirements`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `import_batch_id` | UUID | FK → `import_batches.id`, NOT NULL |
| `external_document_number` | VARCHAR(255) | NULL |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NOT NULL |
| `required_quantity` | NUMERIC(18,4) | NOT NULL, CHECK > 0 |
| `required_at` | TIMESTAMPTZ | NOT NULL |
| `status` | VARCHAR(20) | CHECK: `planned`, `fulfilled`, `cancelled` |

## 6. Запуски расчета и аналитика

### `calculation_runs`

Каждое нажатие «Запустить расчет» создает новую запись. Завершенный запуск неизменяем.

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `status` | VARCHAR(20) | CHECK: `pending`, `running`, `completed`, `failed` |
| `started_by` | UUID | FK → `users.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NULL означает все склады |
| `category_id` | UUID | FK → `categories.id`, NULL означает все категории |
| `forecast_horizon_days` | INTEGER | NOT NULL, CHECK > 0 |
| `source_cutoff_at` | TIMESTAMPTZ | NOT NULL |
| `algorithm_version` | VARCHAR(100) | NOT NULL |
| `parameters` | JSONB | NOT NULL |
| `started_at` | TIMESTAMPTZ | NOT NULL |
| `finished_at` | TIMESTAMPTZ | NULL |
| `error_details` | JSONB | NULL |

`parameters` содержит значения порогов и методов, например `iqr_multiplier`, `safety_stock_days`, `growth_window_months` и пороги риска.

### `calculation_run_imports`

| Колонка | Тип | Ограничения |
|---|---|---|
| `calculation_run_id` | UUID | FK → `calculation_runs.id`, NOT NULL |
| `import_batch_id` | UUID | FK → `import_batches.id`, NOT NULL |

Составной PK: `(calculation_run_id, import_batch_id)`.

### `detected_anomalies`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `calculation_run_id` | UUID | FK → `calculation_runs.id`, NOT NULL |
| `sales_transaction_id` | UUID | FK → `sales_transactions.id`, NOT NULL |
| `method` | VARCHAR(50) | NOT NULL |
| `original_quantity` | NUMERIC(18,4) | NOT NULL |
| `replacement_quantity` | NUMERIC(18,4) | NOT NULL |
| `threshold` | NUMERIC(18,4) | NULL |
| `reason` | TEXT | NOT NULL |
| `details` | JSONB | NOT NULL, DEFAULT '{}' |

Ограничение: `UNIQUE(calculation_run_id, sales_transaction_id, method)`.

### `demand_forecasts`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `calculation_run_id` | UUID | FK → `calculation_runs.id`, NOT NULL |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NOT NULL |
| `forecast_period_start` | DATE | NOT NULL |
| `forecast_period_end` | DATE | NOT NULL |
| `raw_demand` | NUMERIC(18,4) | NOT NULL |
| `return_adjustment` | NUMERIC(18,4) | NOT NULL, DEFAULT 0 |
| `anomaly_adjustment` | NUMERIC(18,4) | NOT NULL |
| `stockout_adjustment` | NUMERIC(18,4) | NOT NULL |
| `cleaned_baseline` | NUMERIC(18,4) | NOT NULL |
| `growth_rate` | NUMERIC(12,6) | NOT NULL |
| `seasonality_index` | NUMERIC(12,6) | NOT NULL |
| `forecast_quantity` | NUMERIC(18,4) | NOT NULL |
| `details` | JSONB | NOT NULL, DEFAULT '{}' |

Ограничение: `UNIQUE(calculation_run_id, product_id, warehouse_id, forecast_period_start, forecast_period_end)`.

Период всегда хранится двумя типизированными датами. Строковые значения наподобие `2026-Q3` или `2026-09` не используются как источник истины. Человекочитаемая подпись периода формируется API или frontend из `forecast_period_start` и `forecast_period_end`.

### `recommendations`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `calculation_run_id` | UUID | FK → `calculation_runs.id`, NOT NULL |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NOT NULL |
| `supplier_id` | UUID | FK → `suppliers.id`, NOT NULL |
| `forecast_quantity` | NUMERIC(18,4) | NOT NULL |
| `current_stock` | NUMERIC(18,4) | NOT NULL |
| `in_transit_quantity` | NUMERIC(18,4) | NOT NULL |
| `material_requirement_quantity` | NUMERIC(18,4) | NOT NULL |
| `safety_stock` | NUMERIC(18,4) | NOT NULL |
| `shortage_quantity` | NUMERIC(18,4) | NOT NULL |
| `quantity_before_rounding` | NUMERIC(18,4) | NOT NULL |
| `moq` | NUMERIC(18,4) | NOT NULL |
| `package_size` | NUMERIC(18,4) | NOT NULL |
| `recommended_quantity` | NUMERIC(18,4) | NOT NULL, CHECK >= 0 |
| `effective_quantity` | NUMERIC(18,4) | NOT NULL, CHECK >= 0 |
| `risk_score` | NUMERIC(5,4) | NOT NULL, CHECK BETWEEN 0 AND 1 |
| `urgency` | VARCHAR(20) | CHECK: `low`, `medium`, `high`, `critical` |
| `status` | VARCHAR(30) | CHECK: `suggested`, `adjusted`, `accepted`, `rejected`, `converted_to_order` |
| `explanation` | TEXT | NOT NULL |
| `calculation_details` | JSONB | NOT NULL |
| `version` | INTEGER | NOT NULL, DEFAULT 1 |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Ограничение: `UNIQUE(calculation_run_id, product_id, warehouse_id, supplier_id)`.

`recommended_quantity` — неизменный результат алгоритма. `effective_quantity` — текущее выбранное пользователем количество. Любое изменение `effective_quantity` обязано создать запись в `recommendation_adjustments`. `version` используется для optimistic locking.

Пример структуры `calculation_details`:

```json
{
  "baseline": 120,
  "return_adjustment": -5,
  "anomaly_adjustment": -25,
  "stockout_compensation": 15,
  "growth_multiplier": 1.08,
  "seasonality_index": 1.2,
  "forecast": 142.56,
  "safety_stock": 35,
  "current_stock": 40,
  "in_transit": 20,
  "material_requirements": 10,
  "quantity_before_rounding": 127.56,
  "moq": 40,
  "package_size": 20,
  "quantity_after_rounding": 160
}
```

## 7. Ручные корректировки и заказы

### `recommendation_adjustments`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `recommendation_id` | UUID | FK → `recommendations.id`, NOT NULL |
| `previous_quantity` | NUMERIC(18,4) | NOT NULL |
| `new_quantity` | NUMERIC(18,4) | NOT NULL, CHECK >= 0 |
| `reason` | TEXT | NOT NULL |
| `changed_by` | UUID | FK → `users.id`, NOT NULL |
| `changed_at` | TIMESTAMPTZ | NOT NULL |

Корректировка и обновление `recommendations.effective_quantity` выполняются в одной транзакции.

### `purchase_orders`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `order_number` | VARCHAR(100) | UNIQUE, NOT NULL |
| `supplier_id` | UUID | FK → `suppliers.id`, NOT NULL |
| `warehouse_id` | UUID | FK → `warehouses.id`, NOT NULL |
| `created_from_run_id` | UUID | FK → `calculation_runs.id`, NOT NULL |
| `status` | VARCHAR(20) | CHECK: `draft`, `approved`, `exported`, `cancelled` |
| `created_by` | UUID | FK → `users.id`, NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `approved_by` | UUID | FK → `users.id`, NULL |
| `approved_at` | TIMESTAMPTZ | NULL |
| `exported_at` | TIMESTAMPTZ | NULL |

Инварианты:

- для `approved` и `exported` обязательны `approved_by` и `approved_at`;
- нельзя перейти из `draft` в `exported`, минуя `approved`;
- автоматическое создание `approved` заказа запрещено;
- после утверждения состав заказа изменяется только через отдельную отмену/новую версию бизнес-процесса.

### `purchase_order_items`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `purchase_order_id` | UUID | FK → `purchase_orders.id`, NOT NULL |
| `recommendation_id` | UUID | FK → `recommendations.id`, NOT NULL, UNIQUE |
| `product_id` | UUID | FK → `products.id`, NOT NULL |
| `recommended_quantity` | NUMERIC(18,4) | NOT NULL |
| `approved_quantity` | NUMERIC(18,4) | NOT NULL, CHECK > 0 |
| `unit_price` | NUMERIC(18,4) | NULL, CHECK >= 0 |
| `total_amount` | NUMERIC(18,4) | NULL, CHECK >= 0 |

`recommended_quantity` и `approved_quantity` сохраняются снимком, чтобы последующие изменения справочников не изменили исторический заказ.

### `order_exports`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `purchase_order_id` | UUID | FK → `purchase_orders.id`, NOT NULL |
| `format` | VARCHAR(20) | CHECK: `xlsx`, `csv` |
| `file_name` | VARCHAR(500) | NOT NULL |
| `file_checksum` | VARCHAR(64) | NOT NULL |
| `created_by` | UUID | FK → `users.id`, NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Экспортировать разрешается только утвержденный заказ. Файл экспорта должен быть совместим с согласованным форматом 1С.

## 8. Ключевые индексы

Помимо PK, UNIQUE и индексов внешних ключей необходимы:

- `sales_transactions(product_id, warehouse_id, sold_at)`;
- `monthly_sales(product_id, warehouse_id, period_start, period_end)`;
- `inventory_snapshots(product_id, warehouse_id, snapshot_at DESC)`;
- `stockout_periods(product_id, warehouse_id, started_at, ended_at)`;
- `in_transit_items(product_id, destination_warehouse_id, status, expected_at)`;
- `calculation_runs(status, started_at DESC)`;
- `recommendations(calculation_run_id, product_id, warehouse_id)`;
- `recommendations(calculation_run_id, supplier_id, urgency)`;
- `recommendations(calculation_run_id, warehouse_id, status)`;
- `purchase_orders(supplier_id, status, created_at DESC)`.

Первые колонки композитного B-tree индекса выбираются в соответствии с реальными фильтрами. Например, индекс `(product_id, warehouse_id, sold_at)` покрывает запросы по товару и по паре `товар + склад`, а также диапазон по дате. Отдельно дублировать индекс `(product_id, warehouse_id)` без подтвержденного query plan не требуется.

GIN-индекс на `calculation_runs.parameters` не создается по умолчанию: в MVP поле используется для воспроизводимости, а не как основной фильтр. Если появятся запросы по содержимому параметров и `EXPLAIN ANALYZE` подтвердит необходимость, добавляется:

```sql
CREATE INDEX ix_calculation_runs_parameters_gin
    ON calculation_runs
    USING GIN (parameters);
```

Основные фильтруемые значения должны оставаться обычными типизированными колонками, а не переноситься в JSONB.

## 9. Транзакционные границы

- Импорт: метаданные и все строки одного файла фиксируются атомарно. При ошибке импорт получает `failed`, а неполные факты не становятся доступными расчету.
- Запуск расчета: создание `calculation_runs` и привязка используемых `import_batches` выполняются одной транзакцией.
- Завершение расчета: forecasts, anomalies и recommendations записываются до перевода запуска в `completed`.
- Корректировка: запись аудита и обновление effective quantity выполняются одной транзакцией.
- Создание заказа: заказ и все строки создаются одной транзакцией.
- Утверждение: проверка статуса, фиксация пользователя и времени выполняются атомарно.

## 10. Data flow

```text
Excel / 1С
    ↓
ImportBatch + валидация
    ↓
Нормализованные исходные таблицы
    ↓
CalculationRun + зафиксированный набор импортов
    ↓
DetectedAnomaly + DemandForecast
    ↓
Recommendation
    ↓
RecommendationAdjustment (опционально)
    ↓
PurchaseOrder(draft)
    ↓ явное подтверждение пользователя
PurchaseOrder(approved)
    ↓
OrderExport для 1С
```

## 11. Соответствие DDD-слоям

- `domain/entities` — доменные `Product`, `SupplierTerms`, `DemandForecast`, `Recommendation`, `CalculationRun`, `PurchaseOrder` и их инварианты.
- `domain/repositories` — интерфейсы доступа к данным без SQLAlchemy-зависимостей.
- `application/use_cases` — импорт, запуск расчета, получение объяснения, корректировка, создание и утверждение заказа, экспорт.
- `application/dto` — входные и выходные DTO use cases.
- `infrastructure/persistence/models` — SQLAlchemy-модели, соответствующие таблицам этого документа.
- `infrastructure/persistence/repositories` — реализации доменных репозиториев.
- `infrastructure/persistence/migrations` — миграции Alembic; после их появления именно миграции являются исполняемым источником истины.

ORM-модели не должны использоваться как доменные сущности или API DTO.

## 12. Минимальный объем для MVP

Для первого сквозного сценария обязательны:

1. `users`, `categories`, `products`, `warehouses`, `suppliers`, `supplier_products`;
2. `import_batches`, `sales_transactions`, `monthly_sales`, `inventory_snapshots`, `in_transit_items`, `seasonality_coefficients`;
3. `calculation_runs`, `calculation_run_imports`, `detected_anomalies`, `demand_forecasts`, `recommendations`;
4. `recommendation_adjustments`, `purchase_orders`, `purchase_order_items`, `order_exports`.

`growth_assumptions`, явные `stockout_periods` и `material_requirements` допускается сначала заполнять синтетически, но их влияние на расчет должно быть показано в итоговой демонстрации и тестах.

## 13. Снимки условий, принятие и денежные суммы

При постановке расчета в очередь `calculation_runs.parameters.supplier_terms_snapshot` сохраняет условия всех доступных поставщиков для каждого товара. Ключ — UUID товара; значение — массив снимков `SupplierProduct`: `id`, `supplier_id`, `product_id`, `moq`, `package_size`, `lead_time_days`, `purchase_price`, `currency`, `priority`, `is_primary`, `is_active`. UUID и Decimal сериализуются строками. Рабочий расчет читает этот снимок, поэтому последующий импорт условий не меняет уже поставленный в очередь запуск.

`recommendations.calculation_details.supplier_terms_snapshot` содержит выбранные условия: `supplier_product_id`, `unit_price`, `currency`, `moq`, `package_size`, `lead_time_days`. У старых рекомендаций без снимка цена и сумма остаются `null`; текущий справочник не используется для восстановления исторической цены.

Явное принятие добавляет запись в `calculation_details.acceptance_history`: `accepted_by` (UUID), `accepted_at` (ISO timestamp), новая `version` и `quantity` (decimal-string). История сохраняется вместе со статусом `accepted` и сравнением ожидаемой версии в одной транзакции. Повторное принятие после корректировки добавляет запись, сохраняя прежние записи. Положительное количество должно соответствовать сохраненным MOQ и кратности; корректировка в ноль разрешена, принятие нуля запрещено.

Массовое принятие и создание выбранных заказов выполняются атомарно: конфликт любой строки откатывает весь набор. Рекомендации блокируются через сравнение версии и статуса; уникальный FK `purchase_order_items.recommendation_id` дополнительно защищает от повторного включения. Цена копируется из снимка в строку заказа. Сумма строки округляется до четырех знаков по правилу `ROUND_HALF_UP`. Итог заказа доступен только при известных ценах всех строк и единой известной валюте; иначе он равен `null`.

Бюджет и результаты распределения хранятся в `calculation_runs.parameters`: `budget_limit`, `currency`, `allocated_amount`, `unmet_need_amount`, `optimization_method`. Поля `budget_allocation` рекомендации содержат исходную потребность без бюджета и выделенное количество. Изменение бюджета создает отдельный запуск.

## 14. Фоновая обработка и миграция 0003

Миграция `0003_background_jobs.py` (после `0002_user_credentials.py`) добавляет `background_jobs`. Задание и связанный `pending` расчет/импорт фиксируются одной транзакцией до ответа HTTP 202.

Таблица содержит UUID `id` (PK), `kind` (`calculation` или `import`), `calculation_run_id` и `import_batch_id` (уникальные nullable FK, заполнен ровно один согласно kind), `created_by` (FK users), `idempotency_key` (nullable VARCHAR(128)), `request_fingerprint` (SHA-256, VARCHAR(64)), `status` (`pending`, `running`, `completed`, `failed`), `claim_token` (nullable UUID), `lease_until` (nullable TIMESTAMPTZ), `attempts` (INTEGER), `payload` и `progress` (JSONB), `created_at` и nullable `finished_at` (TIMESTAMPTZ).

Ограничение `UNIQUE(kind, created_by, idempotency_key)` обеспечивает идемпотентность расчета. Одинаковый ключ и тело возвращают прежний запуск; иное тело с тем же ключом дает 409. Индекс `(status, lease_until, created_at)` используется при захвате заданий. PostgreSQL `FOR UPDATE SKIP LOCKED` позволяет нескольким процессам безопасно забирать задания. Работник обновляет аренду каждые 10 секунд на 60 секунд вперед; после остановки процесса просроченное задание подхватывается другим работником. Новый токен владения запрещает старой попытке зафиксировать результат. Завершение задания и результат расчета/импорта коммитятся одной транзакцией.

В БД сохраняются только метаданные загруженного файла. До валидации XLSX хранится в закрытом каталоге `IMPORT_SPOOL_DIRECTORY` под UUID, с правами 0600; каталог имеет права 0700 там, где ОС их поддерживает. Каталог должен быть постоянным и общим для работников одного развертывания. Файл удаляется после завершения/ошибки. Периодическая уборка удаляет оставшиеся файлы завершенных заданий и файлы без задания старше суток.

`progress` импорта содержит реальные этапы `uploaded`, `validating`, `persisting`, `completed`, `processed_rows` и nullable `total_rows`. Во время атомарной записи число зафиксированных строк равно нулю; после коммита оно равно фактическому числу строк. Прогресс расчета содержит `phase`, `completed`, `total`: текущая единица работы — весь запуск (0/1 до коммита, 1/1 после); искусственный процент обработки SKU не генерируется. При ошибке сохраняется последнее достигнутое состояние и безопасный код ошибки.
