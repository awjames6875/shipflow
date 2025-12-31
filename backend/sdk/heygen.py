"""
HeyGen SDK - Type-safe HeyGen API client with avatar type contracts.

This SDK prevents the most common HeyGen errors:
- Using avatar_id for a talking photo (should be talking_photo_id)
- Using talking_photo_id for a video avatar (should be avatar_id)
- Wrong ID format (must be 32 hex characters)
- Video URL being None when status is "completed"
"""

import re
import asyncio
import logging
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, HttpUrl
import httpx

from .errors import HeyGenError, ConfigurationError, ValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# AVATAR CONFIGURATION MODELS
# =============================================================================


class TalkingPhotoConfig(BaseModel):
    """
    Config for talking photo avatars (created from a PHOTO in HeyGen dashboard).

    Use this when you uploaded a PHOTO to create your avatar.
    Get your ID from: GET /v1/talking_photo.list
    """

    type: Literal["talking_photo"] = "talking_photo"
    talking_photo_id: str = Field(..., description="32-character hex ID from /v1/talking_photo.list")

    @field_validator("talking_photo_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-f0-9]{32}$", v):
            raise ValueError(
                f"Invalid talking_photo_id format: '{v}'. "
                f"Must be exactly 32 lowercase hex characters (got {len(v)} chars). "
                "Get correct ID from: GET https://api.heygen.com/v1/talking_photo.list"
            )
        return v

    def to_api_payload(self) -> dict:
        """Convert to HeyGen API character payload."""
        return {
            "type": self.type,
            "talking_photo_id": self.talking_photo_id,
        }


