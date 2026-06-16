# Агент сборки event log для process mining

Проект содержит Jupyter-агента, который собирает и проверяет event log из CSV/XLSX-таблиц.

Главный артефакт системы - не только `outputs/event_log.xlsx`, а `outputs/join_plan.json`. В нем описано, как именно был собран event log: какие таблицы использовались, какие связи найдены, какие поля выбраны для `case_id`, `activity`, `timestamp`, и какие предупреждения появились при join.

`join_plan.json` можно проверить, исправить, повторить и объяснить. Поэтому он важнее, чем разовый итоговый Excel-файл.

## Структура проекта

```text
agent_pm/
├── demo.ipynb
├── data/
├── outputs/
├── app/
│   ├── agent.py
│   ├── config.py
│   ├── graph/
│   ├── memory/
│   ├── services/
│   ├── ui/
│   └── visualization/
└── requirements.txt
```

Назначение основных папок:

- `demo.ipynb` - точка запуска в Jupyter.
- `data/` - локальные исходные CSV/XLSX-файлы.
- `outputs/` - отчеты, event log, join plan и HTML-граф процесса.
- `app/agent.py` - основной класс агента.
- `app/config.py` - настройки проекта и LLM.
- `app/graph/` - LangGraph-сценарий и состояния.
- `app/services/` - работа с файлами, профилирование таблиц, join, проверки качества, LLM.
- `app/ui/` - чат-виджет для Jupyter.
- `app/visualization/` - визуализация process graph.
- `app/memory/` - runtime-память сессии.

## Установка

```bash
pip install -r requirements.txt
```

Виртуальное окружение проект сам не создает. Если оно нужно, его можно создать отдельно, но в архитектуру агента оно не входит.

Исходные `.csv` или `.xlsx` файлы нужно положить в папку `data/`.

## Запуск в Jupyter

В `demo.ipynb` остается простой код:

```python
from app.agent import ProcessMiningDataAgent
from app.ui.chat_widget import AgentChatWidget


agent = ProcessMiningDataAgent(data_dir="data")

chat = AgentChatWidget(
    agent_func=agent.run,
    title="Агент сборки event log",
    description="Положите таблицы в data и задайте требования",
)

chat.show()
```

После запуска можно писать требования в чат:

```text
Собери event log.
```

Или сразу уточнять поля:

```text
case_id бери из application_id, activity из operation_name, timestamp из created_at.
```

## Настройка LLM

Все настройки LLM находятся в `app/config.py`.

```python
LLM_BACKEND = "cobolt_cpp"
QWEN_MODEL_PATH = str(BASE_DIR / "models" / "qwen3")
KOBOLD_CPP_URL = "http://127.0.0.1:5001/api/v1/generate"
LLM_MAX_NEW_TOKENS = 300
LLM_DECISION_MAX_NEW_TOKENS = 300
KOBOLD_CPP_TIMEOUT_SECONDS = 60
```

Для локального тестирования через Cobolt/KoboldCpp:

```python
LLM_BACKEND = "cobolt_cpp"
```

Для боевого локального запуска через Qwen:

```python
LLM_BACKEND = "qwen"
QWEN_MODEL_PATH = "/path/to/qwen3"
```

Qwen и Cobolt подключены через один внутренний интерфейс:

```python
generate(prompt: str, max_new_tokens: int) -> str
```

Это сделано специально: все, что связано с Cobolt, можно будет убрать без переписывания графа и бизнес-логики. Основной код агента не должен знать, какая именно модель стоит за LLM-интерфейсом.

## Общая архитектура

В системе роли разделены так:

- LangGraph управляет шагами процесса.
- pandas выполняет расчеты, join и сборку event log.
- Qwen/Cobolt помогает понять требования пользователя и принять следующее действие.
- `session_state.json` хранит память текущей сессии.
- Jupyter Widget дает интерфейс общения.
- `ProcessGraphViewer` показывает итоговый процесс.

LLM не делает join и не изменяет таблицы напрямую. Она возвращает структурированное решение, а код уже применяет это решение через обычные Python-сервисы.

## Процесс работы агента

Текущий граф выполнения:

```text
START
  -> load_session
  -> parse_requirements
  -> scan_data
  -> profile_tables
  -> infer_relationships
  -> build_join_plan
  -> validate_join_plan
  -> execute_join_plan
  -> validate_event_log
  -> decide_next_action
      -> apply_agent_decision -> build_join_plan
      -> save_outputs
  -> save_session
  -> generate_answer
END
```

Смысл шагов:

