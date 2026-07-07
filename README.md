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

## Разработка

```bash
pip install -e .
python -m unittest discover -s tests
```
