"""Module to define settings for uploading data to the scratch or archive
buckets."""

from enum import Enum
from pathlib import PurePosixPath
from typing import List, Literal, Optional, Set

from pydantic import (
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings


class BucketType(str, Enum):
    """Types of s3 bucket users can write to through service"""

    PRIVATE = "private"
    OPEN = "open"
    SCRATCH = "scratch"
    ARCHIVE = "archive"


class EmailNotificationType(str, Enum):
    """Types of email notifications a user can select"""

    BEGIN = "begin"
    END = "end"
    FAIL = "fail"
    RETRY = "retry"
    ALL = "all"


class S3UploadJobConfigs(BaseSettings):
    """Configs for uploading a local directory to S3."""

    user_email: EmailStr = Field(
        ...,
        description=(
            "User email address. Data will be stored in archive or scratch "
            "under user's email name."
        ),
    )

    email_notification_types: Optional[Set[EmailNotificationType]] = Field(
        default=None,
        description=(
            "Types of job statuses to receive email notifications about"
        ),
    )
    s3_bucket: Literal[BucketType.SCRATCH, BucketType.ARCHIVE] = Field(
        ...,
        description="Bucket where data will be uploaded.",
        title="S3 Bucket",
    )
    input_source: PurePosixPath = Field(
        ..., description="Local source directory to sync to s3."
    )
    force_cloud_sync: bool = Field(
        default=False,
        description=(
            "Force syncing of data folder even if location exists in cloud"
        ),
        title="Force Cloud Sync",
    )

    @computed_field
    def s3_prefix(self) -> str:
        """Construct s3_prefix from configs."""
        user_name = self.user_email.split("@")[0]
        input_source = self.input_source.name
        s3_prefix = f"{user_name}/{input_source}"
        return s3_prefix.strip("/")


class S3UploadSubmitJobRequest(BaseSettings):
    """Main request that will be sent to the backend. Bundles jobs into a list
    and allows a user to add an email address to receive notifications."""

    model_config = ConfigDict(use_enum_values=True)

    user_email: Optional[EmailStr] = Field(
        default=None,
        description=(
            "Optional email address to receive job status notifications"
        ),
    )
    email_notification_types: Set[EmailNotificationType] = Field(
        default={EmailNotificationType.FAIL},
        description=(
            "Types of job statuses to receive email notifications about"
        ),
    )
    upload_jobs: List[S3UploadJobConfigs] = Field(
        ...,
        description="List of upload jobs to process. Max of 20 at a time.",
        min_items=1,
        max_items=100,
    )

    @model_validator(mode="after")
    def propagate_email_settings(self):
        """Propagate email settings from global to individual jobs"""
        global_email_user = self.user_email
        global_email_notification_types = self.email_notification_types
        for upload_job in self.upload_jobs:
            if global_email_user is not None and upload_job.user_email is None:
                upload_job.user_email = global_email_user
            if upload_job.email_notification_types is None:
                upload_job.email_notification_types = (
                    global_email_notification_types
                )
        return self
