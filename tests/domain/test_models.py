from uuid import uuid4

import pytest

from app.domain.models import (
    AssetOrigin,
    AssetRef,
    EpisodePlan,
    JobStatus,
    Shot,
    Storyboard,
    TaskStatus,
    Timeline,
)
from app.domain.recipes import RecipeValidationError, load_recipe

RECIPE = "app/recipes/drama_vertical_120s_v1.yaml"


def make_plan(
    *,
    storyboards: int,
    references: int,
    aspect_ratio: str = "9:16",
    product_closeup: bool = False,
    approved_asset: bool = False,
) -> EpisodePlan:
    boards: list[Storyboard] = []
    for index in range(storyboards):
        boards.append(
            Storyboard(
                storyboard_id=f"b{index}",
                shots=[
                    Shot(
                        shot_id=f"b{index}-s1",
                        action="turns toward the window",
                        prompt="a person by a window",
                        product_closeup=product_closeup and index == 0,
                        approved_asset_id=uuid4() if approved_asset and index == 0 else None,
                    )
                ],
                references=[f"ref-{slot}" for slot in range(references)],
            )
        )
    return EpisodePlan(
        brief="A short vertical drama.",
        aspect_ratio=aspect_ratio,
        storyboards=boards,
    )


def test_ten_storyboard_plan_matches_default_recipe():
    recipe = load_recipe(RECIPE)
    plan = make_plan(storyboards=10, references=recipe.reference_count)
    plan.validate_for(recipe)
    assert recipe.recipe_id == "drama_vertical_120s_v1"
    assert recipe.aspect_ratio == "9:16"
    assert recipe.reference_count == 9


def test_rejects_plan_that_is_not_vertical():
    recipe = load_recipe(RECIPE)
    plan = make_plan(storyboards=10, references=9, aspect_ratio="16:9")
    with pytest.raises(RecipeValidationError):
        plan.validate_for(recipe)


def test_rejects_storyboard_count_outside_recipe_range():
    recipe = load_recipe(RECIPE)
    plan = make_plan(storyboards=9, references=9)
    with pytest.raises(RecipeValidationError):
        plan.validate_for(recipe)


def test_product_closeup_requires_approved_real_asset():
    recipe = load_recipe(RECIPE)
    generated = make_plan(storyboards=10, references=9, product_closeup=True)
    with pytest.raises(RecipeValidationError):
        generated.validate_for(recipe)
    approved = make_plan(
        storyboards=10,
        references=9,
        product_closeup=True,
        approved_asset=True,
    )
    approved.validate_for(recipe)


def test_status_and_timeline_contracts_are_provider_neutral():
    asset = AssetRef(
        asset_id=uuid4(),
        sha256="abc",
        uri="memory://abc",
        media_type="video/mp4",
        origin=AssetOrigin.approved_real,
    )
    timeline = Timeline(aspect_ratio="9:16", resolution="720p", clips=[], subtitles=[])
    assert JobStatus.delivered_with_flags == "delivered_with_flags"
    assert TaskStatus.pending == "pending"
    assert timeline.aspect_ratio == "9:16"
    assert asset.origin == AssetOrigin.approved_real
