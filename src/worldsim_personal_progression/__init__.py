from worldsim_schemas import AgentManifest, AgentPhase

from .agent import run

MANIFEST = AgentManifest(
    name="personal-progression",
    package="worldsim_personal_progression",
    entrypoint="run",
    phase=AgentPhase.PROGRESSION_UPDATE,
    model_tier="default",
    description="Апдейт прогрессии игрока по результату хода.",
)

__all__ = ["run", "MANIFEST"]
