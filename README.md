# Sprint Health

Репозиторий содержит решение для хакатона T1 по треку "SprintHealth: Инновационный Анализ для Agile-команд". Вся логика приложения реализована в файле db 7.py.

Ссылка на сайт: https://849b-188-186-138-160.ngrok-free.app

## db 7

Код представляет собой приложение Dash, которое выводит статистику спринтов и оценивает их "здоровье". В проекте использовались следующие библиотеки:

* **base64:** Используется для кодирования и декодирования данных в формате base64, что полезно при работе с загружаемыми файлами.
* **io:** Предоставляет возможности для работы с потоками ввода-вывода, позволяя нам одновременно обрабатывать данные в памяти.
* **pandas:** Библиотека для работы с данными. Мы используем ее для загрузки и обработки CSV-файлов.
* **dash:** Библиотека для создания интерактивных веб-приложений на Python.
* **plotly.graph_objects**: Библиотека для создания графиков. Мы используем ее для построения интерактивных графиков на основе данных.

Опишем основные функции:

* **classify_status:** Эта функция принимает статус задачи и ищет его в словаре.
* **load_csv_with_table_prefix:** Эта функция принимает закодированные данные CSV и возвращает очищенный DataFrame или `None`, если произошла ошибка.
* **analyze_status_by_day:** Функция предназначена для анализа распределения задач по статусам, изменений в бэклоге и количества заблокированных задач в рамках спринта для выбранного дня.
* **analyze_sprint_health:** Функция анализа состояния спринта.
* **upload_files:** Функция загрузки файлов.

Помимо этого, в коде используются Callbacks для построения графика и вывода текстовых данных, загрузки файлов, обновления списка спринтов.

![image](https://github.com/user-attachments/assets/f4a046ed-bd3f-460c-83e6-b4c4a257c178)

<div align="center">Пример работы приложения</div>