- `load_session` - загружает память прошлых требований и решений.
- `parse_requirements` - извлекает явные требования из текста пользователя.
- `scan_data` - ищет CSV/XLSX-файлы в `data/`.
- `profile_tables` - читает таблицы и собирает информацию о колонках.
- `infer_relationships` - ищет возможные связи между таблицами.
- `build_join_plan` - строит план сборки event log.
- `validate_join_plan` - проверяет риски join.
- `execute_join_plan` - собирает event log через pandas.
- `validate_event_log` - проверяет качество event log.
- `decide_next_action` - решает, что делать дальше.
- `apply_agent_decision` - применяет правки требований, если нужен пересбор.
- `save_outputs` - сохраняет артефакты в `outputs/`.
- `save_session` - обновляет память сессии.
- `generate_answer` - формирует ответ в чат.

Цикл пересборки ограничен через `max_agent_iterations`, чтобы агент не мог бесконечно перестраивать event log.

## Решения агента

После проверок качества агент выбирает следующее действие. Решение приходит в строгом JSON-формате:

```json
{
  "action": "accept",
  "requirements": {},
  "reason": "Критических ошибок нет.",
  "user_message": "Event log собран и проверен."
}
```

Допустимые действия:

```text
accept
rebuild_join_plan
ask_user
```

### `accept`

Агент принимает текущий результат, сохраняет файлы и отвечает пользователю.

Пример:

```json
{
  "action": "accept",
  "requirements": {},
  "reason": "Критических ошибок нет. Статус join_plan: warning. Статус event_log: ok.",
  "user_message": "Event log собран и проверен."
}
```

### `rebuild_join_plan`

Агент считает, что event log нужно пересобрать с другими требованиями.

Пример:

```json
{
  "action": "rebuild_join_plan",
  "requirements": {
    "base_table": "orders.csv",
    "case_id": "case_id",
    "activity": "status",
    "timestamp": "updated_at"
  },
  "reason": "Текущий join_plan дал many-to-many рост строк.",
  "user_message": "Пересобираю event log с другой базовой таблицей."
}
```

После этого LangGraph применяет новые требования и возвращается к `build_join_plan`.

### `ask_user`

Агент не может безопасно принять решение без уточнения пользователя.

Пример:

```json
{
  "action": "ask_user",
  "requirements": {},
  "reason": "Нельзя однозначно выбрать activity: найдено несколько похожих колонок.",
  "user_message": "Уточните, какое поле использовать как activity."
}
```

Если модель недоступна или возвращает невалидный JSON, система использует детерминированные fallback-правила.

## Состояние графа

Активное состояние описано в `app/graph/state.py`.

Основные поля:

```text
user_question              исходный текст пользователя
session_state              загруженная память сессии
parsed_requirements        требования, найденные в текущем сообщении
user_requirements          активные требования после объединения с памятью
agent_iteration            номер текущей итерации пересборки
max_agent_iterations       лимит итераций пересборки
agent_decision             последнее структурированное решение агента
agent_decision_history     история решений в текущем запуске
files                      найденные исходные файлы
tables_info                профили таблиц
relationships              найденные связи между таблицами
join_plan                  текущий план join
join_validation_report     отчет проверки join
event_log                  pandas DataFrame с event log
validation_report          отчет проверки event log
output_paths               пути к сохраненным файлам
session_path               путь к файлу памяти
answer                     итоговый ответ в чат
```

Это состояние живет внутри одного запуска графа. После завершения часть данных сохраняется в память сессии.

## Память сессии

Память хранится в файле:

```text
app/memory/session_state.json
```

Туда попадает:

- активные требования пользователя;
- последний `join_plan`;
- последний отчет проверки join;
- последний отчет проверки event log;
- пути к последним артефактам;
- история решений агента;
- краткая история запусков.

Память не очищается автоматически перед каждым запросом. Это сделано намеренно: если пользователь написал `case_id бери из application_id`, это требование должно сохраниться и применяться в следующих запусках.

Сбрасывать память нужно только когда начинается новый независимый сценарий, меняется набор данных или нужно подготовить чистое демо:

```python
agent.reset_session()
```

`app/memory/session_state.json` является runtime-состоянием и не должен попадать в git.

## Как выглядят размышления агента

Система не сохраняет и не показывает скрытую цепочку рассуждений модели.

Вместо этого используется объяснимое рабочее решение в структурированном виде:

```json
{
  "action": "accept",
  "requirements": {},
  "reason": "Критических ошибок нет. Статус join_plan: warning. Статус event_log: ok.",
  "user_message": "Event log собран и проверен."
}
```

Это и есть прикладные "размышления" агента для боевой системы:

- какое действие выбрано;
- какие требования изменены;
- почему выбрано это действие;
- что нужно показать пользователю.

