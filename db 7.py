import base64
import io
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, ctx
import plotly.graph_objects as go

# Инициализация приложения Dash
app = Dash(__name__)

# Хранилище данных
data_store = {}

# Классификация статусов
status_categories = {
    "К выполнению": ["created", "analysis", "design", "readyForDevelopment"],
    "В работе": ["inProgress", "development", "fixing", "testing", "review", "localization",
                 "waiting", "st", "stCompleted", "ift", "at", "introduction", "verification", "hold"],
    "Сделано": ["done", "closed"],
    "Снято": ["rejectedByThePerformer", "Отменен инициатором", "Отклонено", "Дубликат"]
}


def classify_status(status):
    """Классифицируем статус задачи."""
    for category, statuses in status_categories.items():
        if status in statuses:
            return category
    return


def load_csv_with_table_prefix(decoded, delimiter=';'):
    try:
        df = pd.read_csv(
            io.StringIO(decoded.decode('utf-8')),
            skiprows=1,  # Пропуск строки "Table 1"
            delimiter=delimiter,
            on_bad_lines='skip'  # Пропуск некорректных строк
        )
        df.columns = df.columns.str.strip()  # Удаляем лишние пробелы из названий столбцов
        df.columns = df.columns.str.replace(r'\s+', '_', regex=True)  # Заменяем пробелы на "_"
        return df
    except Exception as e:
        print(f"Ошибка обработки файла: {e}")
        return None


