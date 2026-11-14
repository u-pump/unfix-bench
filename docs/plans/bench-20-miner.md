# BENCH-20: bug miner for unfix-bench (plan, nothing implemented)

Status: **plan for the owner's review, revision 2** (after the owner's answers in PR #28 and a read-only check of the verifier's code). Nothing here has been built or run. Numbers are marked: **измерено** (read from GitHub/OSV on 2026-11-14, by reading), **оценка**, **не проверено**, **не установлено** (the code does not answer it).

## 0. Что умеет верификатор сегодня (по коду `D:\c-plus`, только чтение)

| Возможность | Ответ | Где в коде |
|---|---|---|
| Система сборки CMake | да | `src/cplus/project_manifest.py:50` (`Literal["cmake","make"]`), автоопределение `project_setup.py:236-246` |
| Система сборки Make | да, но только как команда `make`; тест-команду автоопределение даёт лишь для CTest (`test_command = ""` без CTest) | `project_manifest.py:50`, `project_setup.py:248`, `:254` |
| Другие системы (west, ninja как отдельная система, Bazel…) | нет: поле манифеста принимает только `cmake`/`make`, лишние значения запрещены (`extra="forbid"`) | `project_manifest.py:47-50` |
| Раннер CTest | да (основной путь: `ctest --test-dir build -R <тест>`) | `bug_check/engine.py:170`, `:297`; `gates/regression.py:50-51` (JUnit из ctest) |
| Google Test | да: распознавание `TEST/TEST_F/TEST_P`, имя `Suite.Name`, изоляция через `GTEST_FILTER` | `bug_check/fix_tests.py:89-90`, `:179-186`; `verify.py:665-673`; `reference_overlay.py:29-32` |
| Catch2 | да: `TEST_CASE("…")` | `fix_tests.py:88`; `reference_overlay.py:30` |
| Unity | **частично**: имя `void test_*(void)` распознаётся (в том числе `( void )` с пробелами) и вывод Unity разбирается в проверке регрессий; **извлечение эталонного блока (reference overlay) для Unity не реализовано** (только gtest/Catch2) | `fix_tests.py:91`, `:96-97`; `gates/regression.py:95-96`; `reference_overlay.py:28-33`; тест на распознавание — `tests/test_bug_check.py:337`; тест на режим эталона с Unity **не найден** |
| CMock | отдельной поддержки нет; CMock-тесты — это Unity-исполняемые файлы через CTest | в `src/` нет упоминаний `cmock` (поиск по коду) |
| ztest / twister / west / native_sim | **нет**: в `src/` и `docs/` упоминаний нет | поиск по коду, 0 совпадений |
| check (libcheck) | нет, упоминаний нет | поиск по коду |
| Задание имени эталонного теста | `--reference-test-name` вместе с `--reference-test-from-fix`; имя обязано быть среди добавленных тестов фикса (`added_test_names`) | `cli.py:215-223`; `verify.py:616-624` |
| Выбрать один тест внутри CTest-цели | **только для Google Test** (`GTEST_FILTER=<Suite.Name> ctest …`, имя по регулярке `[A-Za-z_]\w*\.[A-Za-z_]\w*`). Для Unity/Catch2 фильтра внутри одного исполняемого файла в коде нет; доступна лишь гранулярность CTest-теста (`-R`). Как `cplus` поведёт себя при эталоне Unity-функции — **не установлено** | `verify.py:665-673`; `engine.py:297`; `cli.py:274` |
| Тест, добавленный как строка в файл данных (mbedTLS `tests/suites/*.data`) | **нет**: без `TEST`/`TEST_CASE`/`void test_*(void)`/`add_test` фикс получает ошибку «the fix adds no recognizable test to run on the base» | `bug_check/engine.py:290-291`; `fix_tests.py:81-125` |

**Что ограничивает `verify_cases.py` до cmake + `Suite.Name`: частично обвязка, частично сам `cplus`.**
- Обвязка: `verify_cases.py:399` жёстко пишет `build_system: cmake` (сам `cplus` принял бы и `make`), `:402` — защищённые пути `test/** tests/**…` (в `cplus` по умолчанию другие, `project_manifest.py:61`), `:408` — регулярка `Suite.Name` для `reference_test_name`, `:414` — команда `GTEST_FILTER=…`. Для Unity/Catch2-кейсов это бенч-слой нужно расширять отдельным PR.
- Сам `cplus`: изоляция одного теста внутри цели существует только для gtest-имён (`verify.py:665-667`), а блок эталона извлекается только для gtest/Catch2 (`reference_overlay.py:28-33`). Это ограничения продукта.

