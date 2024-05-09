"""Core models for using aind-data-transfer-service"""

import re
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, ClassVar, List, Optional, Union

from aind_data_schema_models.data_name_patterns import build_data_name
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.platforms import Platform
from aind_slurm_rest import V0036JobSubmission
from pydantic import (
    ConfigDict,
    Field,
    ValidationInfo,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings


class BucketType(str, Enum):
    """Types of s3 bucket users can write to through service"""

    PRIVATE = "private"
    OPEN = "open"
    SCRATCH = "scratch"


class ModalityConfigs(BaseSettings):
    """Class to contain configs for each modality type"""

    # Need some way to extract abbreviations. Maybe a public method can be
    # added to the Modality class
    _MODALITY_MAP: ClassVar = {
        m().abbreviation.upper().replace("-", "_"): m().abbreviation
        for m in Modality._ALL
    }

    modality: Modality.ONE_OF = Field(
        ..., description="Data collection modality", title="Modality"
    )
    source: PurePosixPath = Field(
        ...,
        description="Location of raw data to be uploaded",
        title="Data Source",
    )
    compress_raw_data: Optional[bool] = Field(
        default=None,
        description="Run compression on data",
        title="Compress Raw Data",
        validate_default=True,
    )
    extra_configs: Optional[PurePosixPath] = Field(
        default=None,
        description="Location of additional configuration file",
        title="Extra Configs",
    )
    slurm_settings: Optional[V0036JobSubmission] = Field(
        default=None,
        description="Custom slurm submission script to use",
        title="Slurm Settings",
    )

    @computed_field
    def output_folder_name(self) -> str:
        """Construct the default folder name for the modality."""
        return self.modality.abbreviation

    @field_validator("modality", mode="before")
    def parse_modality_string(
        cls, input_modality: Union[str, dict, Modality]
    ) -> Union[dict, Modality]:
        """Attempts to convert strings to a Modality model. Raises an error
        if unable to do so."""
        if isinstance(input_modality, str):
            modality_abbreviation = cls._MODALITY_MAP.get(
                input_modality.upper().replace("-", "_")
            )
            if modality_abbreviation is None:
                raise AttributeError(f"Unknown Modality: {input_modality}")
            return Modality.from_abbreviation(modality_abbreviation)
        else:
            return input_modality

    @field_validator("compress_raw_data", mode="after")
    def get_compress_source_default(
        cls, compress_source: Optional[bool], info: ValidationInfo
    ) -> bool:
        """Set compress source default to True for ecephys data."""
        if (
            compress_source is None
            and info.data.get("modality") == Modality.ECEPHYS
        ):
            return True
        elif compress_source is not None:
            return compress_source
        else:
            return False


class BasicUploadJobConfigs(BaseSettings):
    """Configuration for the basic upload job"""

    # Allow users to pass in extra fields
    model_config = ConfigDict(extra="allow", use_enum_values=True)

    # Need some way to extract abbreviations. Maybe a public method can be
    # added to the Platform class
    _PLATFORM_MAP: ClassVar = {
        p().abbreviation.upper(): p().abbreviation for p in Platform._ALL
    }
    _MODALITY_ENTRY_PATTERN: ClassVar = re.compile(r"^modality(\d*)$")
    _DATETIME_PATTERN1: ClassVar = re.compile(
        r"^\d{4}-\d{2}-\d{2}[ |T]\d{2}:\d{2}:\d{2}$"
    )
    _DATETIME_PATTERN2: ClassVar = re.compile(
        r"^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [APap][Mm]$"
    )

    project_name: str = Field(
        ..., description="Name of project", title="Project Name"
    )
    process_capsule_id: Optional[str] = Field(
        None,
        description="Use custom codeocean capsule or pipeline id",
        title="Process Capsule ID",
    )
    s3_bucket: BucketType = Field(
        BucketType.PRIVATE,
        description=(
            "Bucket where data will be uploaded. If null, will upload to "
            "default bucket"
        ),
        title="S3 Bucket",
    )
    platform: Platform.ONE_OF = Field(
        ..., description="Platform", title="Platform"
    )
    modalities: List[ModalityConfigs] = Field(
        ...,
        description="Data collection modalities and their directory location",
        title="Modalities",
        min_items=1,
    )
    subject_id: str = Field(..., description="Subject ID", title="Subject ID")
    acq_datetime: datetime = Field(
        ...,
        description="Datetime data was acquired",
        title="Acquisition Datetime",
    )
    metadata_dir: Optional[PurePosixPath] = Field(
        default=None,
        description="Directory of metadata",
        title="Metadata Directory",
    )
    metadata_dir_force: bool = Field(
        default=False,
        description=(
            "Whether to override metadata from service with metadata in "
            "optional metadata directory"
        ),
        title="Metadata Directory Force",
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
        return build_data_name(
            label=f"{self.platform.abbreviation}_{self.subject_id}",
            creation_datetime=self.acq_datetime,
        )

    @field_validator("s3_bucket", mode="before")
    def map_bucket(
        cls, bucket: Optional[Union[BucketType, str]]
    ) -> BucketType:
        """We're adding a policy that data uploaded through the service can
        only land in a handful of buckets. As default, things will be
        stored in the private bucket"""
        if isinstance(bucket, str) and (BucketType.OPEN.value in bucket):
            return BucketType.OPEN
        elif isinstance(bucket, str) and (BucketType.SCRATCH.value in bucket):
            return BucketType.SCRATCH
        elif isinstance(bucket, BucketType):
            return bucket
        else:
            return BucketType.PRIVATE

    @field_validator("platform", mode="before")
    def parse_platform_string(
        cls, input_platform: Union[str, dict, Platform]
    ) -> Union[dict, Platform]:
        """Attempts to convert strings to a Platform model. Raises an error
        if unable to do so."""
        if isinstance(input_platform, str):
            platform_abbreviation = cls._PLATFORM_MAP.get(
                input_platform.upper()
            )
            if platform_abbreviation is None:
                raise AttributeError(f"Unknown Platform: {input_platform}")
            else:
                return Platform.from_abbreviation(platform_abbreviation)
        else:
            return input_platform

    @field_validator("acq_datetime", mode="before")
    def _parse_datetime(cls, datetime_val: Any) -> datetime:
        """Parses datetime string to %YYYY-%MM-%DD HH:mm:ss"""
        is_str = isinstance(datetime_val, str)
        if is_str and re.match(
            BasicUploadJobConfigs._DATETIME_PATTERN1, datetime_val
        ):
            return datetime.fromisoformat(datetime_val)
        elif is_str and re.match(
            BasicUploadJobConfigs._DATETIME_PATTERN2, datetime_val
        ):
            return datetime.strptime(datetime_val, "%m/%d/%Y %I:%M:%S %p")
        elif is_str:
            raise ValueError(
                "Incorrect datetime format, should be"
                " YYYY-MM-DD HH:mm:ss or MM/DD/YYYY I:MM:SS P"
            )
        else:
            return datetime_val