def analyze_status_by_day(sprint_name, selected_day, history_df, sprints_df, entities_df):
    """Анализ распределения задач по статусам, изменение бэклога и заблокированные задачи для выбранного дня."""
    # Получаем данные о спринте
    sprint_data = sprints_df[sprints_df['sprint_name'] == sprint_name]
    if sprint_data.empty:
        return "Спринт не найден", {}, 0, 0

    # Явное преобразование дат для
    sprint_data.loc[:, 'sprint_start_date'] = pd.to_datetime(sprint_data['sprint_start_date'],
                                 format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')
    sprint_data.loc[:, 'sprint_end_date'] = pd.to_datetime(sprint_data['sprint_end_date'],
                                                           format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')

    sprint_start = sprint_data['sprint_start_date'].iloc[0]
    sprint_end = sprint_data['sprint_end_date'].iloc[0]

    current_date = sprint_start + pd.Timedelta(days=selected_day)

    history_df.loc[:, 'history_date'] = pd.to_datetime(history_df['history_date'], format='%m/%d/%y %H:%M',
                                                       errors='coerce')
    # Фильтруем изменения бэклога
    backlog_changes = history_df[history_df['history_change'].str.lower().str.contains("бэклог", na=False)]
    backlog_changes = backlog_changes[backlog_changes['history_date'] <= current_date]

    # Начальное состояние бэклога
    initial_backlog = backlog_changes[backlog_changes['history_date'] <= (sprint_start + pd.Timedelta(days=2))]
    initial_sum = initial_backlog['history_change'].apply(
        lambda x: int(''.join(filter(str.isdigit, x))) if any(c.isdigit() for c in x) else 0).sum()

    # Текущее состояние бэклога
    current_sum = backlog_changes['history_change'].apply(
        lambda x: int(''.join(filter(str.isdigit, x))) if any(c.isdigit() for c in x) else 0).sum()

    # Изменение бэклога
    backlog_change_percent = ((current_sum - initial_sum) / initial_sum * 100) if initial_sum > 0 else 0

    # Анализ изменений статусов
    status_changes = history_df[
        (history_df['history_property_name'].str.lower() == "статус") & (history_df['history_date'] <= current_date)]
    status_changes = status_changes.copy()  # Создаем копию для избегания SettingWithCopyWarning

    status_changes.loc[:, 'end_status'] = status_changes['history_change'].str.split(" -> ").str[1]
    status_changes.loc[:, 'status_category'] = status_changes['end_status'].apply(classify_status)

    # Распределение задач по категориям
    status_distribution = status_changes['status_category'].value_counts(normalize=True) * 100

    for category in status_categories.keys():
        if category not in status_distribution:
            status_distribution[category] = 0

    status_distribution = status_distribution.sort_index()

    # Заблокированные задачи
    blocked_tasks = history_df[history_df['history_change'].str.contains("isBlockedBy", case=False, na=False)]
    blocked_tasks_current = blocked_tasks[blocked_tasks['history_date'] <= current_date]
    blocked_count = blocked_tasks_current['entity_id'].nunique()

    return "Анализ выполнен", status_distribution.to_dict(), 0, blocked_count, backlog_change_percent

def analyze_sprint_health(distribution, backlog_change):
    health_issues = []

    # Проверка равномерности перехода статусов
    if distribution.get("К выполнению", 0) > 20:
        health_issues.append("Параметр 'К выполнению' превышает 20% от общего объема.")

    if distribution.get("Снято", 0) > 10:
        health_issues.append("Параметр 'Снято' превышает 10% от общего объема.")

    if backlog_change > 20:
        health_issues.append("Бэклог изменился более чем на 20% после начала спринта.")

    if distribution.get("Сделано", 0) > 50 and max(distribution.values()) == distribution.get("Сделано"):
        health_issues.append("Объекты массово переводятся в статус 'Сделано'.")

    # Итоговый вывод
    if not health_issues:
        return "Спринт в хорошем состоянии. Все параметры соответствуют заданным критериям."
    else:
        return "Обнаружены проблемы:\n" + "\n".join(health_issues)
# Основной макет интерфейса
app.layout = html.Div([
    html.H1("Дашборд для анализа спринтов", style={'text-align': 'center', 'margin-bottom': '20px'}),

    # Хранилище состояния
    dcc.Store(id='file-upload-status', data={'sprints': False, 'entities': False, 'history': False}),

    html.Div([
        html.Div([
            html.Label("Загрузите файл sprints (CSV):", style={'margin-bottom': '5px'}),
            dcc.Upload(
                id='upload-sprints',
                children=html.Button('Загрузить sprints'),
                multiple=False
            ),
        ], style={'margin-right': '20px', 'margin-bottom': '10px'}),

        html.Div([
            html.Label("Загрузите файл entities (CSV):", style={'margin-bottom': '5px'}),
            dcc.Upload(
                id='upload-entities',
                children=html.Button('Загрузить entities'),
                multiple=False
            ),
        ], style={'margin-right': '20px', 'margin-bottom': '10px'}),

        html.Div([
            html.Label("Загрузите файл history (CSV):", style={'margin-bottom': '5px'}),
            dcc.Upload(
                id='upload-history',
                children=html.Button('Загрузить history'),
                multiple=False
            ),
        ], style={'margin-bottom': '10px'}),
    ], style={'display': 'flex', 'align-items': 'flex-start', 'margin-bottom': '30px'}),

    # Сообщения о загрузке
    html.Div(id='sprints-upload-message', style={'margin-bottom': '10px'}),
    html.Div(id='entities-upload-message', style={'margin-bottom': '10px'}),
    html.Div(id='history-upload-message', style={'margin-bottom': '20px'}),

    # Выбор спринта
    html.Label("Выберите спринт:", style={'font-weight': 'bold', 'margin-bottom': '10px'}),
    dcc.Dropdown(id='sprint-dropdown', multi=False, style={'margin-bottom': '20px'}),

    # Слайдер для выбора дня
    html.Label("Выберите день спринта:", style={'font-weight': 'bold', 'margin-bottom': '10px'}),
    html.Div(
        dcc.Slider(
            id='day-slider',
            min=1,
            max=14,
            step=1,
            marks={i: f"День {i}" for i in range(15)},
            value=0
        ),
        style={'margin-bottom': '30px'}
    ),

    # График распределения задач
    dcc.Graph(id='status-distribution', style={'margin-top': '20px', 'margin-bottom': '30px','background-color': 'azure'}),

    # Вывод изменения бэклога, заблокированных задач
    html.Div([
        html.Div(id='backlog-change-text', style={'margin-bottom': '10px', 'font-weight': 'bold'}),
        html.Div(id='blocked-tasks-text', style={'margin-bottom': '10px', 'font-weight': 'bold'}),
    ]),

    html.Div(id='sprint-health-text', style={'margin-top': '10px', 'font-weight': 'bold', 'color': 'red'}),],
    style = {
    'background-color': 'azure',  # Устанавливаем лазурный цвет фона
    'padding': '20px',  # Отступы от краев
    'font-family': 'Arial, sans-serif'  # Шрифт для улучшения визуального стиля
}
)


# Callback для загрузки файлов
@app.callback(
    [Output('sprints-upload-message', 'children'),
     Output('entities-upload-message', 'children'),
     Output('history-upload-message', 'children'),
     Output('file-upload-status', 'data')],
    [Input('upload-sprints', 'contents'),
     Input('upload-entities', 'contents'),
     Input('upload-history', 'contents')],
    [State('upload-sprints', 'filename'),
     State('upload-entities', 'filename'),
     State('upload-history', 'filename'),
     State('file-upload-status', 'data')]
)
def upload_files(sprints_content, entities_content, history_content, sprints_filename, entities_filename,
                 history_filename, upload_status):
    trigger = ctx.triggered_id
    if trigger == 'upload-sprints' and sprints_content:
        content_type, content_string = sprints_content.split(',')
        decoded = base64.b64decode(content_string)
        df = load_csv_with_table_prefix(decoded, delimiter=';')
        if df is not None:
            data_store['sprints-Table 1'] = df
            upload_status['sprints'] = True
            return "Файл sprints успешно загружен!", "", "", upload_status

    elif trigger == 'upload-entities' and entities_content:
        content_type, content_string = entities_content.split(',')
        decoded = base64.b64decode(content_string)
        df = load_csv_with_table_prefix(decoded, delimiter=';')
        if df is not None:
            data_store['data_for_spb_hakaton_entities1-Table 1'] = df
            upload_status['entities'] = True
            return "", "Файл entities успешно загружен!", "", upload_status

    elif trigger == 'upload-history' and history_content:
        content_type, content_string = history_content.split(',')
        decoded = base64.b64decode(content_string)
        df = load_csv_with_table_prefix(decoded, delimiter=';')
        if df is not None:
            data_store['history-Table 1'] = df
            upload_status['history'] = True
            return "", "", "Файл history  успешно загружен!", upload_status

    return "", "", "", upload_status

# Callback для обновления списка спринтов
@app.callback(
    Output('sprint-dropdown', 'options'),
    Input('file-upload-status', 'data')
)
def update_sprint_dropdown(upload_status):
    if upload_status['sprints']:
        sprints_df = data_store['sprints-Table 1']
        if 'sprint_name' in sprints_df.columns:
            sprint_options = [{'label': sprint, 'value': sprint} for sprint in sprints_df['sprint_name'].unique()]
            return sprint_options
    return []

## Callback для построения графика и вывода текстовых данных
@app.callback(
    [Output('status-distribution', 'figure'),
     Output('backlog-change-text', 'children'),
     Output('blocked-tasks-text', 'children'),
     Output('sprint-health-text', 'children')],
    [Input('sprint-dropdown', 'value'),
     Input('day-slider', 'value')]
)
def update_status_distribution(selected_sprint, selected_day):
    if not selected_sprint:
        return go.Figure(), "Выберите спринт и день для анализа.", "Заблокировано задач в Ч/Д: 0", "Не удалось выполнить анализ здоровья спринта."

    history_df = data_store['history-Table 1']
    sprints_df = data_store['sprints-Table 1']
    entities_df = data_store['data_for_spb_hakaton_entities1-Table 1']

    message, distribution, backlog_change, blocked_count, backlog_change_percent = analyze_status_by_day(
        selected_sprint, selected_day, history_df, sprints_df, entities_df)
    if message != "Анализ выполнен":
        return go.Figure(), "Ошибка анализа данных.", "Заблокировано задач в Ч/Д: 0", "Не удалось выполнить анализ здоровья спринта."

    sprint_health = analyze_sprint_health(distribution, backlog_change_percent)

    fig = go.Figure()
    for category, percentage in distribution.items():
        fig.add_trace(go.Bar(
            x=[percentage],
            y=["Прогресс"],
            name=category,
            orientation='h',
            text=f"{percentage:.1f}%",
            textposition='inside'
        ))

    # Настройка оформления графика
    fig.update_layout(
        barmode='stack',
        title=f"Распределение задач: День {selected_day}",
        xaxis_title="Процент задач",
        yaxis_title="Категории",
        xaxis=dict(tickformat=".0f"),
        height=400
    )

    backlog_text = f"Изменение бэклога с начала спринта: {backlog_change_percent:.1f}%"
    blocked_text = f"Заблокировано задач в Ч/Д: {blocked_count}"

    return fig, backlog_text, blocked_text, sprint_health


if __name__ == '__main__':
    app.run_server(debug=True)