## 1. Порядок источников = что верификатор умеет сегодня

Решение владельца: порядок определяется возможностями верификатора. Итог чтения кода:

| Приоритет | Источник | Стыковка с `cplus` сегодня |
|---|---|---|
| 1 | **FreeRTOS-Plus-TCP** (MIT, CMake + ctest, Unity/CMock) | распознаётся имя Unity-функции и вывод; эталонный блок Unity не извлекается (нужен лишь при пересечении патча агента с тестом, `verify.py:1082`); граница — один ctest на модуль, не на функцию |
| 2 | **Ядровые библиотеки FreeRTOS: coreMQTT, coreHTTP, coreJSON, corePKCS11** (MIT, тот же стек Unity/CMock/CMake) | то же, что выше; прочитанный пример coreMQTT#383 добавляет `void test_…( void )` |
| 3 | **mbedTLS** | **не подходит сегодня**: тест чаще строка `.data` (пример #10985), «распознаваемого теста» нет (`engine.py:291`) |
| 4 | Zephyr, NuttX, littlefs | нужна доработка продукта, раздел 3 |

mbedTLS шаг 1 **не подтвердил**, поэтому заменён в пилоте (раздел 4). Для mbedTLS остаётся отдельная задача продукта (распознавание `.data`/`.function`).

Общий механизм поиска: GitHub REST `search/issues` + `pulls/N/files` (фильтр по списку файлов без клонирования), затем клон на `base` и `fix`.

Прочитанные примеры (без сборок):
- FreeRTOS-Plus-TCP [#1357](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1357): IPv6 bounds, 2026-08-06, merge `4e95d077203b86b103315fa90ad7889077467697`; добавляет `void test_FreeRTOS_inet_ntop6_MaxAddressExactSize( void )` (имя совпадает с регуляркой Unity). Сборка юнит-тестов обращается к git submodule (`test/unit-test/CMakeLists.txt:79`, **измерено** на коммите фикса): нужна сеть при сборке (**не проверено**, допустима ли в песочнице).
- coreMQTT [#383](https://github.com/FreeRTOS/coreMQTT/pull/383): bounds в подписке, 2026-08-06, merge `a664bbb07938a8dea6d25cc7d20f581d5fba64c6`; тест `test_MQTTV5_Subscribe_WildcardCheck_HonorsTopicFilterLength`; рядом CBMC-доказательство (в пакет фикса не нужно: файлы `test/cbmc/**`, не запускаются). Также [#382](https://github.com/FreeRTOS/coreMQTT/pull/382) (2026-08-13), coreHTTP [#194](https://github.com/FreeRTOS/coreHTTP/pull/194) (2026-01-15), coreJSON [#179](https://github.com/FreeRTOS/coreJSON/pull/179) (2025-12-05). У всех в диффе есть и тест, и исходник (**измерено** по списку файлов); что тест — именно `void test_*(void)` и что он падает на базе 3/3, **не проверено**.
- Лицензии (**измерено**, GitHub): FreeRTOS-Plus-TCP, coreMQTT, coreHTTP, coreJSON, corePKCS11 — MIT.

Правило **fuzz-происхождения**: метка ставится только если коммит или issue прямо ссылается на фаззер/OSS-Fuzz. Иначе поле пусто. lwIP и littlefs проектами OSS-Fuzz не называем.

## 2. Состав 100 кейсов и оценка выхода

100 = 10 существующих + 90 новых. **Потолок 30% на проект считается от 100** (то есть ≤ 30 кейсов на проект, вместе с уже имеющимися: fmt уже даёт 7 из 100).

Распределение 90 новых по приоритету (**предложение**, зависит от того, какие форматы `cplus` освоит):

| Группа | Новых кейсов | Условие |
|---|---:|---|
| FreeRTOS-Plus-TCP | 25 | сегодня, с ограничениями раздела 0 |
| coreMQTT + coreHTTP + coreJSON + corePKCS11 | 15 (≤ 30 из любого одного) | сегодня |
| mbedTLS | 15 | после доработки «.data/.function» (раздел 3) |
| Zephyr | 20 | после доработки ztest/native_sim |
| NuttX, littlefs, lwIP | 15 | после доработок или отказ, если доработок нет |

Если доработки продукта не будут сделаны, выбираем только строки «сегодня» и честно останавливаемся на меньшем числе (на ориентир около 40 новых кейсов, **оценка** по числу прочитанных кандидатов; не обещание). Пересчёт после пилота.

Выход (**оценка**, кроме двух измеренных чисел): у Zephyr из 30 «fix»-PR 5 прошли дешёвый фильтр «тест + исходник» (**измерено**, ≈17%); для FreeRTOS-библиотек измерен только наличие тест+исходник в диффе. Дальнейший отсев (3/3 на базе, 3/3 на фиксе, сборка ≤ 30 мин, лицензия, issue) — 60–80% (**оценка**), итого 15–30 просмотренных PR на кейс (**оценка**). После пилота заменяем замером.

**Даты.** Для каждого кейса записываем `fix_date`, `post_cutoff` (фикс после **2026-06-30**, граница в конфиге). Требование: **не менее 50% новых кейсов с фиксом после 2026-06-30**. В README результаты таких кейсов показываются **отдельной таблицей/строкой**. О датах обучения моделей ничего не утверждаем.

## 3. Нужна доработка продукта (отдельная задача в D:\c-plus после пилота; в этом PR не делается)

Все оценки трудозатрат — **оценка**, не обязательство.

| Что нужно в `cplus` | Для кого | Оценка |
|---|---|---|
| Эталонный блок для Unity-функции (`void test_*(void)`) в `reference_overlay` + тест на режим эталона | FreeRTOS-библиотеки, mbedTLS | малая: 2–4 дня |
| Фильтр одной Unity-функции внутри исполняемого файла (или правило «эталон = ctest-тест целиком») | FreeRTOS-библиотеки | малая: 2–4 дня; решение по семантике нужно от владельца |
| Распознавание тестов в mbedTLS (`.data`-строки и `.function`-макросы), имя = пара «набор + строка» | mbedTLS | средняя: 1–2 недели |
| Тест-команда для проектов на Make без CTest (`make test`/свой раннер), разбор имён | littlefs, часть NuttX | средняя: 1–2 недели |
| `west build -b native_sim` + запуск `zephyr.exe`, ztest (`ZTEST(suite, name)`), фильтр теста, образ с toolchain и модулями | Zephyr | большая: 3–5 недель; сначала проверка осуществимости |
| NuttX `sim:ostest`, два репозитория (nuttx + nuttx-apps) с закреплёнными коммитами | NuttX | большая: ≥ 4 недели; осуществимость **не проверена** |
| Разрешение сетевых загрузок при сборке (submodules, west) в песочнице верификатора: политика | FreeRTOS-Plus-TCP, Zephyr | **не установлено** (`network: on` по умолчанию, `project_manifest.py:55-56`; как это работает в образе верификатора, из кода не видно) |

Модули west в приватный снимок включать допустимо, только нужные для сборки и только если лицензии позволяют; размер измеряется **в пилоте**, не сейчас.

## 4. Пилот: 10 кандидатов

Состав: **5 FreeRTOS-Plus-TCP + 5 из ядровых библиотек FreeRTOS (coreMQTT, coreHTTP, coreJSON)** вместо 5 mbedTLS (mbedTLS не подтверждён шагом 1, см. раздел 0). Обоснование: тот же Unity/CMake/ctest-стек, MIT, есть фиксы после 2026-06-30 (coreMQTT#383, #382, Plus-TCP#1357). Недостаток: пилот проверяет один тест-стек; поэтому в пилот добавляется измерение размера снимка, времени сборки и необходимость сети (submodules).

Успех пилота (пороги — мои предложения):
1. Пайплайн дошёл от `discover` до PR `candidates/` без ручных правок.
2. Каждый отказ записан с кодом причины; записей без причины нет.
3. Хотя бы 3 из 10 прошли весь фильтр; время сборки, размер и потребность в сети измерены и записаны (заменят оценки).
4. Повтор запуска даёт те же результаты baseline.
5. Установлено на этих 10, судит ли `cplus` Unity-кандидат в режиме эталона: либо «да», либо точная причина отказа (вход для задачи раздела 3).
6. Измерен размер приватного снимка; если включены модули/submodules, указаны лицензии.

Пилот не запускает агентов и не публикует кейсы.

## 5. Схема каталогов, журнал отказов, scripts, workflow

```
candidates/                      # не cases/; публикация и перенос только владельцем
  <id>/
    case.yaml                    # схема как у cases/: id, repo, base, upstream_fix, bug_test, reference_selection,
                                 # issue_url, fix_url, license, category, build, test, baseline_reproduction
    meta.yaml                    # source, spdx, fix_date, post_cutoff, upstream_pr, fuzz_origin (пусто или ссылка),
                                 # dedupe_key, mined_run_url, miner_version
    ISSUE.md                     # черновик; удалённые подсказки перечислены в ISSUE.removals.md
    baseline.log                 # 3 прогона на base (FAIL) и 3 на fix (PASS), урезанные
  _rejected/<source>.jsonl       # журнал отказов, только дописывается
  _runs/<run-id>/summary.json    # сколько просмотрено, сколько отсеяно по причинам
```

Запись журнала (JSON-строка): `{"source","project","ref","fix_commit","stage","reason_code","detail","fix_date","miner_run"}`. `stage`: `discover | static | build | baseline | fix_run | license | issue | cap`. Коды: `no_test_in_diff`, `test_only_fix`, `duplicate_backport`, `base_not_failing_3of3`, `fix_not_passing_3of3`, `build_failed`, `over_30_min`, `needs_hardware`, `needs_network_dependency`, `test_not_selectable` (как fmt #4498), `unsupported_by_verifier` (формат из раздела 3), `license_unclear`, `no_issue_text`, `project_cap`. В публичных результатах это «не кандидат», не NOT_VERIFIABLE. Дедупликация бэкпортов — как в первой версии плана: один ключ на суть правки, бэкпорты в ветки считаются одним кейсом (пример: mbedTLS #10984 и #10985).

`scripts/mine/`: `discover.py` (адаптеры GitHub), `filters.py` (тест+исходник в диффе, не бэкпорт, SPDX из allowlist, дата), `baseline.py` (клон, сборка, 3+3 прогона, лимит времени), `draft.py`, `rejects.py`, `cap.py` (потолок 30% от 100). Тесты: записанные ответы API (без сети), временные git-репозитории, проверка схемы против `cases/*/case.yaml`.

`.github/workflows/mine-candidates.yml`: только `workflow_dispatch` (`source`, список или запрос, `max_candidates`); джобы `discover` (без сборок, `contents: read`) → `baseline` (матрица, `max-parallel`, `timeout-minutes: 30`, кеш) → `collect` (артефакт после скана секретов как в `run-claude-code.yml`) → `record` (PR с `candidates/`; единственная джоба с записью; чужой код собирается без секретов). Доступа к `bench-in-*` и ключам агентов нет. Тяжёлые сборки только в Actions.

## 6. Изменения в docs/protocol.md и docs/DECISIONS.md (после «да»)

`docs/protocol.md`, раздел «Candidate selection»: критерии отбора; дедупликация бэкпортов; потолок 30% от 100; поля `fix_date`, `post_cutoff` и отдельное представление результатов кейсов после 2026-06-30; правило `fuzz_origin` только по прямой ссылке; журнал отказов вместо NOT_VERIFIABLE; заморозка `bug_test` до запуска агента без изменений. `docs/DECISIONS.md`, запись BENCH-20: порядок источников по возможностям верификатора; `candidates/` отдельно от `cases/`; потолок; граница даты без утверждений о моделях; Zephyr/NuttX/littlefs ждут доработки продукта; модули west в снимок только нужные и по лицензии.

## 7. Риски и что не делаем

Риски: Unity в режиме эталона не проверен (раздел 0); сеть при сборке (submodules); размеры снимков и время сборки (**не проверено**); нестабильные тесты (условие 3/3); лицензии issue-текстов (SPDX записываем, оценку делает владелец); чужой код в CI (изоляция джоб); перекос к проектам с удобными тестами (отражаем в «Limits» README).

Не делаем: эксплойты, закрытые воспроизведения OSS-Fuzz, публикацию кейсов, `bench-in-*`, перенос `candidates/` в `cases/`, запуск агентов, Arduino, смену метода вердикта, выводы «какой агент лучше», доработку `cplus` в этом PR.

## 8. Разбивка на PR

1. Схема `candidates/` + валидатор + docs/protocol.md и DECISIONS.
2. `filters.py`, `rejects.py`, `cap.py` + тесты.
3. `discover.py` для GitHub + дедупликация бэкпортов + фикстуры.
4. `baseline.py` для CMake-проектов + тесты + каркас `mine-candidates.yml` (только discover).
5. Джобы baseline/collect/record + тесты политики артефактов.
6. Расширение бенч-обвязки `verify_cases.py` под Unity (после решения по семантике эталона; отдельно от продукта).
7. Пилот (после «да») и отчёт с реальными цифрами.
8. Дальше источники по одному PR, по мере готовности `cplus` (задачи раздела 3 живут в D:\c-plus).

## Вопросы к владельцу

1. Семантика эталона для Unity: достаточно «ctest-тест модуля целиком падает на базе, проходит с фиксом», с `bug_test` = имя добавленной функции (идентификатор), или нужен фильтр на функцию?
2. Сеть при сборке FreeRTOS (git submodule для Unity/CMock): допустима ли в песочнице верификатора, или сначала нужен предзагруженный снимок?
3. Подтверждаете замену mbedTLS в пилоте на ядровые библиотеки FreeRTOS?
