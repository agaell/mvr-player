# Участие в разработке

Спасибо за интерес к MVR Player.

## Как работать с проектом

1. Создайте виртуальное окружение.
2. Установите проект в editable-режиме.
3. Запускайте тесты перед изменениями, которые затрагивают код.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests
```

На Windows используйте `.venv\Scripts\activate` вместо `source`.
