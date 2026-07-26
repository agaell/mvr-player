<p align="center">
  <img src="assets/main_logo.png" alt="Логотип MVR Player" width="680">
</p>

<h1 align="center">MVR Player</h1>

<p align="center">
  Удобная программа для просмотра файлов <code>.mvr</code> и сохранения видео в формате <code>.mp4</code>.
</p>

<p align="center">
  <a href="https://github.com/agaell/mvr-player/releases/latest">
    <img src="https://img.shields.io/github/v/release/agaell/mvr-player?display_name=tag&sort=semver&style=flat-square" alt="Последний релиз">
  </a>
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-111827?style=flat-square" alt="Поддерживаемые платформы">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9 и новее">
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="Лицензия MIT">
  </a>
</p>

MVR Player позволяет просматривать видеофайлы в формате <code>.mvr</code>, быстро 
перемещаться по видео и при необходимости конвертировать его в привычный формат <code>.mp4</code>.
Для начала работы скачайте последнюю версию программы и откройте файл для просмотра.

## Скачать

### [Скачать последнюю версию MVR Player](https://github.com/agaell/mvr-player/releases/latest)

1. Откройте страницу последнего Release.
2. Скачайте файл для своей операционной системы.
3. Распакуйте архив.
4. Запустите MVR Player.


## Возможности

- просмотр видеофайлов в формате `.mvr`;
- быстрая навигация по видео;
- полноэкранный режим;
- выбор папки и поиск `.mvr` во всех вложениях;
- дерево найденных файлов с открытием одним нажатием;
- конвертация выбранного файла в `.mp4`;


## Скриншоты

<p align="center">
  <img src="assets/screenshots/main-window.png" alt="Главное окно MVR Player" width="100%">
</p>

<p align="center"><em>Главное окно MVR Player</em></p>

## Как пользоваться

1. Запустите MVR Player.
2. Перетащите `.mvr` в окно или нажмите **Открыть**.
3. Выберите файл или папку с записями.
4. Если открыта папка, выберите нужное видео в панели справа.
5. Используйте шкалу времени и кнопки Play, Pause и Stop для просмотра.
6. Чтобы сохранить видео, нажмите **Конвертировать в MP4** и выберите папку.

Двойное нажатие по видео включает полноэкранный режим. Для выхода нажмите
`Esc` или снова дважды нажмите по видео.

## Сборка

Понадобится Python 3.9 или новее:

**macOS и Linux**

```bash
git clone https://github.com/agaell/mvr-player.git
cd mvr-player
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m mvr_player.main
```

**Windows**

```powershell
git clone https://github.com/agaell/mvr-player.git
cd mvr-player
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m mvr_player.main
```

## Roadmap

- [x] Просмотр и управление воспроизведением `.mvr`.
- [x] Перемотка и полноэкранный режим.
- [x] Поиск файлов в папках и подпапках.
- [x] Конвертация в `.mp4` с отображением прогресса.
- [ ] Пакетная конвертация нескольких файлов.
- [ ] Расширение совместимости с вариантами формата MVR.
- [ ] Автоматическая проверка обновлений.
- [ ] Дополнительные языки интерфейса.

Предложения и сообщения об ошибках можно оставить в
[GitHub Issues](https://github.com/agaell/mvr-player/issues).

## Лицензия

MVR Player распространяется по лицензии [MIT](LICENSE). Программу можно
использовать, изменять и распространять с сохранением текста лицензии.
