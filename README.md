# MVR Player

MVR Player — кроссплатформенная программа на Python для просмотра `.mvr`
файлов и конвертации их в `.mp4`.

Проект находится на раннем этапе. Сейчас реализован только базовый каркас и
запуск пустого окна Tkinter с названием **MVR Player**.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m mvr_player.main
```

На Windows используйте `.venv\Scripts\activate` вместо `source`.

Команду нужно запускать из корня проекта `mvr-player`.

Если кажется, что запускается старая версия, проверьте пути:

```bash
python3 -m mvr_player.main --debug-paths
```

В выводе `ui` должен указывать на `src/mvr_player/ui.py` внутри этого проекта.

Приложение использует встроенный FFmpeg из зависимости `imageio-ffmpeg`,
поэтому системный `ffmpeg` не обязателен.

Файл можно открыть кнопкой, через меню или перетащить в окно. После открытия
воспроизведение запускается автоматически.

Для обновления зависимостей проекта:

```bash
pip install -e .
```

## Разработка

```bash
pip install -e .
python -m unittest discover -s tests
```
