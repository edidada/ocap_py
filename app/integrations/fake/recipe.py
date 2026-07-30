"""Recipe（配方管理）mock 客户端。"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.integrations.base import IntegrationClient
from app.integrations.dtos import RecipeChangeResultDTO, RecipeDTO
from app.integrations.fake.store import FakeStore


class FakeRecipeClient(IntegrationClient):
    system_code = "recipe"

    def __init__(self, store: FakeStore):
        self.store = store

    async def get_recipe(self, recipe_id: str) -> RecipeDTO:
        recipe = self.store.recipes.get(recipe_id)
        if recipe is None:
            raise NotFoundError(f"配方不存在: {recipe_id}")
        return recipe

    async def change_recipe(self, recipe_id: str, new_params: dict) -> RecipeChangeResultDTO:
        recipe = await self.get_recipe(recipe_id)
        old_params = dict(recipe.params)
        recipe.params = {**old_params, **new_params}
        recipe.version += 1
        return RecipeChangeResultDTO(
            success=True,
            recipe_id=recipe_id,
            new_version=recipe.version,
            message=f"参数已更新: {list(new_params.keys())}",
        )

    async def revert_recipe(self, recipe_id: str, old_params: dict) -> RecipeChangeResultDTO:
        recipe = await self.get_recipe(recipe_id)
        recipe.params = dict(old_params)
        recipe.version += 1
        return RecipeChangeResultDTO(
            success=True, recipe_id=recipe_id, new_version=recipe.version, message="配方已回滚"
        )
