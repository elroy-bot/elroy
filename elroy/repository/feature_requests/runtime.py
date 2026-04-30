from dataclasses import dataclass

from ...core.ctx import ElroyConfig


@dataclass(frozen=True)
class FeatureRequestRuntime:
    user_token: str


def build_feature_request_runtime(ctx: ElroyConfig) -> FeatureRequestRuntime:
    return FeatureRequestRuntime(user_token=ctx.user_token)
