# Агент сборки event log

Jupyter-агент для сборки event log из CSV/XLSX-файлов в папке `data/`.

Агент сам анализирует таблицы, предлагает стратегии, строит preview и показывает качество. Финальный `outputs/event_log.xlsx` создается только после подтверждения пользователя.

## Логика работы

1. Агент сканирует `data/` и профилирует таблицы.
2. Классифицирует таблицы: события, атрибуты, lifecycle, bridge или шум.
3. Находит возможные связи и показывает их как готовые `join`-команды.
4. Строит несколько preview для разных стратегий.
5. Сравнивает стратегии по `preview_score` и рекомендует лучшую.
6. Показывает качество preview и первые строки event log.
7. Финальный `event_log.xlsx` собирается только после команды `подтверждаю`.

Если файлы в `data/` изменились, старая память сессии сбрасывается автоматически.

## Установка

```bash
pip install -r requirements.txt
```

Положи исходные `.csv` или `.xlsx` файлы в `data/`.

## Запуск

В Jupyter:

```python
from app.agent import ProcessMiningDataAgent
from app.ui.chat_widget import AgentChatWidget

agent = ProcessMiningDataAgent()

chat = AgentChatWidget(
    agent_func=agent.run,
    title="Диалог с агентом Process Mining",
    description="Агент помогает собрать event log из таблиц в папке data",
)

chat.show()
```

## Как общаться

Начать анализ:

```text
помоги собрать лог
```

Выбрать стратегию:

```text
выбери вариант 2
```

Сравнить стратегии:

```text
сравни стратегии
```

Понять, почему агент выбрал текущий вариант:

```text
почему?
```

Исправить поля:

```text
case_id=application_id activity=operation_name timestamp=created_at
```

Явно добавить join:

```text
join status_history.xlsx.application_id = applications.xlsx.application_id
```

Собрать финальный event log после preview:

```text
подтверждаю
```

Сбросить память сессии:

```text
сбросить
```

## Выходные файлы

Preview:

- `outputs/preview_event_log.xlsx`
- `outputs/preview_quality_report.json`

Финальная сборка после подтверждения:

- `outputs/event_log.xlsx`
- `outputs/join_plan.json`
- `outputs/join_quality_report.json`
- `outputs/quality_report.json`
- `outputs/relationships.json`

Память диалога хранится в `app/memory/session_state.json`.
