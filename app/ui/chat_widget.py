import html
import time

import ipywidgets as widgets
from IPython.display import HTML, display


class AgentChatWidget:
    """
    Стабильный чат-виджет для Jupyter Notebook:
    - сообщения не залезают под поле ввода;
    - история прокручивается;
    - кнопки остаются доступными;
    - светлый фон задается через CSS.
    """

    def __init__(
        self,
        agent_func=None,
        title="Диалог с агентом",
        description="Введите запрос агенту",
        width="100%",
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
        display(
            HTML(
                """
                <style>
                    .agent-chat-wrapper {
                        background: #f8fafc !important;
                        border: 1px solid #d9e2ec !important;
                        border-radius: 10px !important;
                        padding: 16px !important;
                        width: 100% !important;
                        max-width: 100% !important;
                        box-sizing: border-box !important;
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

                    .agent-chat-history {
                        background: #ffffff !important;
                        color: #1f2937 !important;
                        border: 1px solid #d0d5dd !important;
                        border-radius: 10px !important;
                        padding: 14px !important;
                        overflow-y: auto !important;
                        box-sizing: border-box !important;
                        font-family: Arial, sans-serif !important;
                        font-size: 14px !important;
                        line-height: 1.4 !important;
                        scrollbar-width: thin !important;
                        scrollbar-color: #cbd5e1 #ffffff !important;
                    }

                    .agent-chat-history::-webkit-scrollbar,
                    .agent-chat-input textarea::-webkit-scrollbar {
                        width: 10px !important;
                        height: 10px !important;
                    }

                    .agent-chat-history::-webkit-scrollbar-track,
                    .agent-chat-input textarea::-webkit-scrollbar-track {
                        background: #ffffff !important;
                        border-radius: 999px !important;
                    }

                    .agent-chat-history::-webkit-scrollbar-thumb,
                    .agent-chat-input textarea::-webkit-scrollbar-thumb {
                        background: #cbd5e1 !important;
                        border: 2px solid #ffffff !important;
                        border-radius: 999px !important;
                    }

                    .agent-chat-history::-webkit-scrollbar-thumb:hover,
                    .agent-chat-input textarea::-webkit-scrollbar-thumb:hover {
                        background: #94a3b8 !important;
                    }

                    .agent-chat-empty {
                        color: #667085 !important;
                        font-family: Arial, sans-serif !important;
                    }

                    .agent-chat-message-row {
                        display: flex !important;
                        margin: 0 0 12px 0 !important;
                        width: 100% !important;
                    }

                    .agent-chat-message-row.user {
                        justify-content: flex-end !important;
                    }

                    .agent-chat-message-row.agent {
                        justify-content: flex-start !important;
                    }

                    .agent-chat-message {
                        max-width: 78% !important;
                        border-radius: 10px !important;
                        padding: 10px 12px !important;
                        box-sizing: border-box !important;
                        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.08) !important;
                    }

                    .agent-chat-message.user {
                        background: #2563eb !important;
                        color: #ffffff !important;
                        border: 1px solid #1d4ed8 !important;
                    }

                    .agent-chat-message.agent {
                        background: #f8fafc !important;
                        color: #1f2937 !important;
                        border: 1px solid #e5e7eb !important;
                    }

                    .agent-chat-role {
                        font-size: 12px !important;
                        font-weight: 700 !important;
                        margin-bottom: 6px !important;
                        opacity: 0.85 !important;
                    }

                    .agent-chat-text {
                        white-space: pre-wrap !important;
                        overflow-wrap: anywhere !important;
                        font-family: Arial, sans-serif !important;
                    }

                    .agent-chat-message.agent .agent-chat-text {
                        font-family: Consolas, monospace !important;
                        font-size: 13px !important;
                    }

                    .agent-chat-input textarea {
                        background: #ffffff !important;
                        color: #1f2937 !important;
                        border: 1px solid #d0d5dd !important;
                        border-radius: 10px !important;
                        padding: 10px !important;
                        font-family: Arial, sans-serif !important;
                        font-size: 14px !important;
                        scrollbar-width: thin !important;
                        scrollbar-color: #cbd5e1 #ffffff !important;
                    }

                    .agent-chat-status {
                        min-height: 26px !important;
                        font-family: Arial, sans-serif !important;
                    }
                </style>
                """
            )
        )

    def _default_agent_func(self, user_query: str) -> str:
        time.sleep(1.0)

        return (
            "Я получил ваш запрос.\n\n"
            "Настоящий агент пока не подключен."
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

        self.chat_box = widgets.HTML(
            value="",
            layout=widgets.Layout(
                width="100%",
                height=self.chat_height,
            ),
        )
        self.chat_box.add_class("agent-chat-history")

        self.input_box = widgets.Textarea(
            placeholder="Введите запрос агенту...",
            layout=widgets.Layout(
                width="100%",
                height=self.input_height,
            ),
        )
        self.input_box.add_class("agent-chat-input")

        self.send_button = widgets.Button(
            description="Отправить",
            button_style="primary",
            icon="paper-plane",
            layout=widgets.Layout(width="150px"),
        )

        self.clear_button = widgets.Button(
            description="Очистить чат",
            button_style="warning",
            icon="trash",
            layout=widgets.Layout(width="150px"),
        )

        self.example_button = widgets.Button(
            description="Пример запроса",
            button_style="info",
            icon="lightbulb-o",
            layout=widgets.Layout(width="170px"),
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
            ),
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
                max_width="100%",
                align_self="stretch",
            ),
        )
        self.ui.add_class("agent-chat-wrapper")

    def _bind_events(self):
        self.send_button.on_click(self._on_send_clicked)
        self.clear_button.on_click(self._on_clear_clicked)
        self.example_button.on_click(self._on_example_clicked)

    def _render_chat(self):
        if not self.chat_history:
            self.chat_box.value = """
            <div class="agent-chat-empty">
                Пока сообщений нет. Напишите первый запрос агенту.
            </div>
            """
            return

        blocks = []

        for message in self.chat_history:
            role = message["role"]
            text = html.escape(str(message["text"]))

            if role == "user":
                role_label = "Вы"
            else:
                role_label = "Агент"

            blocks.append(
                f"""
                <div class="agent-chat-message-row {role}">
                    <div class="agent-chat-message {role}">
                        <div class="agent-chat-role">{role_label}</div>
                        <div class="agent-chat-text">{text}</div>
                    </div>
                </div>
                """
            )

        self.chat_box.value = "\n".join(blocks)

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
            "Помоги собрать лог событий. "
            "Посмотри таблицы в папке data, найди кандидаты на case_id, "
            "activity, timestamp, предложи стратегию сборки event log "
            "и сначала собери preview."
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
