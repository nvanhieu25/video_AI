from pathlib import Path

import pytest

from app.domain.recipes import RecipeValidationError, load_recipe
from tests.domain.test_models import make_plan


def test_reference_count_comes_from_the_recipe(tmp_path: Path):
    recipe_path = tmp_path / "five_refs.yaml"
    recipe_path.write_text(
        """
recipe_id: five_ref_v1
aspect_ratio: "9:16"
storyboard_min: 10
storyboard_max: 12
shots_per_storyboard_max: 2
reference_count: 5
reference_roles: [character, wardrobe, location, prop, product]
resolution: "720p"
fallback: reference_image_motion
""".strip(),
        encoding="utf-8",
    )
    recipe = load_recipe(recipe_path)
    assert recipe.reference_count == 5
    make_plan(storyboards=10, references=5).validate_for(recipe)
    with pytest.raises(RecipeValidationError):
        make_plan(storyboards=10, references=9).validate_for(recipe)
