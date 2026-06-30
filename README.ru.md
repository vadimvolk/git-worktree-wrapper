<!-- Language switcher -->
[English](README.md) | **Русский**

> ⚠️ **Предупреждение**: GWW недостаточно протестирован, используйте на свой страх и риск!

# 🚀 GWW — Git Worktree Wrapper

![Tests](https://github.com/vadimvolk/git-worktree-wrapper/actions/workflows/ci.yml/badge.svg)

CLI-инструмент, который оборачивает функциональность `git worktree`, добавляя настраиваемые шаблоны путей, маршрутизацию на основе условий и действия, специфичные для проекта.

## ✨ Возможности

- **📝 Настраиваемые шаблоны путей**: Динамическая генерация путей с использованием шаблонов и функций вроде `path(n)`, `branch()`, `norm_branch()`, `tag()`
- **🔄 Маршрутизация на основе условий**: Размещение репозиториев в разные локации по условиям URI (host, path, protocol, tags)
- **🏷️ Поддержка тегов**: Передавайте пользовательские теги через опцию `--tag` для условной маршрутизации и организации путей
- **⚙️ Действия проекта**: Выполнение пользовательских действий (копирование файлов, команды) после клонирования или создания worktree
- **🐚 Автодополнение shell**: Поддержка completion для Bash, Zsh и Fish

## 📋 Требования

- 🐍 Python 3.11+
- 🔧 Git
- 🖥️ Unix-подобная система (Linux, macOS)

## 📦 Установка

### Установить CLI (рекомендуется)

#### Через uv

```bash
uv tool install "git+https://github.com/vadimvolk/git-worktree-wrapper.git"
gww --help
```

#### Через pipx

```bash
pipx install "git+https://github.com/vadimvolk/git-worktree-wrapper.git"
gww --help
```

### Из исходников (для разработки)

```bash
# Клонируйте репозиторий
git clone git@github.com:vadimvolk/git-worktree-wrapper.git
cd git-worktree-wrapper

# Установите зависимости через uv
uv sync

# Запустите gww
uv run gww --help
```

### Из исходников через pip

```bash
# Из локальной копии репозитория
cd git-worktree-wrapper
python -m pip install .
gww --help
```

## 🚀 Быстрый старт

### 1. ⚙️ Инициализировать конфигурацию

```bash
gww init config
```

Это создаст конфигурационный файл по умолчанию в `~/.config/gww/config.yml` (Linux), `~/Library/Application Support/gww/config.yml` (macOS) или `%APPDATA%\gww\config.yml` (Windows). На любой платформе установка `XDG_CONFIG_HOME` в абсолютный путь переопределяет путь по умолчанию и сохраняет конфиг там. Отредактируйте эти 2 значения: `default_sources` и `default_worktrees`. Проверьте [раздел с руководством](#tutorial) для деталей маршрутизации.

### 2. 🐚 Инициализировать интеграцию с shell

```bash
gww init shell zsh  # или bash, или fish
```

Это установит автодополнение и алиасы (`gwc`, `gwa`, `gwr`) для более удобной работы. Следуйте инструкциям, выведенным командой, чтобы включить их в вашем shell.

### 3. 📥 Клонировать репозиторий

```bash
gwc https://github.com/user/repo.git
# Запрашивает: "Navigate to ~/Developer/sources/github/user/repo? [Y/n]"
# Переходит, если вы подтверждаете (по умолчанию: да)
```

### 4. ➕ Добавить worktree

```bash
cd ~/Developer/sources/github/user/repo
gwa feature-branch
# Запрашивает: "Navigate to ~/Developer/worktrees/github/user/repo/feature-branch? [Y/n]"
# Переходит, если вы подтверждаете (по умолчанию: да)
```

### 5. ➖ Удалить worktree

```bash
gwr feature-branch
# Если в worktree есть незакоммиченные изменения или неотслеживаемые файлы:
#   Запрашивает: "Force removal? [y/N]"
#   Удаляет с --force, если вы подтверждаете
# Иначе: Удаляет worktree немедленно
# Вывод: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 6. 🔄 Обновить исходный репозиторий

```bash
gww pull
# Вывод: Updated source repository: ~/Developer/sources/github/user/repo
```

**Примечание**: `gww pull` обновляет исходный репозиторий даже из worktree, при условии что исходный репозиторий чист и находится на ветке `main` или `master`. Полезно для сценариев merge/rebase.
```bash
gww pull # из любого worktree репозитория
git rebase main # перебазировать ваши текущие изменения на обновленную ветку main
```

### 7. 🚚 Мигрировать репозитории
Сначала создайте резервную копию!

```bash
gww migrate ~/old-repos --dry-run
# Вывод:
# Would migrate 5 repositories:
#   ~/old-repos/repo1 -> ~/Developer/sources/github/user/repo1
#   ...

gww migrate ~/old-repos
# Копирование (по умолчанию): список, копирование sources затем worktrees, repair, итог

gww migrate ~/old-repos --inplace
# Перемещение worktrees затем sources, repair, очистка пустых папок
```

Команда `migrate` сканирует одну или несколько директорий на наличие git-репозиториев и мигрирует их в локации на основе вашей текущей конфигурации. Полезна когда:
- Вы обновили конфигурацию и хотите реорганизовать существующие репозитории
- Вы переходите с ручного управления репозиториями на GWW
- Вам нужно объединить репозитории из разных локаций

**Опции**:
- `--dry-run`, `-n`: Показать что будет мигрировано без внесения изменений
- `--copy` (по умолчанию): Копировать репозитории в новые локации; список, проверка, копирование sources затем worktrees, `git worktree repair`, итог. Без очистки папок.
- `--inplace`: Переместить репозитории на место (сначала worktrees, затем sources), `git worktree repair`, затем рекурсивно очистить пустые исходные папки.

**Поведение**:
- Принимает один или несколько путей; сканирует каждый и объединяет списки репозиториев (без дубликатов)
- Классифицирует каждый репозиторий как source или worktree; для sources используется шаблон пути source, для worktrees — шаблон worktree
- **--inplace**: Два прохода (worktrees затем sources), перемещение и repair, затем удаление освободившихся директорий и пустых родителей до корней ввода
- **--copy**: Список sources и worktrees, проверка назначений, копирование sources затем worktrees, восстановление связей через repair, итог
- Пропускает репозитории без remote, worktrees с detached HEAD или уже в целевой локации

## Tutorial

Минимальный конфигурационный файл выглядит так:
```yaml
# Папка, куда все исходники клонируются с помощью gwc. path(-2)/path(-1) генерирует 2-уровневые подпапки на основе URI репозитория. Например https://github.com/user/repo.git -> ~/Developer/sources/user/repo
default_sources: ~/Developer/other/sources/path(-2)/path(-1)
# Папка, куда все worktree клонируются с помощью gwa. norm_branch() лучше работает с удаленными ветками, например origin/remote-branch -> origin-remote-branch
default_worktrees: ~/Developer/other/worktrees/path(-2)/path(-1)/norm_branch()
```
Сгенерированный файл будет иметь больше опций в комментариях, включая справочник функций.

### Checkout на основе того, где размещен репозиторий
Полезно для разделения, например, open source проектов (где вы учитесь или черпаете вдохновение) от ваших рабочих проектов.
```yaml
# Все еще нужен на случай, если конфигурация не найдет секцию. Вы можете предпочесть невложенную структуру sources, но убедитесь, что результирующая папка уникальна
default_sources: ~/Developer/sources/host()-path(-2)-path(-1)
default_worktrees: ~/Developer/worktrees/host()-path(-2)-path(-1)-norm_branch()
sources:
  # ... другие правила
  work:
    when: "your.org.host" in host()
    sources: ~/Developer/work/sources/path(-2)-path(-1)
    worktrees: ~/Developer/work/sources/path(-2)-path(-1)-norm_branch()
  
```
Этого достаточно, чтобы разделить рабочие исходники от всех остальных, но вы можете создать больше секций с различными правилами. Библиотека использует [simpleeval](https://github.com/danthedeckie/simpleeval) для оценки шаблонов, поэтому вы можете использовать его [операторы](https://github.com/danthedeckie/simpleeval?tab=readme-ov-file#operators) и функции ниже для получения необходимой маршрутизации.

#### 🌐 Функции URI (доступны в шаблонах и условиях `when`)

| Function | Description | Example |
|----------|-------------|---------|
| `uri()` | Получить полную строку URI | `uri()` → `"https://loca-repo-manager.com:8081/user/repo.git"` |
| `host()` | Получить hostname URI | `host()` → `"loca-repo-manager.com"` |
| `port()` | Получить порт URI (пустая строка, если не указан) | `port()` → `"8081"` или `""` обычно |
| `protocol()` | Получить протокол/схему URI | `protocol()` → `"https"` / `"ssh"` / `git` |
| `path(n)` | Получить сегмент пути URI по индексу (0-based, отрицательные — с конца) | `path(-1)` → `"repo"`, `path(0)` → `"user"` |

#### 🌿 Функции веток (доступны в шаблонах)

| Function | Description | Example |
|----------|-------------|---------|
| `branch()` | Получить имя текущей ветки | `branch()` → `"feature/new/ui"` |
| `norm_branch(replacement)` | Имя ветки с заменой `/` (по умолчанию: `"-"`) | `norm_branch()` → `"feature-new-ui"`, `norm_branch("_")` → `"feature_new_ui"` |

Нужно клонировать временные проекты отдельно? Добавьте это в вашу конфигурацию:
```yml
sources:
  # ... другие правила
  temp:
    when: tag_exist("temp")  # См. [раздел тегов](#-tags) для деталей о тегах
    sources: ~/Downloads/temp/sources/time_id()-host()-path(-2)-path(-1) 
    worktrees: ~/Downloads/temp/worktrees/time_id()-host()-path(-2)-path(-1)-norm-branch()
```
`time_id(fmt)` генерирует идентификатор на основе даты/времени (кэшируется в рамках одной оценки шаблона). Формат по умолчанию — `"20260120-2134.03"` (короткий, с точностью до секунд уникальный). Используйте [коды формата](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) для более детальных/вложенных результатов. Работает правильно при многократном использовании.
```yml
worktrees: ~/Downloads/temp/worktrees/time_id("%Y")/time_id("%m")/time_id("%H-%M$.%S")/host()-path(-2)-path(-1)-norm-branch()
```
Генерирует вложенную структуру: `YYYY/HH-MM.ss/host()-path(-2)-path(-1)-norm-branch()`


#### ⚙️ Действия (доступны в секции `actions`)
Запускать действия после клонирования репозитория, после добавления worktree или **перед удалением worktree**. Распространенный пример: копирование `local.properties` для проектов Gradle.
```yml
actions:
  - when: file_exists("settings.gradle") # Проверить, что это действительно проект Gradle
    after_clone:
      - copy: ["~/sources/default-local.properties", "local.properties"] # Копирует ваш файл по умолчанию сразу после клонирования репозитория
    after_add:
      - copy: ["source_path('local.properties')", "local.properties"] # Наследовать существующий файл репозитория в worktree
```
Вы можете иметь несколько подсекций `when` в действиях. После clone/add библиотека проходит сверху вниз и выполняет все действия с соответствующими условиями `when`.
Другие функции, доступные в секции действий:
| Action | Description | Example |
|--------|-------------|---------|
| `copy` | Копировать файл или дерево каталогов из шаблонного источника в шаблонное назначение (относительно `current_worktree()`) | `copy: ["source_path('local.properties')", "local.properties"]` или `copy: ["~/sources/default-local.properties", "local.properties"]` |
| `command` | Выполнить внешнюю команду (запускается в директории назначения, функции шаблонов доступны) | `command: "npm install"` или `command: "claude init"` |

Каждое правило действий также принимает необязательный флаг `critical:` (по умолчанию `true`). Когда `true`, ошибка в любом действии правила прерывает оставшиеся действия этого правила и команда завершается с кодом `1`. Установите `critical: false` для некритичных правил — ошибки сообщаются в сводке выполнения действий, но команда всё равно завершается с `0`. Полную таблицу кодов выхода см. в [Обработке ошибок](#-обработка-ошибок) ниже.
```yml
actions:
  - when: file_exists("package.json")
    critical: false  # некритичное правило: отсутствие node_modules неприятно, но не фатально
    after_clone:
      - command: "npm install"
```

##### 🪓 `before_remove` — действия очистки перед `gww remove`
Третий вид действий, `before_remove`, запускает пользовательские шаги очистки **до** того, как `git worktree remove` удалит worktree. Используйте его для архивации worktree, отправки уведомления, запуска хука и т. п. Применяется тот же механизм `critical:` / `command:` / `copy:`; критичная ошибка `before_remove` прерывает удаление и завершается с кодом `1`, некритичная ошибка сообщается, но удаление всё равно продолжается. `--force` действует только на git и *не* обходит `before_remove`.

В правилах `before_remove` `current_worktree()` — это удаляемый worktree, `source_path()` — родительский исходный репозиторий, а `branch()` возвращает текущую ветку worktree (или `""` для отсоединённого HEAD). Команда `gww remove` также принимает `--tag key=value`, который попадает в предикаты `tag()` / `tag_exist()`, так что очистка для конкретного вызова может управляться тегами.

```yml
actions:
  # Критичное: заархивировать worktree перед тем, как `gww remove` его удалит.
  - when: 'tag_exist("archive")'
    before_remove:
      - command: "tar -czf ~/archives/norm_branch()-time_id('%Y%m%d').tar.gz current_worktree()"

  # Некритичное: уведомить Slack. Ошибка уведомления не должна блокировать удаление.
  - when: tag("notify") == "slack"
    critical: false
    before_remove:
      - command: "curl -sf -X POST https://hooks.slack.com/... -d branch=branch()"

  # Удаление по пути: когда удаляем по абсолютному пути, `branch()` всё равно разрешается.
  - when: branch() == "main"
    before_remove:
      - command: "echo refusing to remove main branch"
```
> Примечание: `gww remove` принимает как абсолютный путь к worktree, так и имя ветки. При вызове с путём `branch()` читает текущую ветку worktree через `git rev-parse --abbrev-ref HEAD` и возвращает `""` для отсоединённого HEAD, поэтому предикаты с `branch()` никогда не падают.

#### ❗ Обработка ошибок
Ошибки действий сообщаются по правилам, сгруппированно в конце цикла действий в stderr как **сводка выполнения действий**. Сводка перечисляет каждое упавшее правило по его индексу в `actions:`, флагу критичности и ошибке упавшего действия. Непустота сводки также блокирует строку успеха: `say()` (строка, в которую скрипты делают `cd $(gwc …)`) подавляется, если в сводке есть хотя бы одна запись, поэтому `cd` всегда попадает в полностью настроенный worktree.

| Исход | Код выхода |
|---|---|
| Чистое выполнение (без ошибок) | `0` |
| Только ошибка некритичного правила | `0` |
| Ошибка критичного правила | `1` |
| Не удалось вычислить предикат `when:` или шаблон `command:` | `2` |

#### 📁 Функции действий (доступны в действиях `command` и условиях `when`)

| Function | Description | Example |
|----------|-------------|---------|
| `source_path(extra?)` | Получить абсолютный путь к исходному репозиторию, опционально с присоединённым `extra` | `source_path()` → `"/path/to/repo"`, `source_path("local.properties")` → `"/path/to/repo/local.properties"` |
| `current_worktree(extra?)` | Получить абсолютный путь к текущему worktree, опционально с присоединённым `extra` | `current_worktree()` → `"/path/to/worktree"`, `current_worktree("local.properties")` → `"/path/to/worktree/local.properties"` |
| `file_exists(path)` | Проверить наличие файла относительно исходного репозитория | `file_exists("local.properties")` → `True` |
| `dir_exists(path)` | Проверить наличие директории относительно исходного репозитория | `dir_exists("config")` → `True` |
| `path_exists(path)` | Проверить наличие пути (файл или директория) относительно исходного репозитория | `path_exists("local.properties")` → `True` |

#### 🏷️ Теги

Все еще недостаточно гибко? Вот теги. Теги указываются с помощью параметра командной строки `-t <tag-name>[=optional value]` (или `--tag`) для команд clone / add. Теги доступны в конфигурации с помощью:

| Function | Description | Example |
|----------|-------------|---------|
| `tag(name)` | Получить значение тега по имени (возвращает пустую строку, если не задан) | `tag("env")` → `"prod"` |
| `tag_exist(name)` | Проверить, существует ли тег (возвращает boolean) | `tag_exist("env")` → `True` |

**🏷️ Пример использования тегов**:
```yaml
sources:
  # Временная копия: Клонировать репозитории в ~/Downloads/temp для быстрого доступа
  # Использование: gwc <uri> -t temp
  temp:
    when: 'tag_exist("temp")'
    sources: ~/Downloads/temp/time_id()-host()-path(-1)
    worktrees: ~/Downloads/temp/time_id()-host()-path(-1)/norm_branch()

  # Worktree для code review: Добавить worktree в ~/Developer/worktree/code-review для задач ревью
  # Использование: gwa <branch> --tag review
  review:
    when: 'tag_exist("review")'
    worktrees: ~/Developer/review/worktree/path(-1)/norm_branch()
    # Если используется во время clone, используется путь источника по умолчанию
```
```

```bash
# Клонировать во временную локацию
gwc https://github.com/user/repo.git -t temp
# Output: ~/Downloads/temp/repo

# Добавить worktree для code review
cd ~/Developer/sources/github/user/repo
gwa feature-branch --tag review
# Output: ~/Developer/worktree/code-review/repo/feature-branch
```

## 📖 Команды

| Command | Description |
|---------|-------------|
| `gwc <uri> [--tag key=value]...` | 📥 Клонировать репозиторий в настроенную локацию (теги доступны в шаблонах/условиях) |
| `gwa <branch> [-c] [--tag key=value]...` | ➕ Добавить worktree для ветки (опционально создать ветку, теги доступны в шаблонах/условиях) |
| `gwr <branch\|path> [-f] [--tag key=value]...` | ➖ Удалить worktree (теги доступны в `before_remove`-предикатах) |
| `gww pull` | 🔄 Обновить исходный репозиторий (работает из worktree, если исходный репозиторий чист и на main/master) |
| `gww migrate <path>... [--dry-run] [--copy \| --inplace]` | 🚚 Мигрировать репозитории в новые локации |
| `gww init config` | ⚙️ Создать конфиг по умолчанию |
| `gww init shell <shell>` | 🐚 Установить автодополнение (bash/zsh/fish) |

**Примечание**: `gwc`, `gwa`, и `gwr` — это удобные алиасы shell для `gww clone`, `gww add`, и `gww remove` соответственно. Они предоставляют ту же функциональность с автоматическими запросами на навигацию. Установите их с помощью `gww init shell <shell>`.

**Часто используемые опции**:
- `--tag`, `-t`: Тег в формате `key=value` или просто `key` (можно указывать несколько раз).

## 🔄 Обновление

### Через uv

```bash
# Повторно выполните команду установки для обновления до последней версии
uv tool install "git+https://github.com/vadimvolk/git-worktree-wrapper.git"

# Или используйте команду обновления (если доступна)
uv tool update gww
```

### Через pipx

```bash
pipx upgrade gww
```

### Через pip

```bash
python -m pip install --upgrade gww
```

## 🗑️ Удаление

### Через uv

```bash
uv tool uninstall gww
```

### Через pipx

```bash
pipx uninstall gww
```

### Через pip

```bash
python -m pip uninstall gww
```

## 🛠️ Разработка

### 🧪 Запуск тестов

```bash
# Запустить все тесты
uv run pytest

# Запустить с coverage
uv run pytest --cov

# Запустить только unit-тесты
uv run pytest tests/unit/

# Запустить только integration-тесты
uv run pytest tests/integration/
```

### 🔍 Проверка типов

```bash
uv run mypy src/gww
```

## 📄 Лицензия

MIT

