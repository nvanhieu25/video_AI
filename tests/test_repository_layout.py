from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED_DIRECTORIES = ("bible", "episodes", "prompt_lib", "scripts", "skills", "templates")
BANNED_PHRASES = ("Dreamina", "handoff.md", "shots.csv", "Phương án A", "validate_shots.py")


def test_operator_docs_describe_only_the_autonomous_base():
    for name in RETIRED_DIRECTORIES:
        assert not (ROOT / name).exists(), name
    for relative in ("README.md", "CLAUDE.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for phrase in BANNED_PHRASES:
            assert phrase not in text, f"{relative} mentions {phrase}"
