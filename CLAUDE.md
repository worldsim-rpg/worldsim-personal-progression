# CLAUDE.md — worldsim-personal-progression

Правила для Claude Code в этом репо.

## Что это

Прогрессия игрока. Одна функция: `run(input, *, client, model) -> TurnPatch`.

## Границы

- Пишет **только** `player_progression.*`. Любой патч на
  `character`/`location`/`faction`/`arc`/`secret` — нарушение.
  Это зона `world-builder`.
- Поле `entity_type` в патчах = `"player"`.

## Инварианты

- `attributes.*` ∈ `[0, 1]`.
- `reputation[*]` ∈ `[-1, 1]`.
- `skill_counters[*]` — только растёт (не уменьшается).
- `known_facts` — только добавление.
- `condition` может меняться по событию (wounded/exhausted), но
  не произвольно.

## Где править поведение

- Пороги роста атрибутов, формулы репутации — `prompts/progression.md`.
- Типы навыков — уже в `worldsim_schemas.Attributes`, менять там.

## Тесты

`python -m pytest -q`.
