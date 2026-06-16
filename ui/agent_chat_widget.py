import time
import ipywidgets as widgets
from IPython.display import display, HTML


class AgentChatWidget:
    """
    Стабильный чат-виджет для Jupyter Notebook:
    - сообщения не залезают под поле ввода;
    - история прокручивается;
    - кнопки остаются красивыми;
    - светлый фон задается через CSS.
    """

    def __init__(
        self,
        agent_func=None,
        title="Диалог с агентом",
        description="Введите запрос агенту",
        width="850px",
        chat_height="360px",
        input_height="90px",
    ):
        self.agent_func = agent_func or self._default_agent_func
        self.chat_history = []

        self.title_text = title
        self.description_text = description
        self.width = width
        self.chat_height = chat_height
        self.input_height = input_height

        self._inject_css()
        self._build_widgets()
        self._bind_events()
        self._render_chat()

    def _inject_css(self):
        display(HTML("""
        <style>
            .agent-chat-wrapper {
                background: #f8fafc !important;
                border: 1px solid #d9e2ec !important;
                border-radius: 12px !important;
                padding: 16px !important;
            }

            .agent-chat-title h2 {
                color: #2c3e50 !important;
                margin-bottom: 4px !important;
                font-family: Arial, sans-serif !important;
            }

            .agent-chat-title div {
                color: #667085 !important;
                margin-bottom: 10px !important;
                font-family: Arial, sans-serif !important;
            }

            .agent-chat-history textarea {
                background: #ffffff !important;
                color: #1f2937 !important;
                border: 1px solid #d0d5dd !important;
                border-radius: 10px !important;
                padding: 12px !important;
                font-family: Consolas, monospace !important;
                font-size: 14px !important;
                line-height: 1.4 !important;
            }

            .agent-chat-input textarea {
                background: #ffffff !important;
                color: #1f2937 !important;
                border: 1px solid #d0d5dd !important;
                border-radius: 10px !important;
                padding: 10px !important;
                font-family: Arial, sans-serif !important;
                font-size: 14px !important;
            }

            .agent-chat-status {
                min-height: 26px !important;
                font-family: Arial, sans-serif !important;
            }
        </style>
        """))

    def _default_agent_func(self, user_query: str) -> str:
        time.sleep(6.2)

        return (
            "Я принял запрос на сборку process mining лога.\n\n"
            "Сначала я проанализирую загруженные таблицы и определю, какие поля можно использовать как:\n"
            "- id экземпляра процесса;\n"
            "- событие;\n"
            "- start_time;\n"
            "- stop_time.\n\n"
            "Также проверю качество данных: пропуски, дубликаты, некорректные даты и возможные нарушения последовательности событий.\n\n"
            "На выходе будет предложена структура event log, которую можно использовать для построения process graph и дальнейшего анализа процесса."
        )

    def _build_widgets(self):
        self.title = widgets.HTML(
            value=f"""
            <div class="agent-chat-title">
                <h2>{self.title_text}</h2>
                <div>{self.description_text}</div>
            </div>
            """
        )

        self.chat_box = widgets.Textarea(
            value="",
            disabled=True,
            layout=widgets.Layout(
                width="100%",
                height=self.chat_height,
            )
        )
        self.chat_box.add_class("agent-chat-history")

        self.input_box = widgets.Textarea(
            placeholder="Введите запрос агенту...",
            layout=widgets.Layout(
                width="100%",
                height=self.input_height,
            )
        )
        self.input_box.add_class("agent-chat-input")

        self.send_button = widgets.Button(
            description="Отправить",
            button_style="primary",
            icon="paper-plane",
            layout=widgets.Layout(width="150px")
        )

        self.clear_button = widgets.Button(
            description="Очистить чат",
            button_style="warning",
            icon="trash",
            layout=widgets.Layout(width="150px")
        )

        self.example_button = widgets.Button(
            description="Пример запроса",
            button_style="info",
            icon="lightbulb-o",
            layout=widgets.Layout(width="170px")
        )

        self.status_label = widgets.HTML(value="")
        self.status_label.add_class("agent-chat-status")

        self.buttons_row = widgets.HBox(
            [
                self.send_button,
                self.clear_button,
                self.example_button,
            ],
            layout=widgets.Layout(
                width="100%",
                gap="10px",
                flex_flow="row wrap",
                margin="8px 0 0 0",
            )
        )

        self.ui = widgets.VBox(
            [
                self.title,
                self.chat_box,
                self.input_box,
                self.buttons_row,
                self.status_label,
            ],
            layout=widgets.Layout(
                width=self.width,
            )
        )
        self.ui.add_class("agent-chat-wrapper")

    def _bind_events(self):
        self.send_button.on_click(self._on_send_clicked)
        self.clear_button.on_click(self._on_clear_clicked)
        self.example_button.on_click(self._on_example_clicked)

    def _render_chat(self):
        if not self.chat_history:
            self.chat_box.value = "Пока сообщений нет. Напишите первый запрос агенту."
            return

        lines = []

        for message in self.chat_history:
            role = message["role"]
            text = message["text"]

            if role == "user":
                lines.append("Вы:")
                lines.append(str(text))
            else:
                lines.append("Агент:")
                lines.append(str(text))

            lines.append("")
            lines.append("-" * 80)
            lines.append("")

        self.chat_box.value = "\n".join(lines)

    def _on_send_clicked(self, button):
        user_query = self.input_box.value.strip()

        if not user_query:
            self.status_label.value = """
            <span style="color: #c0392b;">
                Введите запрос перед отправкой.
            </span>
            """
            return

        self.chat_history.append(
            {
                "role": "user",
                "text": user_query,
            }
        )

        self.input_box.value = ""
        self._render_chat()

        self.status_label.value = """
        <span style="color: #667085;">
            Агент думает...
        </span>
        """

        self._set_buttons_disabled(True)

        try:
            answer = self.agent_func(user_query)

            self.chat_history.append(
                {
                    "role": "agent",
                    "text": str(answer),
                }
            )

            self._render_chat()

            self.status_label.value = """
            <span style="color: #27ae60;">
                Ответ получен.
            </span>
            """

        except Exception as error:
            self.chat_history.append(
                {
                    "role": "agent",
                    "text": f"Произошла ошибка: {error}",
                }
            )

            self._render_chat()

            self.status_label.value = """
            <span style="color: #c0392b;">
                Ошибка при обработке запроса.
            </span>
            """

        finally:
            self._set_buttons_disabled(False)

    def _on_clear_clicked(self, button):
        self.chat_history.clear()
        self._render_chat()

        self.status_label.value = """
        <span style="color: #667085;">
            Чат очищен.
        </span>
        """

    def _on_example_clicked(self, button):
        self.input_box.value = (
            "Проанализируй таблицы в папке data, "
            "найди пропуски, проверь соответствие колонок "
            "и предложи структуру event log."
        )

    def _set_buttons_disabled(self, disabled: bool):
        self.send_button.disabled = disabled
        self.clear_button.disabled = disabled
        self.example_button.disabled = disabled

    def show(self):
        display(self.ui)

    def get_history(self):
        return self.chat_history

    def clear_history(self):
        self.chat_history.clear()
        self._render_chat()