class VideoAvatarConfig(BaseModel):
    """
    Config for video avatars (created from a VIDEO in HeyGen dashboard, or public avatars).

    Use this when you:
    - Uploaded a 2+ minute VIDEO to create your avatar
    - Are using a public/preset avatar like "Anna_public_3_20240108"

    Get your ID from: GET /v2/avatars
    """

    type: Literal["avatar"] = "avatar"
    avatar_id: str = Field(..., description="32-character hex ID from /v2/avatars")
    avatar_style: Literal["normal", "happy", "sad", "serious", "yelling"] = "normal"
    scale: float = Field(default=1.0, ge=0.1, le=2.0)

    @field_validator("avatar_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        v = v.strip()
        # Allow both 32-char hex IDs and public avatar names
        if re.match(r"^[a-f0-9]{32}$", v):
            return v
        if re.match(r"^[A-Za-z0-9_-]+$", v) and len(v) > 5:
            # Likely a public avatar name like "Anna_public_3_20240108"
            return v
        raise ValueError(
            f"Invalid avatar_id format: '{v}'. "
            "Must be 32 lowercase hex characters OR a valid public avatar name. "
            "Get correct ID from: GET https://api.heygen.com/v2/avatars"
        )

    def to_api_payload(self) -> dict:
        """Convert to HeyGen API character payload."""
        return {
            "type": self.type,
            "avatar_id": self.avatar_id,
            "avatar_style": self.avatar_style,
            "scale": self.scale,
        }


# Union type - forces you to choose the correct config type
AvatarConfig = Union[TalkingPhotoConfig, VideoAvatarConfig]


# =============================================================================
# VOICE CONFIGURATION
# =============================================================================


class VoiceConfig(BaseModel):
    """Voice configuration for video generation."""

    voice_id: str = Field(..., description="Voice ID from HeyGen")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: int = Field(default=50, ge=0, le=100)
    emotion: Literal["Excited", "Friendly", "Serious", "Soothing", "Broadcaster"] = "Friendly"

    def to_api_payload(self, input_text: str) -> dict:
        """Convert to HeyGen API voice payload."""
        return {
            "type": "text",
            "input_text": input_text,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "pitch": self.pitch,
            "emotion": self.emotion,
        }


# =============================================================================
# VIDEO RESULT
# =============================================================================


class VideoResult(BaseModel):
    """
    Result of a completed video generation.

    The video_url is REQUIRED - if the video is complete, the URL must exist.
    This prevents the "URL is empty" error when posting to Blotato.
    """

    video_id: str
    status: Literal["completed"]
    video_url: HttpUrl  # REQUIRED - not Optional! Prevents empty URL bugs.

    @field_validator("video_url", mode="before")
    @classmethod
    def validate_url(cls, v):
        if not v:
            raise ValueError(
                "video_url is empty even though status is 'completed'. "
                "This is a HeyGen API bug - wait a few more seconds and check again."
            )
        return v


class VideoStatus(BaseModel):
    """Status of a video being generated."""

    video_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    video_url: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# HEYGEN CLIENT
# =============================================================================


class HeyGenClient:
    """
    Type-safe HeyGen API client.

    Usage:
        client = HeyGenClient(api_key="your-key")

        # For talking photo (created from a PHOTO):
        config = TalkingPhotoConfig(talking_photo_id="d3882e6017e04a569868b81c6d60fab6")

        # For video avatar (created from a VIDEO):
        config = VideoAvatarConfig(avatar_id="6749d17784bf4e2fa243e19965b786b0")

        voice = VoiceConfig(voice_id="your-voice-id", speed=1.1, emotion="Excited")

        video_id = await client.create_video(config, voice, "Hello world!")
        result = await client.wait_for_video(video_id)
        print(result.video_url)  # Guaranteed to be a valid URL
    """

    def __init__(self, api_key: str, timeout: float = 60.0):
        if not api_key:
            raise ConfigurationError(
                "HeyGen API key is not set",
                "Set HEYGEN_API_KEY in your .env file"
            )
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://api.heygen.com"

    def _headers(self) -> dict:
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def list_talking_photos(self) -> list[dict]:
        """
        List all talking photos in your account.

        Use this to find the correct talking_photo_id for TalkingPhotoConfig.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/talking_photo.list",
                headers=self._headers(),
            )

            if response.status_code != 200:
                raise HeyGenError(
                    "Failed to list talking photos",
                    status_code=response.status_code,
                    response_body=response.text,
                    fix_instruction="Check your HEYGEN_API_KEY is valid",
                )

            data = response.json()
            photos = data.get("data", [])

            # Return simplified list
            return [
                {
                    "id": p.get("id"),
                    "image_url": p.get("image_url"),
                    "is_preset": p.get("is_preset", False),
                }
                for p in photos
            ]

    async def list_avatars(self) -> list[dict]:
        """
        List all video avatars in your account.

        Use this to find the correct avatar_id for VideoAvatarConfig.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v2/avatars",
                headers=self._headers(),
            )

            if response.status_code != 200:
                raise HeyGenError(
                    "Failed to list avatars",
                    status_code=response.status_code,
                    response_body=response.text,
                    fix_instruction="Check your HEYGEN_API_KEY is valid",
                )

            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])

            # Return simplified list
            return [
                {
                    "avatar_id": a.get("avatar_id"),
                    "avatar_name": a.get("avatar_name"),
                    "preview_image_url": a.get("preview_image_url"),
                }
                for a in avatars
            ]

    async def verify_talking_photo_exists(self, talking_photo_id: str) -> bool:
        """Check if a talking photo ID exists in your account."""
        try:
            photos = await self.list_talking_photos()
            return any(p["id"] == talking_photo_id for p in photos)
        except HeyGenError:
            return False

    async def verify_avatar_exists(self, avatar_id: str) -> bool:
        """Check if an avatar ID exists in your account."""
        try:
            avatars = await self.list_avatars()
            return any(a["avatar_id"] == avatar_id for a in avatars)
        except HeyGenError:
            return False

    async def create_video(
        self,
        avatar: AvatarConfig,
        voice: VoiceConfig,
        script: str,
        title: str = "Generated Video",
        dimension: tuple[int, int] = (720, 1280),
    ) -> str:
        """
        Create a video with the specified avatar and voice.

        Args:
            avatar: TalkingPhotoConfig or VideoAvatarConfig
            voice: VoiceConfig with voice settings
            script: The text for the avatar to speak
            title: Video title
            dimension: (width, height) tuple, default 720x1280 (9:16)

        Returns:
            video_id to use with wait_for_video()
        """
        if not script or not script.strip():
            raise ValidationError(
                "Script cannot be empty",
                "Provide the text you want the avatar to speak"
            )

        video_input = {
            "character": avatar.to_api_payload(),
            "voice": voice.to_api_payload(script),
        }

        payload = {
            "video_inputs": [video_input],
            "dimension": {"width": dimension[0], "height": dimension[1]},
            "aspect_ratio": "9:16",
            "title": title,
        }

        logger.info(f"Creating HeyGen video with {avatar.type} avatar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v2/video/generate",
                headers=self._headers(),
                json=payload,
            )

            logger.info(f"HeyGen response status: {response.status_code}")

            if response.status_code != 200:
                # Parse common errors
                error_text = response.text
                fix = "Check HeyGen dashboard for more details"

                if "avatar_not_found" in error_text.lower():
                    if isinstance(avatar, TalkingPhotoConfig):
                        fix = (
                            f"Avatar ID '{avatar.talking_photo_id}' not found. "
                            "Verify with: GET /v1/talking_photo.list"
                        )
                    else:
                        fix = (
                            f"Avatar ID '{avatar.avatar_id}' not found. "
                            "Verify with: GET /v2/avatars"
                        )

                raise HeyGenError(
                    "Failed to create video",
                    status_code=response.status_code,
                    response_body=error_text,
                    fix_instruction=fix,
                )

            data = response.json()
            video_id = data["data"]["video_id"]
            logger.info(f"Created video with ID: {video_id}")
            return video_id

    async def get_video_status(self, video_id: str) -> VideoStatus:
        """Get the current status of a video."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/v1/video_status.get",
                headers=self._headers(),
                params={"video_id": video_id},
            )

            if response.status_code != 200:
                raise HeyGenError(
                    f"Failed to get video status for {video_id}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            data = response.json()["data"]
            return VideoStatus(
                video_id=video_id,
                status=data["status"],
                video_url=data.get("video_url"),
                error=data.get("error"),
            )

    async def wait_for_video(
        self,
        video_id: str,
        max_attempts: int = 30,
        delay_seconds: int = 20,
    ) -> VideoResult:
        """
        Poll until video is ready.

        Args:
            video_id: The video ID from create_video()
            max_attempts: Maximum polling attempts (default 30 = 10 minutes)
            delay_seconds: Seconds between polls (default 20)

        Returns:
            VideoResult with guaranteed video_url

        Raises:
            HeyGenError: If video generation fails or times out
        """
        for attempt in range(max_attempts):
            status = await self.get_video_status(video_id)
            logger.info(
                f"Video {video_id} status: {status.status} "
                f"(attempt {attempt + 1}/{max_attempts})"
            )

            if status.status == "completed":
                if not status.video_url:
                    # Sometimes HeyGen returns completed without URL - wait a bit more
                    logger.warning("Status is completed but no URL yet, waiting...")
                    await asyncio.sleep(5)
                    status = await self.get_video_status(video_id)

                if not status.video_url:
                    raise HeyGenError(
                        "Video completed but URL is missing",
                        fix_instruction="This is a HeyGen API bug. Try again in a few seconds.",
                    )

                return VideoResult(
                    video_id=video_id,
                    status="completed",
                    video_url=status.video_url,
                )

            if status.status == "failed":
                raise HeyGenError(
                    f"Video generation failed: {status.error or 'Unknown error'}",
                    fix_instruction="Check HeyGen dashboard for details. Common issues: invalid voice_id, script too long.",
                )

            await asyncio.sleep(delay_seconds)

        raise HeyGenError(
            f"Video generation timed out after {max_attempts * delay_seconds} seconds",
            fix_instruction="Video is still processing. Check status manually or increase max_attempts.",
        )
