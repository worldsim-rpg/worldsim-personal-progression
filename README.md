# worldsim-personal-progression

Агент развития игрока. Отдельный от world-builder'а, потому что
**мир и персонаж — разные зоны ответственности**. Мир не должен
чинить/менять игрока, игрок не должен править мир.

Часть игры **worldsim**.

## Что делает

На каждом ходу (после `world-builder.run_turn_update`) получает:
- intent игрока,
- произошедшее в мире (`TurnPatch`/`narrative_summary`),
- текущее `player_progression`.

Возвращает патчи **только на `player_progression`**:
- счётчики использования навыков (`skill_counters`),
- репутация во фракциях,
- новые факты в `known_facts` (уже применяет оркестратор напрямую,
  здесь — только относящееся к мастерству/биографии),
- инвентарь (добавить/убрать предметы — но только то, что
  подтверждено миром, напр. "получил ключ от NPC"),
- флаги (`flags`),
- состояние (`condition`) — если мир нанёс урон.

## Важно

- **Не меняет атрибуты напрямую.** Рост атрибутов — событие
  пороговое: копим счётчик использования в `skill_counters`, когда
  он достигает порога — поднимаем соответствующий атрибут на 0.05.
  Порог — в `prompts/progression.md`.
- **Не пишет в канон мира.** Если что-то должно произойти в мире —
  это работа world-builder.

## API

```python
from worldsim_personal_progression import run

patch = run(
    {
        "intent": {...},
        "world_change_summary": "...",      # narrative_summary от world-builder
        "turn_patch": {...},                # что мир только что применил
        "player_progression_before": {...},
    },
    client=client,
    model="claude-haiku-4-5-20251001",
)
# patch: TurnPatch (только с world_changes на entity_type=player)
```

## Структура

- `prompts/progression.md` — правила роста, порогов, soft-ограничений.
- `src/worldsim_personal_progression/agent.py` — клей.

См. [CLAUDE.md](CLAUDE.md).
