<!-- Language switcher -->
[English](README.md) | **Русский**

# GWW — Git Worktree Wrapper

CLI-инструмент, который оборачивает функциональность `git worktree`, добавляя настраиваемые шаблоны путей, маршрутизацию на основе предикатов и действия, специфичные для проекта.

## Возможности

- **Настраиваемые шаблоны путей**: Динамическая генерация путей с использованием шаблонов и функций вроде `path(n)`, `branch()`, `norm_branch()`, `tag()`
- **Маршрутизация на основе предикатов**: Размещение репозиториев в разные локации по предикатам URI (host, path, protocol, tags)
- **Поддержка тегов**: Передавайте пользовательские теги через опцию `--tag` для условной маршрутизации и организации путей
- **Действия проекта**: Выполнение пользовательских действий (копирование файлов, команды) после клонирования или создания worktree
- **Автодополнение shell**: Поддержка completion для Bash, Zsh и Fish

## Требования

- Python 3.11+
- Git
- Unix-подобная система (Linux, macOS)

## Установка

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

## Быстрый старт

### 1. Инициализировать конфигурацию

```bash
gww init config
```

Это создаст конфигурационный файл по умолчанию в `~/.config/gww/config.yml` (Linux) или `~/Library/Application Support/gww/config.yml` (macOS).

### 2. Клонировать репозиторий

```bash
gww clone https://github.com/user/repo.git
# Output: ~/Developer/sources/github/user/repo
```

### 3. Добавить worktree

```bash
cd ~/Developer/sources/github/user/repo
gww add feature-branch
# Output: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 4. Удалить worktree

```bash
gww remove feature-branch
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 5. Обновить исходный репозиторий

```bash
gww pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo
```

## Конфигурация

Пример `config.yml`:

```yaml
default_sources: ~/Developer/sources/default/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/default/path(-2)/path(-1)/norm_branch()

sources:
  github:
    predicate: '"github" in host()'
    sources: ~/Developer/sources/github/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/norm_branch()

  gitlab:
    predicate: '"gitlab" in host()'
    sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/gitlab/path(-3)/path(-2)/path(-1)/norm_branch()

actions:
  - predicate: file_exists("local.properties")
    source_actions:
      - abs_copy: ["~/sources/default-local.properties", "local.properties"]
    worktree_actions:
      - rel_copy: ["local.properties"]
```

### Функции шаблонов

#### Функции URI (доступны в шаблонах, URI-предикатах и предикатах проектов)

| Function | Description | Example |
|----------|-------------|---------|
| `host()` | Получить hostname из URI | `host()` → `"github.com"` |
| `port()` | Получить порт из URI (пустая строка, если не указан) | `port()` → `""` или `"22"` |
| `protocol()` | Получить протокол/схему URI | `protocol()` → `"https"` или `"ssh"` |
| `uri()` | Получить URI целиком | `uri()` → `"https://github.com/user/repo.git"` |
| `path(n)` | Получить сегмент пути URI по индексу (0-based, отрицательные — с конца) | `path(-1)` → `"repo"`, `path(0)` → `"user"` |

#### Функции веток (доступны в шаблонах)

| Function | Description | Example |
|----------|-------------|---------|
| `branch()` | Получить имя текущей ветки | `branch()` → `"feature/new/ui"` |
| `norm_branch(replacement)` | Имя ветки с заменой `/` (по умолчанию: `"-"`) | `norm_branch()` → `"feature-new-ui"`, `norm_branch("_")` → `"feature_new_ui"` |

#### Функции тегов (доступны в шаблонах, URI-предикатах и предикатах проектов)

| Function | Description | Example |
|----------|-------------|---------|
| `tag(name)` | Получить значение тега по имени (пустая строка, если не задан) | `tag("env")` → `"prod"` |
| `tag_exist(name)` | Проверить, существует ли тег (возвращает boolean) | `tag_exist("env")` → `True` |

#### Функции проекта (доступны только в предикатах проектов)

| Function | Description | Example |
|----------|-------------|---------|
| `source_path()` | Получить абсолютный путь к исходному репозиторию или корню worktree | `source_path()` → `"/path/to/repo"` |
| `dest_path()` | Получить абсолютный путь к назначению (цель clone или worktree) | `dest_path()` → `"/path/to/worktree"` |
| `file_exists(path)` | Проверить наличие файла относительно исходного репозитория | `file_exists("local.properties")` → `True` |
| `dir_exists(path)` | Проверить наличие директории относительно исходного репозитория | `dir_exists("config")` → `True` |
| `path_exists(path)` | Проверить наличие пути (файл или директория) относительно исходного репозитория | `path_exists("local.properties")` → `True` |

**Пример использования тегов**:

```yaml
sources:
  production:
    predicate: 'tag_exist("env") and tag("env") == "prod"'
    sources: ~/Developer/sources/prod/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/prod/path(-2)/path(-1)/norm_branch()
```

```bash
# Клонировать с тегами
gww clone https://github.com/user/repo.git --tag env=prod --tag project=backend

# Добавить worktree с тегами
gww add feature-branch --tag env=dev --tag team=frontend
```

## Команды

| Command | Description |
|---------|-------------|
| `gww clone <uri> [--tag key=value]...` | Клонировать репозиторий в настроенную локацию (теги доступны в шаблонах/предикатах) |
| `gww add <branch> [-c] [--tag key=value]...` | Добавить worktree для ветки (опционально создать ветку, теги доступны в шаблонах/предикатах) |
| `gww remove <branch\|path> [-f]` | Удалить worktree |
| `gww pull` | Обновить исходный репозиторий |
| `gww migrate <path> [--dry-run] [--move]` | Мигрировать репозитории в новые локации |
| `gww init config` | Создать конфиг по умолчанию |
| `gww init shell <shell>` | Установить автодополнение (bash/zsh/fish) |

**Часто используемые опции**:

- `--tag`, `-t`: Тег в формате `key=value` или просто `key` (можно указывать несколько раз)

## Разработка

### Запуск тестов

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

### Проверка типов

```bash
uv run mypy src/gww
```

## Лицензия

MIT

