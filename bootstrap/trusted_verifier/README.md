# Symphony Next: verifier для PR #11

Пакет подготовлен для отдельной установки владельцем на **1c-db, Ubuntu 22.04, CPython 3.10 x86_64, systemd 249**. Он проверяет только commit `78d60bd77a5c9667e1241ca64f3429a3123d86df`. Это bootstrap защищённых checks; общая автоматическая очередь CI/SN-030 не реализована.

**Не запускать WORK-01, BOOT-P01, прежние prepare/preflight/recovery helpers.** Данный пакет использует новые пути и unit names, не читает старые маркеры и не запускает модель.

## Состав и границы
- `verifier.py`: фиксированные owner-команды install/configure/status и controller verification.
- `controller.service`: root-owned controller, без restart/timer/webhook; 20 минут максимум.
- `worker.py`: transient DynamicUser service, отдельный RootDirectory, readonly исходники/venv, PrivateNetwork/PrivateDevices/PrivateIPC, без capabilities, 2 CPU / 2 GiB / 128 PIDs / 600 секунд. Временные файлы — отдельный tmpfs `/worktmp` до 512 MiB; `/tmp` и `/var/tmp` недоступны. Перед тестами worker проверяет эффективные mounts и права.
- `github_api.py`: App JWT, токен только для repo ID 1381693716; curl с TLS/deadline/output limits.
- `target.json`: exact HEAD/tree/base/parent, SHA-256 девяти тестовых файлов и 126 test IDs.
- `requirements.lock`: все шесть зависимостей, только wheels с проверкой SHA-256.
- `package-manifest.json`: полный список исполняемых файлов и SHA-256.

Установка пишет только `/opt/symphony-next-verifier`, `/var/lib/symphony-next-verifier` и `/etc/systemd/system/symphony-next-verifier-controller.service`; выполняет daemon-reload, **не запускает сервис**. Systemd создаст отдельный transient test unit при явном старте controller.

Controller выполняет проверку и публикацию как доверенный код владельца; исходники PR запускаются только в DynamicUser sandbox без ключа/App-токена и доступа к controller state. Root-права не передаются writer/модели. Первичная установка владельцем — отдельная операция по конкретному проверенному пакету, а не replay ранее отклонённого установщика.

## 1. Получить точные байты
Используйте архив exact commit подготовленного PR, ссылку/хеш которого сопровождает owner-handoff. Скачайте архив через свой GitHub-сеанс, передайте на сервер, распакуйте в новый каталог. Не выполняйте файлы из изменяемой ветки без сверки exact commit/архива.

Для команд ниже рабочий каталог — `bootstrap/trusted_verifier` распакованного кандидата. Сначала проверьте сопровождающие commit/hash и независимое review. Приведённые здесь команды ещё не выполнялись на сервере.

## 2. Подготовить зависимости и установить пакет
Если prerequisite отсутствуют, владелец устанавливает стандартные пакеты Ubuntu:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends python3-venv python3-pip git curl openssl
```

Скачать только закреплённые wheels в новый пустой каталог **под обычной учётной записью**:

```bash
mkdir wheelhouse
python3 -m pip --isolated download --only-binary=:all: --require-hashes --no-deps \
  --index-url https://pypi.org/simple --dest wheelhouse -r requirements.lock
```

Этот lock предназначен для Python 3.10 / Linux x86_64. Другой ABI/platform приведёт к остановке. PyPI/files.pythonhosted.org должны быть доступны серверу; при сетевом отказе сохранить вывод, не менять index/хеши наугад. Никакие Python-пакеты системного окружения не обновляются.

Перед root-исполнением скопируйте проверенный пакет в **новый root-private staging каталог** с владельцем root. Полученные шесть wheels должны находиться рядом в `wheelhouse`. После сверки хешей запустите из staging:

```bash
sudo /usr/bin/python3 -I -B verifier.py install --wheelhouse wheelhouse
```

Ожидается `INSTALLED_NO_TEST_RUN`. Если путь/installation marker уже существует или возникает STOP — сохраняйте его; installer не удаляет и не перезаписывает частичную установку. До исправления конкретной причины следующий этап не выполнять.

## 3. Создать GitHub App
В аккаунте **pupkinson**: Settings → Developer settings → GitHub Apps → New GitHub App.
- Название: уникальное, например **Symphony Next Verifier**.
- Homepage URL: `https://github.com/pupkinson/SymphonyNext`.
- Webhook: **Active выключен**; callback/публичный endpoint этому bootstrap не нужен.
- Repository permissions: **Contents: Read-only**, **Pull requests: Read-only**, **Checks: Read and write**. Metadata read назначается GitHub автоматически. Остальные права — No access.
- Where can this GitHub App be installed: **Only on this account**.
- Создать App, записать **App ID**, сгенерировать private key.
- Install App → аккаунт pupkinson → **Only select repositories → SymphonyNext**.
- Записать **Installation ID** из URL страницы конкретной установки. Не путать с App ID.

