from pathlib import Path
import html

import pandas as pd
import networkx as nx
from pyvis.network import Network
from IPython.display import HTML, display


class ProcessGraphViewer:
    """
    Красивый интерактивный process graph для Jupyter Notebook.

    Строит граф по DataFrame:
    - case_id_col: уникальный id экземпляра процесса
    - event_col: событие / активность
    - start_time_col: время начала события
    - stop_time_col: время окончания события

    Пример:
        graph = ProcessGraphViewer(
            df=df,
            case_id_col="id",
            event_col="event_id",
            start_time_col="start_time",
            stop_time_col="stop_time",
            layout_mode="hierarchical",
            node_spacing=280,
            level_separation=360,
        )

        graph.show()
    """

    def __init__(
        self,
        df: pd.DataFrame,
        case_id_col: str,
        event_col: str,
        start_time_col: str,
        stop_time_col: str,
        output_dir: str = "graph_outputs",
        filename: str = "process_graph.html",
        height: str = "750px",
        width: str = "100%",
        min_edge_count: int = 1,
        max_edges: int | None = None,
        add_start_end_nodes: bool = True,
        notebook: bool = True,

        # Управление видом графа
        layout_mode: str = "hierarchical",
        node_spacing: int = 140,
        level_separation: int = 110,
        physics_enabled: bool = False,
    ):
        self.df = df.copy()

        self.case_id_col = case_id_col
        self.event_col = event_col
        self.start_time_col = start_time_col
        self.stop_time_col = stop_time_col

        self.output_dir = Path(output_dir)
        self.filename = filename

        self.height = height
        self.width = width

        self.min_edge_count = min_edge_count
        self.max_edges = max_edges
        self.add_start_end_nodes = add_start_end_nodes
        self.notebook = notebook

        self.layout_mode = layout_mode
        self.node_spacing = node_spacing
        self.level_separation = level_separation
        self.physics_enabled = physics_enabled

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._validate_columns()
        self._prepare_dataframe()

    # =========================
    # Проверки и подготовка df
    # =========================

    def _validate_columns(self):
        required_columns = [
            self.case_id_col,
            self.event_col,
            self.start_time_col,
            self.stop_time_col,
        ]

        missing_columns = [
            col for col in required_columns
            if col not in self.df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"В DataFrame отсутствуют колонки: {missing_columns}"
            )

    def _prepare_dataframe(self):
        self.df[self.start_time_col] = pd.to_datetime(
            self.df[self.start_time_col],
            errors="coerce"
        )

        self.df[self.stop_time_col] = pd.to_datetime(
            self.df[self.stop_time_col],
            errors="coerce"
        )

        self.df = self.df.dropna(
            subset=[
                self.case_id_col,
                self.event_col,
                self.start_time_col,
                self.stop_time_col,
            ]
        )

        self.df[self.event_col] = self.df[self.event_col].astype(str)

        self.df["__duration_seconds"] = (
            self.df[self.stop_time_col] - self.df[self.start_time_col]
        ).dt.total_seconds()

        self.df["__duration_seconds"] = self.df["__duration_seconds"].clip(lower=0)

        self.df = self.df.sort_values(
            by=[
                self.case_id_col,
                self.start_time_col,
                self.stop_time_col,
            ]
        )

    # =========================
    # Статистика по узлам
    # =========================

    def get_node_stats(self) -> pd.DataFrame:
        """
        Статистика по событиям:
        - сколько раз событие встречалось
        - в скольких экземплярах процесса встречалось
        - средняя длительность события
        - медианная длительность события
        """

        node_stats = (
            self.df
            .groupby(self.event_col)
            .agg(
                event_count=(self.event_col, "count"),
                case_count=(self.case_id_col, "nunique"),
                avg_duration_seconds=("__duration_seconds", "mean"),
                median_duration_seconds=("__duration_seconds", "median"),
            )
            .reset_index()
            .rename(columns={self.event_col: "event"})
        )

        return node_stats

    # =========================
    # Статистика по связям
    # =========================

    def get_edge_stats(self) -> pd.DataFrame:
        """
        Статистика по переходам между событиями.

        Логика:
        Для каждого case_id события сортируются по start_time.
        Потом строятся пары:

            текущее событие -> следующее событие
        """

        edges = []

        for case_id, group in self.df.groupby(self.case_id_col):
            group = group.sort_values(
                by=[
                    self.start_time_col,
                    self.stop_time_col,
                ]
            ).reset_index(drop=True)

            events = group[self.event_col].tolist()
            starts = group[self.start_time_col].tolist()
            stops = group[self.stop_time_col].tolist()

            if not events:
                continue

            if self.add_start_end_nodes:
                edges.append(
                    {
                        "source": "__START__",
                        "target": events[0],
                        "case_id": case_id,
                        "waiting_seconds": 0,
                    }
                )

            for i in range(len(events) - 1):
                source_event = events[i]
                target_event = events[i + 1]

                current_stop = stops[i]
                next_start = starts[i + 1]

                waiting_seconds = (next_start - current_stop).total_seconds()

                if pd.isna(waiting_seconds):
                    waiting_seconds = 0

                waiting_seconds = max(waiting_seconds, 0)

                edges.append(
                    {
                        "source": source_event,
                        "target": target_event,
                        "case_id": case_id,
                        "waiting_seconds": waiting_seconds,
                    }
                )

            if self.add_start_end_nodes:
                edges.append(
                    {
                        "source": events[-1],
                        "target": "__END__",
                        "case_id": case_id,
                        "waiting_seconds": 0,
                    }
                )

        if not edges:
            return pd.DataFrame(
                columns=[
                    "source",
                    "target",
                    "transition_count",
                    "case_count",
                    "avg_waiting_seconds",
                    "median_waiting_seconds",
                ]
            )

        edge_df = pd.DataFrame(edges)

        edge_stats = (
            edge_df
            .groupby(["source", "target"])
            .agg(
                transition_count=("case_id", "count"),
                case_count=("case_id", "nunique"),
                avg_waiting_seconds=("waiting_seconds", "mean"),
                median_waiting_seconds=("waiting_seconds", "median"),
            )
            .reset_index()
        )

        edge_stats = edge_stats[
            edge_stats["transition_count"] >= self.min_edge_count
        ]

        edge_stats = edge_stats.sort_values(
            by="transition_count",
            ascending=False
        )

        if self.max_edges is not None:
            edge_stats = edge_stats.head(self.max_edges)

        return edge_stats

    # =========================
    # Форматирование
    # =========================

    def _format_seconds(self, seconds: float) -> str:
        if pd.isna(seconds):
            return "нет данных"

        seconds = int(seconds)

        if seconds < 60:
            return f"{seconds} сек."

        minutes = seconds / 60

        if minutes < 60:
            return f"{minutes:.1f} мин."

        hours = minutes / 60

        if hours < 24:
            return f"{hours:.1f} ч."

        days = hours / 24
        return f"{days:.1f} дн."

    def _node_color(self, event_name: str) -> dict:
        if event_name == "__START__":
            return {
                "background": "#d9ecff",
                "border": "#2f80ed",
            }

        if event_name == "__END__":
            return {
                "background": "#fde2e2",
                "border": "#eb5757",
            }

        return {
            "background": "#e8f5e9",
            "border": "#27ae60",
        }

    def _node_label(self, event_name: str) -> str:
        if event_name == "__START__":
            return "START"

        if event_name == "__END__":
            return "END"

        return str(event_name)

    def _node_display_label(
        self,
        event_name: str,
        event_count: int,
        case_count: int,
    ) -> str:
        base_label = self._node_label(event_name)

        if event_name in ["__START__", "__END__"]:
            return f"{base_label}\ncase: {case_count}"

        return f"{base_label}\nопераций: {event_count}"

    # =========================
    # NetworkX граф
    # =========================

    def build_networkx_graph(self) -> nx.DiGraph:
        """
        Возвращает NetworkX-граф.
        Можно использовать отдельно для анализа.
        """

        node_stats = self.get_node_stats()
        edge_stats = self.get_edge_stats()

        graph = nx.DiGraph()

        total_cases = self.df[self.case_id_col].nunique()

        if self.add_start_end_nodes:
            graph.add_node(
                "__START__",
                event_count=0,
                case_count=total_cases,
                avg_duration_seconds=0,
            )

            graph.add_node(
                "__END__",
                event_count=0,
                case_count=total_cases,
                avg_duration_seconds=0,
            )

        for _, row in node_stats.iterrows():
            graph.add_node(
                row["event"],
                event_count=int(row["event_count"]),
                case_count=int(row["case_count"]),
                avg_duration_seconds=float(row["avg_duration_seconds"]),
                median_duration_seconds=float(row["median_duration_seconds"]),
            )

        for _, row in edge_stats.iterrows():
            graph.add_edge(
                row["source"],
                row["target"],
                transition_count=int(row["transition_count"]),
                case_count=int(row["case_count"]),
                avg_waiting_seconds=float(row["avg_waiting_seconds"]),
                median_waiting_seconds=float(row["median_waiting_seconds"]),
            )

        return graph

    # =========================
    # PyVis граф
    # =========================

    def build_pyvis_network(self) -> Network:
        node_stats = self.get_node_stats()
        edge_stats = self.get_edge_stats()

        total_cases = self.df[self.case_id_col].nunique()

        net = Network(
            height=self.height,
            width=self.width,
            directed=True,
            notebook=self.notebook,
            cdn_resources="in_line",
            bgcolor="#ffffff",
            font_color="#1f2937",
        )

        # Если выбран физический режим — включаем более жесткие настройки
        if self.layout_mode == "physics":
            net.barnes_hut(
                gravity=-9000,
                central_gravity=0.15,
                spring_length=self.level_separation,
                spring_strength=0.015,
                damping=0.95,
                overlap=1,
            )

        node_stats_map = {
            row["event"]: row
            for _, row in node_stats.iterrows()
        }

        used_nodes = set()

        if not edge_stats.empty:
            used_nodes = set(edge_stats["source"]).union(set(edge_stats["target"]))

        if self.add_start_end_nodes:
            used_nodes.add("__START__")
            used_nodes.add("__END__")

        max_event_count = max(
            node_stats["event_count"].max()
            if not node_stats.empty
            else 1,
            1
        )

        for event_name in used_nodes:
            if event_name in ["__START__", "__END__"]:
                event_count = total_cases
                case_count = total_cases
                avg_duration_seconds = 0
                median_duration_seconds = 0
            else:
                stats = node_stats_map.get(event_name)

                if stats is None:
                    continue

                event_count = int(stats["event_count"])
                case_count = int(stats["case_count"])
                avg_duration_seconds = float(stats["avg_duration_seconds"])
                median_duration_seconds = float(stats["median_duration_seconds"])

            size = 25 + 45 * (event_count / max_event_count)
            color = self._node_color(event_name)

            title = f"""
            <b>{self._node_label(event_name)}</b><br>
            Кол-во событий: {event_count}<br>
            Кол-во экземпляров: {case_count}<br>
            Средняя длительность: {self._format_seconds(avg_duration_seconds)}<br>
            Медианная длительность: {self._format_seconds(median_duration_seconds)}
            """

            net.add_node(
                event_name,
                label=self._node_display_label(
                    event_name=event_name,
                    event_count=event_count,
                    case_count=case_count,
                ),
                title=title,
                shape="box",
                size=size,
                color={
                    "background": color["background"],
                    "border": color["border"],
                    "highlight": {
                        "background": "#ffffff",
                        "border": color["border"],
                    },
                },
                borderWidth=2,
                font={
                    "size": 16,
                    "face": "Arial",
                    "color": "#1f2937",
                },
                margin=14,
            )

        max_transition_count = max(
            edge_stats["transition_count"].max()
            if not edge_stats.empty
            else 1,
            1
        )

        for _, row in edge_stats.iterrows():
            source = row["source"]
            target = row["target"]

            transition_count = int(row["transition_count"])
            case_count = int(row["case_count"])

            avg_waiting_seconds = float(row["avg_waiting_seconds"])
            median_waiting_seconds = float(row["median_waiting_seconds"])

            width = 1 + 8 * (transition_count / max_transition_count)

            title = f"""
            <b>{self._node_label(source)} → {self._node_label(target)}</b><br>
            Кол-во переходов: {transition_count}<br>
            Кол-во экземпляров: {case_count}<br>
            Среднее ожидание между событиями: {self._format_seconds(avg_waiting_seconds)}<br>
            Медианное ожидание между событиями: {self._format_seconds(median_waiting_seconds)}
            """

            label = str(transition_count)

            net.add_edge(
                source,
                target,
                label=label,
                title=title,
                arrows="to",
                color="#7b8794",
                width=width,
                smooth={
                    "type": "dynamic"
                },
                font={
                    "size": 12,
                    "face": "Arial",
                    "color": "#555555",
                    "strokeWidth": 3,
                    "strokeColor": "#ffffff",
                },
            )

        self._apply_layout_options(net)

        return net

    # =========================
    # Настройки внешнего вида
    # =========================

    def _apply_layout_options(self, net: Network):
        """
        Применяет настройки расположения графа.
        """

        if self.layout_mode == "hierarchical":
            net.set_options(
                f"""
                {{
                  "layout": {{
                    "hierarchical": {{
                      "enabled": true,
                      "direction": "UD",
                      "sortMethod": "directed",
                      "levelSeparation": {self.level_separation},
                      "nodeSpacing": {self.node_spacing},
                      "treeSpacing": 180,
                      "blockShifting": false,
                      "edgeMinimization": true,
                      "parentCentralization": false
                    }}
                  }},
                  "interaction": {{
                    "hover": true,
                    "tooltipDelay": 120,
                    "navigationButtons": true,
                    "keyboard": true,
                    "dragNodes": true,
                    "dragView": true,
                    "zoomView": true
                  }},
                  "physics": {{
                    "enabled": false
                  }},
                  "nodes": {{
                    "fixed": false,
                    "shadow": {{
                      "enabled": true,
                      "color": "rgba(0,0,0,0.15)",
                      "size": 8,
                      "x": 2,
                      "y": 2
                    }}
                  }},
                  "edges": {{
                    "smooth": {{
                      "enabled": false
                    }},
                    "shadow": {{
                      "enabled": true,
                      "color": "rgba(0,0,0,0.12)",
                      "size": 5,
                      "x": 1,
                      "y": 1
                    }}
                  }}
                }}
                """
            )

        elif self.layout_mode == "physics":
            net.set_options(
                f"""
                {{
                  "layout": {{
                    "improvedLayout": true
                  }},
                  "interaction": {{
                    "hover": true,
                    "tooltipDelay": 120,
                    "navigationButtons": true,
                    "keyboard": true,
                    "dragNodes": true,
                    "dragView": true,
                    "zoomView": true
                  }},
                  "physics": {{
                    "enabled": {str(self.physics_enabled).lower()},
                    "barnesHut": {{
                      "gravitationalConstant": -9000,
                      "centralGravity": 0.15,
                      "springLength": {self.level_separation},
                      "springConstant": 0.015,
                      "damping": 0.95,
                      "avoidOverlap": 1
                    }},
                    "stabilization": {{
                      "enabled": true,
                      "iterations": 250,
                      "fit": true
                    }}
                  }},
                  "nodes": {{
                    "shadow": {{
                      "enabled": true,
                      "color": "rgba(0,0,0,0.15)",
                      "size": 8,
                      "x": 2,
                      "y": 2
                    }}
                  }},
                  "edges": {{
                    "smooth": {{
                      "enabled": true,
                      "type": "dynamic"
                    }},
                    "shadow": {{
                      "enabled": true,
                      "color": "rgba(0,0,0,0.12)",
                      "size": 5,
                      "x": 1,
                      "y": 1
                    }}
                  }}
                }}
                """
            )

        else:
            raise ValueError(
                "layout_mode должен быть 'hierarchical' или 'physics'"
            )

    # =========================
    # Отображение и сохранение
    # =========================

    def show(self):
        """
        Показать граф в Jupyter Notebook.
        """

        output_path = self.save()
        graph_html = output_path.read_text(encoding="utf-8")
        graph_srcdoc = html.escape(graph_html, quote=True)

        display(
            HTML(
                f"""
                <iframe
                    srcdoc="{graph_srcdoc}"
                    width="100%"
                    height="760"
                    style="border: 1px solid #d0d5dd; border-radius: 8px;"
                ></iframe>
                """
            )
        )

    def save(self) -> Path:
        """
        Сохранить граф в HTML.
        """

        net = self.build_pyvis_network()

        output_path = self.output_dir / self.filename
        net.save_graph(str(output_path))

        return output_path

    def summary(self) -> dict:
        """
        Краткая статистика по процессу.
        """

        edge_stats = self.get_edge_stats()
        node_stats = self.get_node_stats()

        return {
            "cases": int(self.df[self.case_id_col].nunique()),
            "events_total": int(len(self.df)),
            "unique_events": int(self.df[self.event_col].nunique()),
            "transitions": int(len(edge_stats)),
            "most_frequent_events": node_stats.sort_values(
                by="event_count",
                ascending=False
            ).head(10),
            "most_frequent_transitions": edge_stats.sort_values(
                by="transition_count",
                ascending=False
            ).head(10),
        }
