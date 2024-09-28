"""Models for aind-trigger-capsule"""

from enum import Enum
from typing import List, Optional, Union

from aind_data_schema_models.modalities import Modality
from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings
from typing_extensions import Self


class ValidJobType(str, Enum):
    """Valid job types for the AIND Trigger Capsule."""

    ECEPHYS = "ecephys"
    ECEPHYS_OPTO = "ecephys_opto"
    SINGLEPLANE_OPHYS = "singleplane_ophys"
    MULTIPLANE_OPHYS = "multiplane_ophys"
    SMARTSPIM = "smartspim"
    RUN_GENERIC_PIPELINE = "run_generic_pipeline"
    REGISTER_DATA = "register_data"
    TEST = "test"


class TriggerConfigModel(BaseSettings):
    """Config to be parsed by the AIND Trigger Capsule."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    job_type: ValidJobType = Field(
        description="The type of job to be triggered.",
    )
    bucket: Optional[str] = Field(
        description="The bucket where the data is stored.",
        default=None,
    )
    prefix: Optional[str] = Field(
        description="The prefix where the data is stored.",
        default=None,
    )
    asset_name: Optional[str] = Field(
        description="The name of the asset.",
        default=None,
    )
    mount: Optional[str] = Field(
        description="The mount point for the data.",
        default=None,
    )
    input_data_asset_id: Optional[Union[str, List[str]]] = Field(
        description=(
            "The ID of the input data asset. To attach multiple "
            "input data assets, use semicolon as a delimiter."
        ),
        default=None,
    )
    input_data_mount: Optional[Union[str, List[str]]] = Field(
        description=(
            "The mount point for the input data. If None, the input data "
            "mount will be the same as the data asset name. For multiple "
            "input data assets, use semicolon as a delimiter to specify "
            "the mount path for each input data asset."
        ),
        default=None,
    )
    process_capsule_id: Optional[str] = Field(
        description=(
            "The ID of the process capsule. Ignored if job type is "
            "run_generic_pipeline."
        ),
        default=None,
    )
    capsule_version: Optional[str] = Field(
        description="The version of the capsule.",
        default=None,
    )
    results_suffix: Optional[str] = Field(
        description="The suffix to be added to the results.",
        default="processed",
    )
    input_data_asset_name: Optional[str] = Field(
        description=(
            "The name to use as stem for the captured asset. It is required "
            "when multiple input data assets are attached."
        ),
        default=None,
    )
    output_bucket: Optional[str] = Field(
        description="The bucket where the results will be stored.",
        default=None,
    )
    # From legacy aind data transfer service
    aind_data_transfer_version: Optional[str] = Field(
        description=(
            "(deprecated) The version of the AIND Data Transfer Library."
        ),
        default=None,
    )
    modalities: Optional[List[Modality.ONE_OF]] = Field(
        description="(deprecated - use 'job_type').",
        default=None,
    )
    capsule_id: Optional[str] = Field(
        description=(
            "(deprecated - use 'process_capsule_id'). "
            "The ID of the process capsule"
        ),
        default=None,
    )
    input_data_point: Optional[str] = Field(
        description=(
            "(deprecated - use 'input_data_mount'). " "The input data point."
        ),
        default=None,
    )

    @field_validator("modalities", mode="before")
    def validate_modalities(
        cls, modalities_before
    ) -> Union[List[Modality.ONE_OF], None]:
        """Convert str modalities to Modality objects."""
        if isinstance(modalities_before, list) and len(modalities_before) == 0:
            return None
        elif isinstance(modalities_before, list) and isinstance(
            modalities_before[0], str
        ):
            return [
                Modality.from_abbreviation(modality)
                for modality in modalities_before
            ]
        else:
            return modalities_before

    @model_validator(mode="after")
    def validate_trigger_config(self) -> Self:
        """Validate the trigger config."""
        # registration
        if (
            self.bucket is not None
            and self.prefix is not None
            and self.input_data_asset_id is not None
        ):
            raise ValueError(
                "If bucket and prefix are provided, input_data_asset_id "
                "should not be provided."
            )
        self.asset_name = (
            self.prefix if self.asset_name is None else self.asset_name
        )
        self.mount = self.prefix if self.mount is None else self.mount

        # legacy aind data transfer service
        if self.input_data_point is not None and self.input_data_mount is None:
            self.input_data_mount = self.input_data_point
        if self.capsule_id is not None and self.process_capsule_id is None:
            self.process_capsule_id = self.capsule_id

        # input data asset ids, mounts, and names
        if (
            self.input_data_asset_id is not None
            and isinstance(self.input_data_asset_id, str)
            and ";" in self.input_data_asset_id
        ):
            self.input_data_asset_id = self.input_data_asset_id.split(";")
        if (
            self.input_data_asset_id is not None
            and self.input_data_mount is not None
            and ";" in self.input_data_mount
        ):
            self.input_data_mount = self.input_data_mount.split(";")
        if (
            self.input_data_asset_id is not None
            and isinstance(self.input_data_asset_id, list)
            and not isinstance(self.input_data_mount, list)
        ):
            raise ValueError(
                "input_data_mount should be a list if "
                "input_data_asset_id is a list."
            )
        if (
            self.input_data_asset_id is not None
            and isinstance(self.input_data_asset_id, list)
            and len(self.input_data_asset_id) != len(self.input_data_mount)
        ):
            raise ValueError(
                "input_data_asset_id and input_data_mount should "
                "have the same length when multiple input data "
                "assets are attached."
            )
        if (
            self.input_data_asset_id is not None
            and isinstance(self.input_data_asset_id, list)
            and self.input_data_asset_name is None
        ):
            raise ValueError(
                "input_data_asset_name is required when multiple "
                "input data assets are attached."
            )

        # generic pipeline
        if (
            self.job_type == ValidJobType.RUN_GENERIC_PIPELINE
            and self.process_capsule_id is None
        ):
            raise ValueError(
                "process_capsule_id is required for job type "
                "run_generic_pipeline."
            )
        return self