Private key передайте по SFTP в отдельный root-private каталог, например `/root/snv-secrets/app.pem`; файл root:root mode 600, каталог mode 700. Не вставляйте ключ в чат, Git, issue, shell history или env-файл репозитория.

## 4. Привязать App
В следующей команде заменяются только числовые ID из GitHub и путь к собственному ключу:

```bash
sudo /usr/bin/python3 -I -B /opt/symphony-next-verifier/verifier.py configure \
  --app-id APP_ID --installation-id INSTALLATION_ID \
  --key-file /root/snv-secrets/app.pem
```

Ожидается `CONFIGURED_NO_TEST_RUN`. Configure не публикует check. Сетевое подтверждение identity/permissions выполняется controller перед проверкой. Ключ копируется в `/var/lib/symphony-next-verifier/private/app.pem`, root-only.

## 5. Выполнить проверку
Это запускает **только новый verifier**, без Symphony/model turn:

```bash
sudo systemctl start symphony-next-verifier-controller.service
sudo journalctl -u symphony-next-verifier-controller.service --no-pager -n 80
sudo /usr/bin/python3 -I -B /opt/symphony-next-verifier/verifier.py status
```

Проверка длится до 10 минут, controller ограничен 20 минутами. Если result ещё не появился, выполните только `status`/чтение журнала позже, **не повторный start**.

Готовый результат: `CHECK_PUBLISHED_EXACT_HEAD` для полного SHA `78d60bd...`. Журнал/JSON с STOP означает, что gate не закрыт. Нам нужны безопасный итог status и ссылка на check; ключи/токены не присылать.

После любого сбоя остаются `intent.json`, логи, unit-state и result. Наличие attempt не разрешает повтор тестов. Если есть `publication-intent.json`, но нет подтверждённого check, возможен неизвестный результат POST: сначала читать GitHub, не повторять publication. Встроенной команды сброса/force/retry нет.

## 6. Защитить required check
После первого успешного check в настройках защиты `main` потребуйте **symphony-next/verified-tests**, ожидаемый источник — созданный GitHub App. Примените правила к администраторам/уберите bypass, если это допускает действующая политика репозитория. Не выбирать Any source.

Если GitHub-тариф/настройки private repository не позволяют защиту, зафиксировать BLOCKED; наличие зелёного check само по себе не подтверждает защищённость. Тариф в этой подготовке не проверялся.

Пакет не меняет branch protection, не делает merge/deploy и не объявляет серверную функциональную приёмку завершённой.

## Что реально проверено и что ещё нет
Локальные 27 unit/regression tests проверяют acceptance и ошибки, реальное исполнение временных unittest fixtures, JWT подпись через OpenSSL, отказы повторного запуска/POST, фактические права каталогов при umask 077 и параметры sandbox. Проверка systemd unit статическая. **Native DynamicUser/RootDirectory, установка wheels, живой GitHub App, защита ветки и полные 126 тестов на сервере ещё NOT_RUN.** Эти результаты нельзя выводить из mocks.

Команда тестов пакета из корня репозитория:
```bash
PYTHONPATH=bootstrap/trusted_verifier python3 -B -m unittest discover -s bootstrap/trusted_verifier/tests -v
```

Первый dependency/full-suite прогон может обнаружить дополнительный дефект; 126 PASS заранее не обещаются. Полный source tree и окружение до/после сохраняются в новом attempt. Исходный PR #11 не изменён.

## Dependency provenance
Хеши взяты из разделов Release files официальных PyPI релизов:
- https://pypi.org/project/jsonschema/4.25.1/
- https://pypi.org/project/attrs/25.3.0/
- https://pypi.org/project/jsonschema-specifications/2025.9.1/
- https://pypi.org/project/referencing/0.36.2/
- https://pypi.org/project/rpds-py/0.27.1/
- https://pypi.org/project/typing-extensions/4.15.0/

Это фиксация происхождения/байтов, не заявление об отсутствии всех уязвимостей. Полный advisory audit и frozen install в целевом ABI ещё не выполнены.
