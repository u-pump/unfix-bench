# BENCH-20: bug miner for unfix-bench (plan, nothing implemented)

Status: **plan for the owner's review.** Nothing in this document has been built or run. Every number is one of three kinds, always marked: **измерено** (read from GitHub/OSV on 2026-11-14, by reading, no builds), **оценка** (my estimate), **не проверено**.

## 0. Что я нашёл, пока читал источники (важное для решения)

1. **Верификатор сейчас умеет только CMake.** `scripts/verify_cases.py` пишет `cplus.yaml` с `build_system: cmake`, защищёнными путями `test/** tests/** .github/**`, а `reference_test_name` проходит проверку только вида `Suite.Name` (Google Test). Zephyr (west/twister, ztest), NuttX (make, ostest), littlefs (свой Python-раннер) и Unity-тесты mbedTLS (`.data`-файлы) этому формату не соответствуют. Что из этого `cplus` умеет на самом деле, я знать не могу (исходники приватные). **Это вопрос №1 к владельцу**: от ответа зависит порядок источников.
2. **lwIP и littlefs не проекты OSS-Fuzz** (измерено: в `google/oss-fuzz/projects/` нет каталогов `lwip` и `littlefs`; `mbedtls` есть). Запрос OSV `ecosystem=OSS-Fuzz, package=mbedtls` вернул **1** запись (2022), по `lwip` и `littlefs` — 0. Диапазон `introduced/fixed` в OSV — результат бисекта OSS-Fuzz, а не обязательно коммит с фиксом: для OSV-2022-1223 «fixed» указывает на коммит «CID update to RFC 9146». Воспроизводящий вход лежит в трекере и требует входа. Вывод: OSS-Fuzz как *канал поиска* слабый; рабочий путь для fuzz-находок — обычные fix-коммиты с регрессионным тестом в самом репозитории (mbedTLS, lwIP, littlefs).
3. **Zephyr даёт много кандидатов.** Измерено: 475 смерженных PR с меткой `bug` после 2026-06-01. Из выборки в 30 PR с «fix» в заголовке 5 имели одновременно тест и исходник в диффе.
4. **Бэкпорты дублируют кейсы** (mbedTLS #10984 и #10985 — одна правка для веток 3.6 и 4.1). Нужна дедупликация.

## 1. Источники: поиск, запуск одного теста, риски

Общий механизм поиска: GitHub REST `search/issues` + `pulls/N/files` (дешёвый фильтр по списку файлов без клонирования), затем клон на `base` (родитель первого коммита PR) и `fix`.

| Источник | Поиск | Запуск одного теста | Примеры (прочитаны, без сборки) | Главные риски |
|---|---|---|---|---|
| **Zephyr** (Apache-2.0) | PR `is:merged label:bug`, в файлах есть `tests/` и исходник вне тестов | `west build -b native_sim tests/<path>` и запуск `build/zephyr/zephyr.exe`; фильтр ztest `-test=suite::name` (не проверено) | [#122423](https://github.com/zephyrproject-rtos/zephyr/pull/122423) stream_flash, тест `tests/subsys/storage/stream/stream_flash` (native_sim в `tests.yaml`), 2026-11-09, merge `574d9e437269332b421388f341b68b9c5ed48ac6`; [#122400](https://github.com/zephyrproject-rtos/zephyr/pull/122400) DNS QNAME, `tests/net/lib/dns_packet`, 2026-10-20, merge `dc4a55f1fdd4bc30cef844329a4471c5b40664b9` (в теле «Fixes #1» — issue нет, ISSUE.md из текста PR, как в fmt-кейсах) | `west update` тянет модули из сети; снимок для агента должен содержать их и собираться offline; размер снимка и место на раннере **не проверено**; SDK/32-бит; часто нет issue, только PR |
| **NuttX** (Apache-2.0) | `apache/nuttx` и `apache/nuttx-apps`, PR «fix» | `sim:ostest` / отдельные тест-приложения из `nuttx-apps`, make | [nuttx-apps#3998](https://github.com/apache/nuttx-apps/pull/3998) FAT FSINFO + тест `testing/fs/fatgap`, 2026-11-11, merge `304f5fd353e85b7789963bce11fef4229672ead9` | тесты живут в другом репозитории (два закреплённых коммита); новый тест — целое приложение на 700+ строк, плохо выбирается как эталон; в выборке из 40 PR ядра пар «тест + исходник» не нашлось (измерено: 0 из 40) |
| **FreeRTOS** (MIT) | `FreeRTOS-Plus-TCP` (unit-тесты Unity/CMock, CMake/ctest), `FreeRTOS-Kernel` (POSIX-порт) | `cmake` + `ctest -R <тест>` в `test/unit-test/<модуль>` — формат ближе всего к текущему | [Plus-TCP#1357](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1357) IPv6 bounds, тест в `test/unit-test/FreeRTOS_Sockets_IPv6`, 2026-08-06, merge `4e95d077203b86b103315fa90ad7889077467697` | у Kernel в выборке пар «тест + исходник» не нашлось (измерено: 0 из первых 30 «fix»), его тесты в отдельном репозитории (не проверено); Unity-тест не `Suite.Name` |
| **mbedTLS** как fuzz-канал (Apache-2.0 OR GPL-2.0-or-later; GitHub показывает NOASSERTION, SPDX записывать вручную) | OSV `api.osv.dev/v1/query` — мало (1 запись); основной путь: PR со словом fuzz/oss-fuzz и тестом в `tests/suites/*.data` | `cmake` + `ctest -R test_suite_<name>` | [mbedtls#10985](https://github.com/Mbed-TLS/mbedtls/pull/10985) x509 пустой AuthorityKeyIdentifier (тест — строка в `test_suite_x509parse.data`), 2026-10-21, merge `5e889b385f67e3d402741094713714b9c6ea1bc0` | тест — запись в `.data`, а не именованный тест; бэкпорты; двойная лицензия |
| **lwIP** (BSD-3-Clause) | fix-коммиты с изменением `test/unit` | unit-тесты (check), способ запуска не проверен | не искал (последний коммит 2026-11-08) | не OSS-Fuzz; формат unit-тестов не проверен |
| **littlefs** (BSD-3-Clause) | PR «fix» с тестом в `tests/` | `make test` — собственный раннер, не CMake | [littlefs#1099](https://github.com/littlefs-project/littlefs/pull/1099) (2025-05-13, до июня 2026) | не CMake; последний коммит 2026-03-24 — мало свежих фиксов |
| **Betaflight** (запасной) | не исследовал | — | — | **не проверено** |

## 2. Оценка выхода

Измерено: из 30 «bug/fix» PR Zephyr 5 прошли дешёвый фильтр «тест + исходник» (≈17%). Дальше всё **оценка**: 3/3 падение на базе, 3/3 прохождение на фиксе, сборка ≤ 30 мин, лицензия и issue-текст отсекают ещё 60–80%. Тогда один кейс = 15–30 просмотренных PR (**оценка**), на 90 новых кейсов ≈ 1500–2700 просмотренных PR и ≈ 300–500 полных базовых прогонов (**оценка**). Вилка широкая; пилот (раздел 4) её сузит, и я пересчитаю.

Распределение 90 новых кейсов (плюс 10 существующих; fmt = 7 из 100):

| Источник | Новых кейсов | Доля из 100 |
|---|---:|---:|
| Zephyr | 28 | 28% |
| FreeRTOS (Plus-TCP, Kernel) | 15 | 15% |
| mbedTLS | 15 | 15% |
| NuttX (+apps) | 12 | 12% |
| lwIP | 8 | 8% |
| littlefs | 8 | 8% |
| Betaflight | 4 | 4% |

Правило: не более 30% кейсов из одного проекта (Zephyr — один проект, потолок 30). Майнер проверяет долю при выборке и при превышении пишет отказ `project_cap`. Если часть источников окажется невозможной (вопрос №1), доли пересчитываются, а не добираются другим проектом сверх потолка.

**Дата и контаминация.** Записываем `fix_date` и `post_cutoff` (фикс позже 2026-06-30, граница в конфиге). Предлагаю держать **не менее 50% новых кейсов с фиксом после июня 2026** и показывать результаты в README отдельно по двум группам. Дата отсечения обучения проверяемых моделей (claude-opus-5-5, gpt-6-sol) мне неизвестна (**не проверено**), поэтому «после июня» — осторожный ориентир, а не гарантия, что решения нет в обучении. Для Zephyr свежих кейсов достаточно (475 PR с `bug` после июня, измерено), у littlefs их почти нет.

## 3. Схема каталогов, журнал отказов, scripts, workflow

```
candidates/                      # не cases/; публикация только владельцем
  <id>/
    case.yaml                    # схема как у cases/: id, repo, base, upstream_fix, bug_test, reference_selection,
                                 # issue_url, fix_url, license, category, build, test, baseline_reproduction
    meta.yaml                    # source, spdx, fix_date, post_cutoff, upstream_pr, dedupe_key, mined_run_url, miner_version
    ISSUE.md                     # черновик; удаляемые подсказки перечислены в ISSUE.removals.md
    baseline.log                 # 3 прогона на base (ожидается FAIL) и 3 на fix (PASS), урезанные
  _rejected/<source>.jsonl       # журнал отказов, только дописывается
  _runs/<run-id>/summary.json    # сколько просмотрено, сколько отсеяно по причинам
```

Запись журнала (одна JSON-строка): `{"source","project","ref","fix_commit","stage","reason_code","detail","fix_date","miner_run"}`. `stage`: `discover | static | build | baseline | fix_run | license | issue | cap`. Коды: `no_test_in_diff`, `test_only_fix`, `source_only_fix_no_test`, `duplicate_backport`, `base_not_failing_3of3`, `fix_not_passing_3of3`, `build_failed`, `over_30_min`, `needs_hardware`, `needs_network_dependency`, `test_not_selectable` (как fmt #4498), `license_unclear`, `no_issue_text`, `project_cap`. В публичные результаты это не попадает как NOT_VERIFIABLE: это «не кандидат». Существующий `docs/candidates.md` остаётся ручной публичной таблицей владельца; из журнала в неё попадает только то, что владелец решит показать.

`scripts/mine/` (новое; существующие скрипты агента не трогаем):
- `discover.py` — адаптеры источников (GitHub PR, OSV); вывод — список кандидатов JSON.
- `filters.py` — статические фильтры (тест + исходник в диффе, не бэкпорт, лицензия из allowlist SPDX, дата).
- `baseline.py` — клон, сборка, 3 прогона на base и 3 на fix, лимит времени.
- `draft.py` — запись `candidates/<id>/`; `rejects.py` — журнал; `cap.py` — доля проекта.
- Тесты: записанные JSON-ответы API (без сети), временные git-репозитории для `baseline.py`, проверка схемы `case.yaml` против существующих `cases/*/case.yaml`.

`.github/workflows/mine-candidates.yml`: только `workflow_dispatch` (входы `source`, `query` или список кандидатов, `max_candidates`); джобы `discover` (без сборок, `contents: read`) → `baseline` (матрица, `max-parallel`, `timeout-minutes: 30` на кандидата, `actions/cache` для ccache/west) → `collect` (артефакт; перед загрузкой тот же скан секретов, что в `run-claude-code.yml`) → `record` (открывает PR с `candidates/`; единственная джоба с правом записи; сборка чужого кода идёт без секретов и без записи). Ключей агентов и доступа к `bench-in-*` нет. Тяжёлые сборки только в Actions.

## 4. Пилот: 5 Zephyr + 5 из fuzz-источников

Из-за п. 0.2 предлагаю заменить «5 из OSS-Fuzz» на **5 кандидатов fuzz-происхождения из mbedTLS** (PR со словом fuzz/oss-fuzz и регрессионным тестом в репозитории). Если их не найдётся, пилот честно фиксирует, что канал OSS-Fuzz для этих проектов кандидатов не даёт. Нужно решение владельца (вопрос №2).

Успех пилота (пороги — мои предложения):
1. Пайплайн дошёл от `discover` до PR `candidates/` без ручных правок.
2. Каждый отказ записан с кодом; записей без причины нет.
3. Хотя бы 3 из 10 прошли весь фильтр; время сборки и размер по каждому измерены и записаны (заменят оценки выше).
4. Повтор того же запуска даёт те же результаты baseline.
5. Выяснено, способен ли `cplus` судить кандидат хотя бы одного нового формата (Zephyr или Unity); если нет, пилот фиксирует границу и план пересматривается.

Пилот не запускает агентов.

## 5. Изменения в docs/protocol.md и docs/DECISIONS.md (после «да»)

`docs/protocol.md`, новый раздел «Candidate selection»: обязательные критерии отбора (раздел 3), дедупликация бэкпортов, лимит 30% на проект, поля `fix_date` и `post_cutoff`, раздельная публикация групп, правило заморозки `bug_test` до запуска агента без изменений, журнал отказов вместо NOT_VERIFIABLE. `docs/DECISIONS.md`, запись BENCH-20: почему `candidates/` отдельно от `cases/`, почему отбор в Actions, лимит на проект и его цифра, граница контаминации и оговорка к ней, отказ от Arduino, статус OSS-Fuzz как канала поиска.

## 6. Риски и что сознательно не делаем

Риски: поддержка форматов в `cplus` (п. 0.1); offline-сборка Zephyr/NuttX для агента и размер приватных снимков (**не проверено**); нестабильные тесты (отсеиваются условием 3/3); лицензия issue-текста и тестов (SPDX записывается, юридическую оценку делает владелец); чужой код в CI (изоляция джоб, см. раздел 3); минуты Actions и диск раннера (**не проверено**); смещение отбора к проектам с удобными тестами (фиксируем в «Limits» README).

Не делаем: не пишем эксплойтов и не берём непубличные воспроизведения OSS-Fuzz, не публикуем кейсы и не создаём `bench-in-*`, не переносим `candidates/` в `cases/`, не запускаем агентов, не берём Arduino, не меняем метод вердикта, не делаем выводов «какой агент лучше».

## 7. Разбивка на PR (малые, каждый с тестами)

1. Схема `candidates/` + валидатор `case.yaml`/`meta.yaml` (проверка против существующих `cases/`) + правки docs/protocol.md и DECISIONS.
2. `filters.py`, `rejects.py`, `cap.py` + тесты на фикстурах.
3. `discover.py` для GitHub (с дедупликацией бэкпортов) + записанные ответы API.
4. `baseline.py` для CMake-проектов + тесты на временных репозиториях + каркас `mine-candidates.yml` (только discover).
5. Джобы baseline/collect/record (скан артефактов, статические тесты политики по образцу `test_artifact_policy.py`).
6. Адаптер Zephyr (west/native_sim, кеш).
7. Адаптер mbedTLS/OSV.
8. Пилот (отдельное «да» владельца) и отчёт с реальными цифрами; затем FreeRTOS, NuttX, lwIP, littlefs — по одному PR.

## Вопросы к владельцу

1. Что `cplus` умеет кроме `build_system: cmake` и Google Test (`Suite.Name`): west/native_sim, ztest, Unity/ctest, make? От этого зависит, с чего начинать.
2. Пилот: заменить «5 OSS-Fuzz» на «5 fuzz-происхождения из mbedTLS» (п. 0.2)?
3. Порог доли «после июня 2026»: 50% подходит?
4. Входят ли 10 существующих кейсов в 100 (как в таблице выше)?
5. Можно ли включать модули west в приватный снимок Zephyr для offline-сборки агентом (размер не измерен)?
