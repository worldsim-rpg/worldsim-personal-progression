def test_import():
    from worldsim_personal_progression import run  # noqa: F401


def test_prompt_exists():
    from pathlib import Path

    assert (Path(__file__).parent.parent / "prompts" / "progression.md").exists()
