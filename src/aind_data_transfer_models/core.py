"""Core models for using aind-data-transfer-service"""

import logging
import re
from copy import deepcopy
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, ClassVar, List, Optional, Set, Union, get_args

from aind_data_schema_models.data_name_patterns import build_data_name
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.platforms import Platform
from aind_metadata_mapper.models import (
    JobSettings as GatherMetadataJobSettings,
)
from aind_metadata_mapper.models import (
    ProceduresSettings,
    RawDataDescriptionSettings,
    SessionSettings,
    SubjectSettings,
)
from aind_slurm_rest import V0036JobProperties
from pydantic import (
    ConfigDict,
    EmailStr,
    Field,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings

from aind_data_transfer_models.trigger import TriggerConfigModel, ValidJobType


class EmailNotificationType(str, Enum):
    """Types of email notifications a user can select"""

    BEGIN = "begin"
    END = "end"
    FAIL = "fail"
    RETRY = "retry"
    ALL = "all"


class BucketType(str, Enum):
    """Types of s3 bucket users can write to through service"""

    PRIVATE = "private"
    OPEN = "open"
    SCRATCH = "scratch"


class ModalityConfigs(BaseSettings):
    """Class to contain configs for each modality type"""

    model_config = ConfigDict(extra="allow")

    # Need some way to extract abbreviations. Maybe a public method can be
    # added to the Modality class
    _MODALITY_MAP: ClassVar = {
        m().abbreviation.upper().replace("-", "_"): m().abbreviation
        for m in Modality.ALL
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
    slurm_settings: Optional[V0036JobProperties] = Field(
        default=None,
        description=(
            "Custom slurm job properties. `environment` is a required field. "
            "Please set it to an empty dictionary. A downstream process will "
            "overwrite it."
        ),
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

    @model_validator(mode="before")
    def check_computed_field(cls, data: Any) -> Any:
        """If the computed field is present, we check that it's expected. If
        this validator isn't added, then an 'extra field not allow' error
        will be raised when serializing and deserializing json."""
        if (
            isinstance(data, dict)
            and data.get("output_folder_name") is not None
        ):
            modality = data.get("modality", dict()).get("abbreviation")
            if modality != data.get("output_folder_name"):
                raise ValueError(
                    f"output_folder_name {data.get('output_folder_name')} "
                    f"doesn't match {modality}!"
                )
            else:
                del data["output_folder_name"]
        return data


class BasicUploadJobConfigs(BaseSettings):
    """Configuration for the basic upload job"""

    model_config = ConfigDict(use_enum_values=True, extra="allow")

    # Need some way to extract abbreviations. Maybe a public method can be
    # added to the Platform class
    _PLATFORM_MAP: ClassVar = {
        p().abbreviation.upper(): p().abbreviation for p in Platform.ALL
    }
    _DATETIME_PATTERN1: ClassVar = re.compile(
        r"^\d{4}-\d{2}-\d{2}[ |T]\d{2}:\d{2}:\d{2}$"
    )
    _DATETIME_PATTERN2: ClassVar = re.compile(
        r"^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [APap][Mm]$"
    )

    user_email: Optional[EmailStr] = Field(
        default=None,
        description=(
            "Optional email address to receive job status notifications"
        ),
    )

    email_notification_types: Optional[Set[EmailNotificationType]] = Field(
        default=None,
        description=(
            "Types of job statuses to receive email notifications about"
        ),
    )

    project_name: str = Field(
        ..., description="Name of project", title="Project Name"
    )
    input_data_mount: Optional[str] = Field(
        default=None,
        description="(deprecated - set trigger_capsule_configs)",
        title="Input Data Mount",
    )
    process_capsule_id: Optional[str] = Field(
        None,
        description="(deprecated - set trigger_capsule_configs)",
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
    metadata_configs: Optional[GatherMetadataJobSettings] = Field(
        default=None,
        description="Settings for gather metadata job",
        title="Metadata Configs",
        validate_default=True,
    )
    trigger_capsule_configs: Optional[TriggerConfigModel] = Field(
        default=None,
        description=(
            "Settings for the codeocean trigger capsule. "
            "Validators will set defaults."
        ),
        title="Trigger Capsule Configs",
        validate_default=True,
    )

    @computed_field
    def s3_prefix(self) -> str:
        """Construct s3_prefix from configs."""
        return build_data_name(
            label=f"{self.platform.abbreviation}_{self.subject_id}",
            creation_datetime=self.acq_datetime,
        )

    @model_validator(mode="before")
    def check_computed_field(cls, data: Any) -> Any:
        """If the computed field is present, we check that it's expected. If
        this validator isn't added, then an 'extra field not allow' error
        will be raised when serializing and deserializing json."""
        if isinstance(data, dict) and data.get("s3_prefix") is not None:
            expected_s3_prefix = build_data_name(
                label=(
                    f"{data.get('platform', dict()).get('abbreviation')}"
                    f"_{data.get('subject_id')}"
                ),
                creation_datetime=datetime.fromisoformat(
                    data.get("acq_datetime")
                ),
            )
            if expected_s3_prefix != data.get("s3_prefix"):
                raise ValueError(
                    f"s3_prefix {data.get('s3_prefix')} doesn't match "
                    f"computed {expected_s3_prefix}!"
                )
            else:
                del data["s3_prefix"]
        return data

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

    @staticmethod
    def _get_job_type(
        platform: Platform, process_capsule_id: Optional[str] = None
    ) -> ValidJobType:
        """
        Determines job type based on Platform
        Parameters
        ----------
        platform : Platform
        process_capsule_id: Optional[str]

        Returns
        -------
        ValidJobType

        """
        if process_capsule_id is not None:
            return ValidJobType.RUN_GENERIC_PIPELINE
        if platform == Platform.ECEPHYS:
            return ValidJobType.ECEPHYS
        elif platform == Platform.SMARTSPIM:
            return ValidJobType.SMARTSPIM
        elif platform == Platform.SINGLE_PLANE_OPHYS:
            return ValidJobType.SINGLEPLANE_OPHYS
        elif platform == Platform.MULTIPLANE_OPHYS:
            return ValidJobType.MULTIPLANE_OPHYS
        else:
            return ValidJobType.REGISTER_DATA

    @model_validator(mode="after")
    def set_trigger_capsule_configs(self):
        """
        Sets default values for the code ocean trigger capsule.
        Returns
        -------

        """
        if (
            self.trigger_capsule_configs is not None
            and self.process_capsule_id is not None
            and self.trigger_capsule_configs.process_capsule_id
            != self.process_capsule_id
        ):
            logging.warning(
                "Only one of trigger_capsule_configs or legacy "
                "process_capsule_id should be set!"
            )
        if self.trigger_capsule_configs is None:
            default_trigger_capsule_configs = TriggerConfigModel(
                job_type=self._get_job_type(
                    self.platform, self.process_capsule_id
                ),
                process_capsule_id=self.process_capsule_id,
                input_data_mount=self.input_data_mount,
            )
        else:
            default_trigger_capsule_configs = (
                self.trigger_capsule_configs.model_copy(deep=True)
            )
        # Override these settings if the user supplied them.
        default_trigger_capsule_configs.bucket = self.s3_bucket
        default_trigger_capsule_configs.prefix = self.s3_prefix
        default_trigger_capsule_configs.asset_name = self.s3_prefix
        if default_trigger_capsule_configs.mount is None:
            default_trigger_capsule_configs.mount = self.s3_prefix
        default_trigger_capsule_configs.modalities = [
            m.modality for m in self.modalities
        ]
        self.trigger_capsule_configs = default_trigger_capsule_configs
        return self

    @model_validator(mode="wrap")
    def fill_in_metadata_configs(self, handler):
        """Fills in settings for gather metadata job"""
        all_configs = deepcopy(self)
        if isinstance(all_configs, BasicUploadJobConfigs):
            all_configs = all_configs.model_dump(
                exclude={
                    "s3_prefix": True,
                    "modalities": {"__all__": {"output_folder_name"}},
                }
            )
        if all_configs.get("metadata_configs") is not None:
            if isinstance(
                all_configs.get("metadata_configs"), GatherMetadataJobSettings
            ):
                user_defined_metadata_configs = all_configs.get(
                    "metadata_configs"
                ).model_dump()
            else:
                user_defined_metadata_configs = deepcopy(
                    all_configs.get("metadata_configs")
                )
            del all_configs["metadata_configs"]
        else:
            user_defined_metadata_configs = dict()
        if user_defined_metadata_configs.get("session_settings") is not None:
            user_defined_session_settings = deepcopy(
                user_defined_metadata_configs.get("session_settings")
            )
            del user_defined_metadata_configs["session_settings"]
        else:
            user_defined_session_settings = None
        validated_self = handler(all_configs)
        metadata_dir = (
            None
            if validated_self.metadata_dir is None
            else validated_self.metadata_dir.as_posix()
        )
        default_metadata_configs = {
            "directory_to_write_to": "stage",
            "subject_settings": SubjectSettings(
                subject_id=validated_self.subject_id
            ),
            "procedures_settings": ProceduresSettings(
                subject_id=validated_self.subject_id
            ),
            "raw_data_description_settings": RawDataDescriptionSettings(
                name=validated_self.s3_prefix,
                project_name=validated_self.project_name,
                modality=([mod.modality for mod in validated_self.modalities]),
            ),
            "metadata_dir_force": validated_self.metadata_dir_force,
        }
        # Override user defined values if they were set.
        user_defined_metadata_configs.update(default_metadata_configs)

        # Validate metadata configs without session settings
        validated_gather_configs = GatherMetadataJobSettings.model_validate(
            user_defined_metadata_configs
        )

        # Allow relaxed Session settings so that only job_settings_name and
        # user_settings_config_file need to be set
        if (
            user_defined_session_settings is not None
            and set(
                user_defined_session_settings.get(
                    "job_settings", dict()
                ).keys()
            )
            == {"user_settings_config_file", "job_settings_name"}
            and isinstance(
                user_defined_session_settings["job_settings"][
                    "user_settings_config_file"
                ],
                (str, PurePosixPath),
            )
            and isinstance(
                user_defined_session_settings["job_settings"][
                    "job_settings_name"
                ],
                str,
            )
            and user_defined_session_settings["job_settings"][
                "job_settings_name"
            ]
            in [
                f.model_fields["job_settings_name"].default
                for f in get_args(
                    SessionSettings.model_fields["job_settings"].annotation
                )
            ]
        ):
            session_settings = SessionSettings.model_construct(
                job_settings={
                    "user_settings_config_file": user_defined_session_settings[
                        "job_settings"
                    ]["user_settings_config_file"],
                    "job_settings_name": user_defined_session_settings[
                        "job_settings"
                    ]["job_settings_name"],
                }
            )
            validated_gather_configs.session_settings = session_settings
            validated_self.metadata_configs = validated_gather_configs
        else:
            user_defined_metadata_configs["session_settings"] = (
                user_defined_session_settings
            )
            validated_self.metadata_configs = (
                GatherMetadataJobSettings.model_validate(
                    user_defined_metadata_configs
                )
            )
        validated_self.metadata_configs = (
            validated_self.metadata_configs.model_copy(
                update={"metadata_dir": metadata_dir}, deep=True
            )
        )
        return validated_self


class SubmitJobRequest(BaseSettings):
    """Main request that will be sent to the backend. Bundles jobs into a list
    and allows a user to add an email address to receive notifications."""

    model_config = ConfigDict(use_enum_values=True, extra="allow")

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
    upload_jobs: List[BasicUploadJobConfigs] = Field(
        ...,
        description="List of upload jobs to process. Max of 1000 at a time.",
        min_items=1,
        max_items=1000,
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
