# Агент сборки event log

Jupyter-агент для сборки event log из CSV/XLSX-файлов в папке `data/`.

Агент сам анализирует таблицы, предлагает стратегии, строит preview и показывает качество. Финальный `outputs/event_log.xlsx` создается только после подтверждения пользователя.

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
