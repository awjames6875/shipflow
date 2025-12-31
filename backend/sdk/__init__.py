"""
ShipFlow SDK - Type-safe API clients with built-in contracts.

This SDK prevents common configuration errors by validating at object creation time,
not at API call time. If you can create the object, the API call will work.
"""

from .errors import SDKError, ConfigurationError, ValidationError, APIError
from .heygen import (
    TalkingPhotoConfig,
    VideoAvatarConfig,
    AvatarConfig,
    VoiceConfig,
    VideoResult,
    HeyGenClient,
)
from .blotato import (
    TikTokPost,
    FacebookPost,
    InstagramPost,
    YouTubePost,
    PinterestPost,
    TwitterPost,
    BlueskyPost,
    BlotaoClient,
)
from .config_validator import ConfigValidator

__all__ = [
    # Errors
    "SDKError",
    "ConfigurationError",
    "ValidationError",
    "APIError",
    # HeyGen
    "TalkingPhotoConfig",
    "VideoAvatarConfig",
    "AvatarConfig",
    "VoiceConfig",
    "VideoResult",
    "HeyGenClient",
    # Blotato
    "TikTokPost",
    "FacebookPost",
    "InstagramPost",
    "YouTubePost",
    "PinterestPost",
    "TwitterPost",
    "BlueskyPost",
    "BlotaoClient",
    # Validator
    "ConfigValidator",
]