Последнее решение можно посмотреть так:

```python
agent.get_last_state()["agent_decision"]
```

Историю решений текущего запуска:

```python
agent.get_last_state()["agent_decision_history"]
```

Последняя история также сохраняется в:

```text
app/memory/session_state.json
```

## Правки пользователя

Пользователь может исправлять требования прямо в чате:

```text
Нет, case_id бери из application_id, activity из operation_name, timestamp из created_at.
```

Парсер требований извлекает очевидные назначения полей. Затем агент объединяет их с памятью сессии и пересобирает event log.

Поддерживаемые ключи требований:

```text
plan_mode
activity_source
base_table
case_id
activity
timestamp
start_time
stop_time
```

## Режим: каждый файл как activity

Для сценария, где в папке `data/` лежит много event-таблиц, и каждая таблица означает отдельный этап процесса, используется отдельный режим:

```text
plan_mode = event_tables_concat
activity_source = table_name
```

В этом режиме агент не делает большой join между всеми файлами. Он читает каждый файл как источник событий, подбирает `case_id` и `timestamp` отдельно для каждого файла, а `activity` берет из имени файла.

Например:

```text
application_created.csv  -> activity = application_created
contract_signed.csv      -> activity = contract_signed
payment_received.csv     -> activity = payment_received
```

Итоговый event log собирается через `concat`:

```text
case_id | activity | activity_id | timestamp | start_time | stop_time | source_table
```

Пример фразы для чата:

```text
Собери event log. Имя таблицы это activity_id.
```

После такой фразы парсер включит:

```json
{
  "plan_mode": "event_tables_concat",
  "activity_source": "table_name"
}
```

Пример `join_plan.json` для этого режима:

```json
{
  "status": "ok",
  "mode": "event_tables_concat",
  "activity_source": "table_name",
  "event_sources": [
    {
      "file": "application_created.csv",
      "activity": "application_created",
      "activity_source": "table_name",
      "case_id": "application_id",
      "timestamp": "created_at",
      "start_time": "created_at",
      "stop_time": "created_at"
    }
  ],
  "joins": []
}
```

Этот режим лучше подходит для 10-20 и более файлов с разными именами полей, если каждый файл уже является отдельным типом события. Join в таком случае нужен только для обогащения справочниками, а не для создания самих событий.

## Выходные файлы

Сгенерированные файлы сохраняются в `outputs/`.

Основные файлы:

```text
join_plan.json
join_quality_report.json
relationships.json
quality_report.json
event_log.xlsx
event_log_preview.xlsx
quality_report.xlsx
join_quality_report.xlsx
process_graph.html
```

`join_plan.json` - основной файл для проверки и исправления.

## Проверки качества

Проверки join:

- разрастание строк после join;
- many-to-many join;
- потеря строк после join;
- дубли ключей;
- пропуски в ключах join.

Проверки event log:

- наличие обязательных колонок;
- пропуски в `case_id`, `activity`, `timestamp`;
- невалидные даты;
- дубли событий;
- отрицательные длительности;
- кейсы с одним событием;
- пропущенные частые этапы;
- повторные возвраты;
- редкие маршруты;
- outlier-длительности.

## Визуализация process graph

После сборки `event_log.xlsx` граф можно построить так:

```python
import pandas as pd

from app.visualization.process_graph_viewer import ProcessGraphViewer


df = pd.read_excel("outputs/event_log.xlsx")

viewer = ProcessGraphViewer(
    df=df,
    case_id_col="case_id",
    event_col="activity",
    start_time_col="start_time",
    stop_time_col="stop_time",
    output_dir="outputs",
    filename="process_graph.html",
    layout_mode="hierarchical",
    node_spacing=140,
    level_separation=110,
)

viewer.show()
```

Граф строится сверху вниз. В узлах показывается количество операций, на ребрах - количество переходов.

## Что не попадает в git

В `.gitignore` исключены:

- локальные файлы данных в `data/`;
- runtime-память `app/memory/session_state.json`;
- сгенерированные отчеты в `outputs/`;
- кэши Python и Jupyter.

Папки `data/` и `outputs/` остаются в проекте через `.gitkeep`, но реальные данные и результаты работы агента не должны попадать в индекс git.

## Ключевые принципы

- `join_plan.json` важнее, чем разово собранный `event_log.xlsx`.
- LLM должна возвращать структурированное решение, а не свободный текст.
- pandas отвечает за все детерминированные операции с данными.
- Jupyter Widget является интерфейсом оператора, а не слоем бизнес-логики.
- Память сессии нужна для правок пользователя и повторной сборки.
