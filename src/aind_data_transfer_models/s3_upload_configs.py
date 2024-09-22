"""Module to define settings for uploading data to the scratch or archive
buckets."""

from enum import Enum
from pathlib import PurePosixPath
from typing import List, Literal, Optional, Set

from aind_slurm_rest import V0036JobProperties
from pydantic import EmailStr, Field, model_validator
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

    user_email: Optional[EmailStr] = Field(
        default=None,
        description="User email address to send notifications to.",
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
    s3_prefix: str = Field(
        ...,
        description=(
            "Should be the project name if storing in archive. Should be user "
            "name if storing in scratch."
        ),
    )
    force_cloud_sync: bool = Field(
        default=False,
        description=(
            "Force syncing of data folder even if location exists in cloud"
        ),
        title="Force Cloud Sync",
    )
    slurm_settings: Optional[V0036JobProperties] = Field(
        default=None,
        description=(
            "Custom slurm job properties. `environment` is a required field. "
            "Please set it to an empty dictionary. A downstream process will "
            "overwrite it."
        ),
        title="Slurm Settings",
    )


class S3UploadSubmitJobRequest(BaseSettings):
    """Main request that will be sent to the backend. Bundles jobs into a list
    and allows a user to add an email address to receive notifications."""

    job_type: Literal["s3_upload"] = "s3_upload"
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
