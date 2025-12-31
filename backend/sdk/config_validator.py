"""
Config Validator - Validates all configuration at startup.

This validator runs before the app accepts any traffic and:
1. Checks all required environment variables are set
2. Validates formats (API keys, IDs)
3. Verifies IDs actually exist in the external services
4. Returns actionable error messages with exact fix instructions

If ANY validation fails, the app refuses to start.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass, field

from .heygen import HeyGenClient, TalkingPhotoConfig, VideoAvatarConfig
from .blotato import BlotaoClient
from .errors import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    service: str
    check: str
    passed: bool
    message: str = ""
    fix_instruction: str = ""


@dataclass
class ValidationReport:
    """Complete validation report for all services."""

    results: list[ValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def errors(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.passed]

    @property
    def warnings(self) -> list[ValidationResult]:
        return [r for r in self.results if r.passed and r.message]

    def print_report(self) -> None:
        """Print a formatted validation report."""
        print("\n" + "=" * 60)
        print("CONFIGURATION VALIDATION REPORT")
        print("=" * 60)

        if self.passed:
            print("\n[OK] All checks passed!\n")
            for r in self.results:
                print(f"  [OK] [{r.service}] {r.check}")
        else:
            print("\n[FAIL] VALIDATION FAILED - Cannot start application\n")
            print("ERRORS:")
            for r in self.errors:
                print(f"\n  [X] [{r.service}] {r.check}")
                print(f"    {r.message}")
                if r.fix_instruction:
                    print(f"    HOW TO FIX: {r.fix_instruction}")

        print("\n" + "=" * 60 + "\n")


class ConfigValidator:
    """
    Validates all configuration at startup.

    Usage:
        validator = ConfigValidator()
        report = await validator.validate_all()

        if not report.passed:
            report.print_report()
            raise RuntimeError("Configuration validation failed")
    """

    def __init__(self):
        # Load config from environment
        self.heygen_api_key = os.getenv("HEYGEN_API_KEY", "")
        self.heygen_avatar_type = os.getenv("HEYGEN_AVATAR_TYPE", "talking_photo")
        self.heygen_talking_photo_id = os.getenv("HEYGEN_TALKING_PHOTO_ID", "")
        self.heygen_avatar_id = os.getenv("HEYGEN_AVATAR_ID", "")
        self.heygen_voice_id = os.getenv("HEYGEN_VOICE_ID", "")

        self.blotato_api_key = os.getenv("BLOTATO_API_KEY", "")
        self.blotato_tiktok_account_id = os.getenv("BLOTATO_TIKTOK_ACCOUNT_ID", "")
        self.blotato_instagram_account_id = os.getenv("BLOTATO_INSTAGRAM_ACCOUNT_ID", "")
        self.blotato_youtube_account_id = os.getenv("BLOTATO_YOUTUBE_ACCOUNT_ID", "")
        self.blotato_facebook_account_id = os.getenv("BLOTATO_FACEBOOK_ACCOUNT_ID", "")
        self.blotato_facebook_page_id = os.getenv("BLOTATO_FACEBOOK_PAGE_ID", "")
        self.blotato_pinterest_account_id = os.getenv("BLOTATO_PINTEREST_ACCOUNT_ID", "")
        self.blotato_pinterest_board_id = os.getenv("BLOTATO_PINTEREST_BOARD_ID", "")

        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY", "")

    async def validate_heygen(self) -> list[ValidationResult]:
        """Validate HeyGen configuration."""
        results = []

        # Check API key
        if not self.heygen_api_key:
            results.append(ValidationResult(
                service="HeyGen",
                check="API Key",
                passed=False,
                message="HEYGEN_API_KEY is not set",
                fix_instruction="Add HEYGEN_API_KEY to your .env file",
            ))
            return results  # Can't validate further without key

        results.append(ValidationResult(
            service="HeyGen",
            check="API Key",
            passed=True,
        ))

        # Check voice ID
        if not self.heygen_voice_id:
            results.append(ValidationResult(
                service="HeyGen",
                check="Voice ID",
                passed=False,
                message="HEYGEN_VOICE_ID is not set",
                fix_instruction="Add HEYGEN_VOICE_ID to your .env file",
            ))
        else:
            results.append(ValidationResult(
                service="HeyGen",
                check="Voice ID",
                passed=True,
            ))

        # Validate avatar based on type
        if self.heygen_avatar_type == "talking_photo":
            if not self.heygen_talking_photo_id:
                results.append(ValidationResult(
                    service="HeyGen",
                    check="Talking Photo ID",
                    passed=False,
                    message="HEYGEN_AVATAR_TYPE=talking_photo but HEYGEN_TALKING_PHOTO_ID is not set",
                    fix_instruction="Set HEYGEN_TALKING_PHOTO_ID in .env. Get ID from: GET /v1/talking_photo.list",
                ))
            else:
                # Validate format
                try:
                    TalkingPhotoConfig(talking_photo_id=self.heygen_talking_photo_id)
                    results.append(ValidationResult(
                        service="HeyGen",
                        check="Talking Photo ID Format",
                        passed=True,
                    ))

                    # Verify ID exists in HeyGen
                    try:
                        client = HeyGenClient(self.heygen_api_key)
                        exists = await client.verify_talking_photo_exists(self.heygen_talking_photo_id)
                        if exists:
                            results.append(ValidationResult(
                                service="HeyGen",
                                check="Talking Photo Exists",
                                passed=True,
                            ))
                        else:
                            results.append(ValidationResult(
                                service="HeyGen",
                                check="Talking Photo Exists",
                                passed=False,
                                message=f"Talking photo ID '{self.heygen_talking_photo_id}' not found in your HeyGen account",
                                fix_instruction="Run: curl -H 'X-Api-Key: YOUR_KEY' https://api.heygen.com/v1/talking_photo.list",
                            ))
                    except Exception as e:
                        results.append(ValidationResult(
                            service="HeyGen",
                            check="Talking Photo Exists",
                            passed=False,
                            message=f"Could not verify talking photo: {e}",
                            fix_instruction="Check your HEYGEN_API_KEY is valid",
                        ))

                except ValueError as e:
                    results.append(ValidationResult(
                        service="HeyGen",
                        check="Talking Photo ID Format",
                        passed=False,
                        message=str(e),
                        fix_instruction="ID must be 32 hex characters. Get from: GET /v1/talking_photo.list",
                    ))

        elif self.heygen_avatar_type == "avatar":
            if not self.heygen_avatar_id:
                results.append(ValidationResult(
                    service="HeyGen",
                    check="Avatar ID",
                    passed=False,
                    message="HEYGEN_AVATAR_TYPE=avatar but HEYGEN_AVATAR_ID is not set",
                    fix_instruction="Set HEYGEN_AVATAR_ID in .env. Get ID from: GET /v2/avatars",
                ))
            else:
                # Validate format
                try:
                    VideoAvatarConfig(avatar_id=self.heygen_avatar_id)
                    results.append(ValidationResult(
                        service="HeyGen",
                        check="Avatar ID Format",
                        passed=True,
                    ))

                    # Verify ID exists
                    try:
                        client = HeyGenClient(self.heygen_api_key)
                        exists = await client.verify_avatar_exists(self.heygen_avatar_id)
                        if exists:
                            results.append(ValidationResult(
                                service="HeyGen",
                                check="Avatar Exists",
                                passed=True,
                            ))
                        else:
                            results.append(ValidationResult(
                                service="HeyGen",
                                check="Avatar Exists",
                                passed=False,
                                message=f"Avatar ID '{self.heygen_avatar_id}' not found in your HeyGen account",
                                fix_instruction="Run: curl -H 'X-Api-Key: YOUR_KEY' https://api.heygen.com/v2/avatars",
                            ))
                    except Exception as e:
                        results.append(ValidationResult(
                            service="HeyGen",
                            check="Avatar Exists",
                            passed=False,
                            message=f"Could not verify avatar: {e}",
                        ))

                except ValueError as e:
                    results.append(ValidationResult(
                        service="HeyGen",
                        check="Avatar ID Format",
                        passed=False,
                        message=str(e),
                    ))
        else:
            results.append(ValidationResult(
                service="HeyGen",
                check="Avatar Type",
                passed=False,
                message=f"Invalid HEYGEN_AVATAR_TYPE: '{self.heygen_avatar_type}'",
                fix_instruction="Must be 'talking_photo' or 'avatar'",
            ))

        return results

    async def validate_blotato(self) -> list[ValidationResult]:
        """Validate Blotato configuration."""
        results = []

        # Check API key
        if not self.blotato_api_key:
            results.append(ValidationResult(
                service="Blotato",
                check="API Key",
                passed=False,
                message="BLOTATO_API_KEY is not set",
                fix_instruction="Get API key from https://my.blotato.com/settings/api-keys",
            ))
            return results

        # Validate format
        if not self.blotato_api_key.startswith("blt_"):
            results.append(ValidationResult(
                service="Blotato",
                check="API Key Format",
                passed=False,
                message=f"Invalid API key format: '{self.blotato_api_key[:10]}...'",
                fix_instruction="Blotato API keys must start with 'blt_'",
            ))
            return results

        results.append(ValidationResult(
            service="Blotato",
            check="API Key",
            passed=True,
        ))

        # Test connection
        try:
            client = BlotaoClient(self.blotato_api_key)
            test_result = await client.test_connection()
            if test_result["status"] == "success":
                results.append(ValidationResult(
                    service="Blotato",
                    check="API Connection",
                    passed=True,
                ))
            else:
                results.append(ValidationResult(
                    service="Blotato",
                    check="API Connection",
                    passed=False,
                    message=test_result["message"],
                    fix_instruction=test_result.get("fix", ""),
                ))
        except Exception as e:
            results.append(ValidationResult(
                service="Blotato",
                check="API Connection",
                passed=False,
                message=str(e),
            ))

        # Check platform-specific requirements

        # Facebook requires both account_id AND page_id
        if self.blotato_facebook_account_id and not self.blotato_facebook_page_id:
            results.append(ValidationResult(
                service="Blotato",
                check="Facebook Page ID",
                passed=False,
                message="BLOTATO_FACEBOOK_ACCOUNT_ID is set but BLOTATO_FACEBOOK_PAGE_ID is missing",
                fix_instruction="Facebook requires BOTH account_id AND page_id. Get page_id from Blotato dashboard.",
            ))

        # Pinterest requires board_id - warn but don't fail (Pinterest posting will be skipped)
        if self.blotato_pinterest_account_id and not self.blotato_pinterest_board_id:
            results.append(ValidationResult(
                service="Blotato",
                check="Pinterest Board ID",
                passed=True,  # Don't block startup, just warn
                message="BLOTATO_PINTEREST_BOARD_ID missing - Pinterest posting will be skipped",
                fix_instruction="Pinterest requires board_id. Get it from Blotato dashboard.",
            ))

        return results

    async def validate_openai(self) -> list[ValidationResult]:
        """Validate OpenAI configuration."""
        results = []

        if not self.openai_api_key:
            results.append(ValidationResult(
                service="OpenAI",
                check="API Key",
                passed=False,
                message="OPENAI_API_KEY is not set",
                fix_instruction="Add OPENAI_API_KEY to your .env file",
            ))
        else:
            results.append(ValidationResult(
                service="OpenAI",
                check="API Key",
                passed=True,
            ))

        return results

    async def validate_perplexity(self) -> list[ValidationResult]:
        """Validate Perplexity configuration."""
        results = []

        if not self.perplexity_api_key:
            results.append(ValidationResult(
                service="Perplexity",
                check="API Key",
                passed=False,
                message="PERPLEXITY_API_KEY is not set",
                fix_instruction="Add PERPLEXITY_API_KEY to your .env file",
            ))
        else:
            results.append(ValidationResult(
                service="Perplexity",
                check="API Key",
                passed=True,
            ))

        return results

    async def validate_all(self) -> ValidationReport:
        """
        Run all validators and return a complete report.

        Usage:
            validator = ConfigValidator()
            report = await validator.validate_all()

            if not report.passed:
                report.print_report()
                raise RuntimeError("Fix configuration errors before starting")
        """
        report = ValidationReport()

        # Run all validators
        heygen_results = await self.validate_heygen()
        blotato_results = await self.validate_blotato()
        openai_results = await self.validate_openai()
        perplexity_results = await self.validate_perplexity()

        report.results.extend(heygen_results)
        report.results.extend(blotato_results)
        report.results.extend(openai_results)
        report.results.extend(perplexity_results)

        return report


async def validate_config_or_exit() -> None:
    """
    Validate configuration and exit if invalid.

    Call this in FastAPI lifespan to fail fast on startup.
    """
    validator = ConfigValidator()
    report = await validator.validate_all()

    report.print_report()

    if not report.passed:
        logger.error("Configuration validation failed. Fix errors and restart.")
        raise RuntimeError("Configuration validation failed")

    logger.info("Configuration validation passed!")
