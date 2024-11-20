"""Module to test configs"""

import json
import unittest
from datetime import datetime
from pathlib import Path, PurePosixPath
from unittest.mock import MagicMock, patch

from aind_codeocean_pipeline_monitor.models import PipelineMonitorSettings
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.platforms import Platform
from aind_metadata_mapper.models import BergamoSessionJobSettings
from aind_metadata_mapper.models import (
    JobSettings as GatherMetadataJobSettings,
)
from aind_metadata_mapper.models import (
    ProceduresSettings,
    SessionSettings,
    SubjectSettings,
)
from aind_slurm_rest import V0036JobProperties
from codeocean.computation import RunParams
from codeocean.data_asset import DataAssetParams
from pydantic import ValidationError

from aind_data_transfer_models.core import (
    BasicUploadJobConfigs,
    CodeOceanPipelineMonitorConfigs,
    ModalityConfigs,
    SubmitJobRequest,
)
from aind_data_transfer_models.s3_upload_configs import (
    BucketType,
    EmailNotificationType,
)
from aind_data_transfer_models.trigger import TriggerConfigModel, ValidJobType


class TestModalityConfigs(unittest.TestCase):
    """Tests ModalityConfigs class"""

    def test_default_output_folder_name(self):
        """Test default_output_folder_name property"""
        configs = ModalityConfigs(modality=Modality.ECEPHYS, source="some_dir")
        self.assertEqual("ecephys", configs.output_folder_name)

    def test_parse_modality_string(self):
        """Test parse_modality_string method"""
        configs = ModalityConfigs(modality="ecephys", source="some_dir")
        self.assertEqual(Modality.ECEPHYS, configs.modality)

    def test_parse_modality_string_error(self):
        """Test parse_modality_string method raises error"""

        with self.assertRaises(AttributeError) as e:
            ModalityConfigs(modality="abcdef", source="some_dir")

        self.assertEqual("Unknown Modality: abcdef", e.exception.args[0])

    def test_get_compress_source_default(self):
        """Test get_compress_source_default method"""

        # Check ecephys default is true
        configs1 = ModalityConfigs(modality=Modality.ECEPHYS, source="dir1")

        # Check other default
        configs2 = ModalityConfigs(modality=Modality.FIB, source="dir2")

        # Check custom
        configs3 = ModalityConfigs(
            modality=Modality.FIB, source="dir2", compress_raw_data=True
        )

        self.assertTrue(configs1.compress_raw_data)
        self.assertFalse(configs2.compress_raw_data)
        self.assertTrue(configs3.compress_raw_data)

    def test_slurm_settings(self):
        """Tests slurm settings"""

        slurm_settings_for_ephys_modality = V0036JobProperties(
            # "environment" is a required field, but will be created by a
            # downstream process if blank here
            environment=dict(),
            memory_per_cpu=8000,
            tasks=1,
            time_limit=720,
            nodes=[1, 1],
            minimum_cpus_per_node=16,
        )

        configs = ModalityConfigs(
            modality=Modality.ECEPHYS,
            source="some_dir",
            slurm_settings=slurm_settings_for_ephys_modality,
        )

        self.assertEqual(8000, configs.slurm_settings.memory_per_cpu)
        self.assertEqual(1, configs.slurm_settings.tasks)
        self.assertEqual(720, configs.slurm_settings.time_limit)
        self.assertEqual([1, 1], configs.slurm_settings.nodes)
        self.assertEqual(16, configs.slurm_settings.minimum_cpus_per_node)

    def test_round_trip(self):
        """Tests model can be deserialized easily"""

        configs = ModalityConfigs(modality=Modality.ECEPHYS, source="dir1")
        model_json = configs.model_dump_json()
        deserialized_model = ModalityConfigs.model_validate_json(model_json)
        self.assertEqual(configs, deserialized_model)

    def test_deserialization_fails(self):
        """Tests deserialization fails when computed field is incorrect"""

        corrupt_json = json.dumps(
            {
                "modality": {
                    "name": "Extracellular electrophysiology",
                    "abbreviation": "ecephys",
                },
                "source": "dir1",
                "compress_raw_data": True,
                "output_folder_name": "incorrect",
            }
        )
        with self.assertRaises(ValidationError) as e:
            ModalityConfigs.model_validate_json(corrupt_json)
        errors = json.loads(e.exception.json())
        expected_msg = (
            "Value error, output_folder_name incorrect doesn't match ecephys!"
        )
        self.assertEqual(1, len(errors))
        self.assertEqual(expected_msg, errors[0]["msg"])

    def test_extra_allow(self):
        """Tests that extra fields can be passed into model."""
        config = ModalityConfigs(
            modality=Modality.ECEPHYS,
            source="some_dir",
            extra_field_1="an extra field",
        )
        config_json = config.model_dump_json()
        self.assertEqual(
            config, ModalityConfigs.model_validate_json(config_json)
        )

    def test_extra_configs_error(self):
        """Tests validation error raised if user sets both extra_configs and
        job_settings fields."""

        with self.assertRaises(ValidationError) as e:
            ModalityConfigs(
                modality=Modality.ECEPHYS,
                source="some_dir",
                extra_configs="some_dir",
                job_settings={"param1": 3, "param2": "abc"},
            )
        errors = e.exception.errors()
        self.assertEqual(1, len(errors))
        self.assertEqual(
            "Value error, Only job_settings or "
            "extra_configs should be set!",
            errors[0]["msg"],
        )

    def test_extra_configs_json_error(self):
        """Tests validation error raised if passes in dictionary that is not
        json serializable."""

        with self.assertRaises(ValidationError) as e:
            ModalityConfigs(
                modality=Modality.ECEPHYS,
                source="some_dir",
                job_settings={"param1": list},
            )
        expected_error_message_snippet = (
            "Value error, job_settings must be json serializable!"
        )
        errors = e.exception.errors()
        self.assertEqual(1, len(errors))
        self.assertTrue(expected_error_message_snippet in errors[0]["msg"])


class TestCodeOceanPipelineMonitorConfigs(unittest.TestCase):
    """Tests CodeOceanPipelineMonitorConfigs class"""

    def test_basic_class(self):
        """Tests basic class serialization round trip"""
        codeocean_configs = CodeOceanPipelineMonitorConfigs(
            pipeline_monitor_capsule_settings=[
                PipelineMonitorSettings(
                    run_params=RunParams(
                        pipeline_id="123-abc", parameters=["param1", "param2"]
                    )
                )
            ],
            register_data_settings=DataAssetParams(
                name="custom_name",
                mount="custom_mount",
                tags=["custom1", "custom2"],
            ),
        )
        expected_json = {
            "pipeline_monitor_capsule_settings": [
                {
                    "run_params": {
                        "pipeline_id": "123-abc",
                        "parameters": ["param1", "param2"],
                    }
                }
            ],
            "register_data_settings": {
                "name": "custom_name",
                "tags": ["custom1", "custom2"],
                "mount": "custom_mount",
            },
        }
        expected_deser_model = (
            CodeOceanPipelineMonitorConfigs.model_validate_json(
                json.dumps(expected_json)
            )
        )
        self.assertEqual(codeocean_configs, expected_deser_model)

    def test_validator(self):
        """Tests that users cannot set more than 10 tags."""

        tags = [f"a_{x}" for x in range(11)]
        with self.assertRaises(ValidationError) as e:
            CodeOceanPipelineMonitorConfigs(
                pipeline_monitor_capsule_settings=[],
                register_data_settings=DataAssetParams(
                    name="custom_name",
                    mount="custom_mount",
                    tags=tags,
                ),
            )
        errors = json.loads(e.exception.json())
        self.assertEqual(1, len(errors))
        self.assertEqual(
            "Value error, Tags can only have a max of 10 items!",
            errors[0]["msg"],
        )


class TestBasicUploadJobConfigs(unittest.TestCase):
    """Tests BasicUploadJobConfigs class"""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class"""
        example_configs = BasicUploadJobConfigs(
            project_name="Behavior Platform",
            s3_bucket="some_bucket2",
            platform=Platform.BEHAVIOR,
            modalities=[
                ModalityConfigs(
                    modality=Modality.BEHAVIOR_VIDEOS,
                    source=(PurePosixPath("dir") / "data_set_2"),
                ),
            ],
            subject_id="123456",
            acq_datetime=datetime(2020, 10, 13, 13, 10, 10),
            metadata_dir="/some/metadata/dir/",
            metadata_dir_force=False,
            force_cloud_sync=False,
        )
        cls.example_configs = example_configs
        cls.base_configs = example_configs.model_dump(
            exclude={
                "s3_bucket": True,
                "acq_datetime": True,
                "s3_prefix": True,
                "modalities": {"__all__": {"output_folder_name"}},
                "metadata_configs": True,
            }
        )

    def test_s3_prefix(self):
        """Test s3_prefix property"""

        self.assertEqual(
            "behavior_123456_2020-10-13_13-10-10",
            self.example_configs.s3_prefix,
        )

    def test_map_bucket(self):
        """Test map_bucket method"""
        open_configs = BasicUploadJobConfigs(
            s3_bucket="open",
            acq_datetime=datetime(2020, 10, 13, 13, 10, 10),
            **self.base_configs,
        )
        base_configs = open_configs.model_dump(
            exclude={
                "s3_bucket": True,
                "s3_prefix": True,
                "metadata_configs": True,
                "modalities": {"__all__": {"output_folder_name"}},
            }
        )
        scratch_configs = BasicUploadJobConfigs(
            s3_bucket="scratch", **base_configs
        )
        private_configs1 = BasicUploadJobConfigs(
            s3_bucket="private", **base_configs
        )
        private_configs2 = BasicUploadJobConfigs(
            s3_bucket="custom", **base_configs
        )
        private_configs3 = BasicUploadJobConfigs(
            s3_bucket=BucketType.PRIVATE, **base_configs
        )

        self.assertEqual(BucketType.OPEN, open_configs.s3_bucket)
        self.assertEqual(BucketType.SCRATCH, scratch_configs.s3_bucket)
        self.assertEqual(BucketType.PRIVATE, private_configs1.s3_bucket)
        self.assertEqual(BucketType.PRIVATE, private_configs2.s3_bucket)
        self.assertEqual(BucketType.PRIVATE, private_configs3.s3_bucket)

    def test_parse_datetime(self):
        """Test parse_datetime method"""

        configs1 = BasicUploadJobConfigs(
            s3_bucket="open",
            acq_datetime="2020-05-23T09:05:03",
            **self.base_configs,
        )
        configs2 = BasicUploadJobConfigs(
            s3_bucket="open",
            acq_datetime="05/23/2020 09:05:03 AM",
            **self.base_configs,
        )
        self.assertEqual(datetime(2020, 5, 23, 9, 5, 3), configs1.acq_datetime)
        self.assertEqual(datetime(2020, 5, 23, 9, 5, 3), configs2.acq_datetime)

    def test_parse_datetime_error(self):
        """Test parse_datetime method raises error"""

        with self.assertRaises(ValidationError) as e:
            BasicUploadJobConfigs(
                s3_bucket="open",
                acq_datetime="2020/05/23T09:05:03",
                **self.base_configs,
            )
        error_msg = json.loads(e.exception.json())[0]["msg"]
        self.assertTrue("Value error, Incorrect datetime format" in error_msg)

    def test_parse_platform_string(self):
        """Tests platform can be parsed from string"""

        base_configs = self.example_configs.model_dump(
            exclude={
                "platform": True,
                "s3_prefix": True,
                "metadata_configs": True,
                "modalities": {"__all__": {"output_folder_name"}},
            }
        )
        configs = BasicUploadJobConfigs(platform="behavior", **base_configs)
        self.assertEqual(Platform.BEHAVIOR, configs.platform)

    def test_parse_platform_string_error(self):
        """Tests that an error is raised if an unknown platform is used"""

        base_configs = self.example_configs.model_dump(
            exclude={
                "platform": True,
                "s3_prefix": True,
                "metadata_configs": True,
                "modalities": {"__all__": {"output_folder_name"}},
            }
        )

        with self.assertRaises(AttributeError) as e:
            BasicUploadJobConfigs(platform="MISSING", **base_configs)
        self.assertEqual("Unknown Platform: MISSING", e.exception.args[0])

    def test_get_job_type(self):
        """Tests _get_job_type for several situations."""

        self.assertEqual(
            ValidJobType.ECEPHYS,
            BasicUploadJobConfigs._get_job_type(platform=Platform.ECEPHYS),
        )
        self.assertEqual(
            ValidJobType.SMARTSPIM,
            BasicUploadJobConfigs._get_job_type(platform=Platform.SMARTSPIM),
        )
        self.assertEqual(
            ValidJobType.SINGLEPLANE_OPHYS,
            BasicUploadJobConfigs._get_job_type(
                platform=Platform.SINGLE_PLANE_OPHYS
            ),
        )
        self.assertEqual(
            ValidJobType.MULTIPLANE_OPHYS,
            BasicUploadJobConfigs._get_job_type(
                platform=Platform.MULTIPLANE_OPHYS
            ),
        )
        self.assertEqual(
            ValidJobType.REGISTER_DATA,
            BasicUploadJobConfigs._get_job_type(platform=Platform.BEHAVIOR),
        )

    def test_set_trigger_capsule_configs_defaults(self):
        """Tests set_trigger_capsule_configs sets default values for
        trigger_capsule_configs."""
        expected_configs = TriggerConfigModel(
            job_type=ValidJobType.REGISTER_DATA,
            bucket="private",
            prefix="behavior_123456_2020-10-13_13-10-10",
            asset_name="behavior_123456_2020-10-13_13-10-10",
            mount="behavior_123456_2020-10-13_13-10-10",
            results_suffix="processed",
            modalities=[m.modality for m in self.example_configs.modalities],
        )
        self.assertEqual(
            expected_configs, self.example_configs.trigger_capsule_configs
        )

    def test_set_trigger_capsule_configs_user_defined(self):
        """Tests set_trigger_capsule_configs values when user defines their
        own settings."""
        user_configs = TriggerConfigModel(
            job_type=ValidJobType.RUN_GENERIC_PIPELINE,
            process_capsule_id="abc-123",
            bucket="should_be_overwritten",
            prefix="should_be_overwritten",
            asset_name="should_be_overwritten",
            mount="custom_mount",
            results_suffix="custom-suffix",
        )
        base_configs = self.example_configs.model_dump(
            exclude={
                "s3_prefix": True,
                "modalities": {"__all__": {"output_folder_name"}},
                "metadata_configs": True,
                "trigger_capsule_configs": True,
            }
        )
        configs = BasicUploadJobConfigs(
            trigger_capsule_configs=user_configs, **base_configs
        )

        expected_configs = TriggerConfigModel(
            job_type=ValidJobType.RUN_GENERIC_PIPELINE,
            bucket="private",
            prefix="behavior_123456_2020-10-13_13-10-10",
            asset_name="behavior_123456_2020-10-13_13-10-10",
            mount="custom_mount",
            process_capsule_id="abc-123",
            results_suffix="custom-suffix",
            modalities=[m.modality for m in self.example_configs.modalities],
        )
        self.assertEqual(expected_configs, configs.trigger_capsule_configs)

    @patch("logging.warning")
    def test_set_trigger_capsule_configs_user_defined_error(
        self, mock_warn: MagicMock
    ):
        """Tests set_trigger_capsule_configs values when user defines their
        own settings and an error is raised when user sets both trigger
        configs and process_capsule_id."""
        user_configs = TriggerConfigModel(
            job_type=ValidJobType.RUN_GENERIC_PIPELINE,
            process_capsule_id="abc-123",
            bucket="should_be_overwritten",
            prefix="should_be_overwritten",
            asset_name="should_be_overwritten",
            mount="custom_mount",
            results_suffix="custom-suffix",
        )
        base_configs = self.example_configs.model_dump(
            exclude={
                "s3_prefix": True,
                "modalities": {"__all__": {"output_folder_name"}},
                "metadata_configs": True,
                "trigger_capsule_configs": True,
                "process_capsule_id": True,
            }
        )
        _ = BasicUploadJobConfigs(
            trigger_capsule_configs=user_configs,
            **base_configs,
            process_capsule_id="def-456",
        )
        mock_warn.assert_called_once_with(
            "Only one of trigger_capsule_configs or legacy "
            "process_capsule_id should be set!"
        )

    def test_set_trigger_capsule_configs_user_defined_process_id(self):
        """Tests set_trigger_capsule_configs values when user defines their
        own settings and legacy process capsule id."""
        base_configs = self.example_configs.model_dump(
            exclude={
                "s3_prefix": True,
                "modalities": {"__all__": {"output_folder_name"}},
                "metadata_configs": True,
                "trigger_capsule_configs": True,
                "process_capsule_id": True,
            }
        )
        configs = BasicUploadJobConfigs(
            **base_configs, process_capsule_id="def-456"
        )
        expected_trigger_configs = TriggerConfigModel(
            job_type=ValidJobType.RUN_GENERIC_PIPELINE,
            bucket="private",
            prefix="behavior_123456_2020-10-13_13-10-10",
            asset_name="behavior_123456_2020-10-13_13-10-10",
            mount="behavior_123456_2020-10-13_13-10-10",
            results_suffix="processed",
            process_capsule_id="def-456",
            modalities=[Modality.BEHAVIOR_VIDEOS],
        )
        self.assertEqual(
            expected_trigger_configs, configs.trigger_capsule_configs
        )

    def test_fill_in_metadata_configs(self):
        """Tests that metadata jobSettings are filled in as expected"""
        metadata_configs = GatherMetadataJobSettings(
            directory_to_write_to="/some/path/",
        )
        base_configs = self.example_configs.model_dump(
            exclude={
                "s3_prefix": True,
                "modalities": {"__all__": {"output_folder_name"}},
                "metadata_configs": True,
            }
        )
        configs = BasicUploadJobConfigs(
            metadata_configs=metadata_configs, **base_configs
        )
        self.assertEqual(
            configs.metadata_configs.metadata_dir,
            configs.metadata_dir.as_posix(),
        )
        self.assertEqual(
            configs.metadata_configs.metadata_dir_force,
            configs.metadata_dir_force,
        )
        self.assertEqual(
            configs.metadata_configs.directory_to_write_to, Path("stage")
        )
        self.assertEqual(
            configs.metadata_configs.raw_data_description_settings.name,
            configs.s3_prefix,
        )
        self.assertEqual(
            configs.metadata_configs.raw_data_description_settings.modality,
            [Modality.BEHAVIOR_VIDEOS],
        )
        self.assertIsInstance(
            configs.metadata_configs.procedures_settings, ProceduresSettings
        )
        self.assertIsInstance(
            configs.metadata_configs.subject_settings, SubjectSettings
        )

    def test_fill_in_metadata_configs_with_session(self):
        """Tests fill_in_metadata_configs with user defined session"""
        session_settings = SessionSettings(
            job_settings=BergamoSessionJobSettings(
                input_source="some_directory",
                experimenter_full_name=["John Apple"],
                subject_id="12345",
                imaging_laser_wavelength=560,
                fov_imaging_depth=120,
                fov_targeted_structure="Bregma",
                notes=None,
            )
        )

        gather_metadata_settings = GatherMetadataJobSettings(
            directory_to_write_to="stage", session_settings=session_settings
        )
        configs = BasicUploadJobConfigs(
            metadata_configs=gather_metadata_settings,
            acq_datetime=datetime(2020, 10, 13, 13, 10, 10),
            **self.base_configs,
        )
        self.assertEqual(
            session_settings, configs.metadata_configs.session_settings
        )

    def test_fill_in_metadata_configs_relaxed_session(self):
        """Tests fill_in_metadata_configs allows for relaxed session
        validation"""

        gather_metadata_settings = {
            "session_settings": {
                "job_settings": {
                    "user_settings_config_file": "session_settings.json",
                    "job_settings_name": "Bergamo",
                }
            }
        }
        configs = BasicUploadJobConfigs(
            metadata_configs=gather_metadata_settings,
            acq_datetime=datetime(2020, 10, 13, 13, 10, 10),
            **self.base_configs,
        )
        model_json = json.loads(
            configs.model_dump_json(warnings=False, exclude_none=True)
        )
        self.assertEqual(
            gather_metadata_settings["session_settings"],
            model_json["metadata_configs"]["session_settings"],
        )

    def test_round_trip(self):
        """Tests model can be serialized and de-serialized easily"""
        model_json = self.example_configs.model_dump_json()
        deserialized = BasicUploadJobConfigs.model_validate_json(model_json)
        self.assertEqual(self.example_configs, deserialized)

    def test_deserialization_fail(self):
        """Tests deserialization fails with incorrect computed field"""
        corrupt_json = json.dumps(
            {
                "project_name": "Behavior Platform",
                "s3_bucket": "private",
                "platform": {
                    "name": "Behavior platform",
                    "abbreviation": "behavior",
                },
                "modalities": [
                    {
                        "modality": {
                            "name": "Behavior videos",
                            "abbreviation": "behavior-videos",
                        },
                        "source": "dir/data_set_2",
                        "output_folder_name": "behavior-videos",
                    }
                ],
                "subject_id": "123456",
                "acq_datetime": "2020-10-13T13:10:10",
                "metadata_dir": "/some/metadata/dir",
                "s3_prefix": "incorrect",
            }
        )
        with self.assertRaises(ValidationError) as e:
            BasicUploadJobConfigs.model_validate_json(corrupt_json)
        errors = json.loads(e.exception.json())
        expected_msg = (
            "Value error, s3_prefix incorrect doesn't match computed "
            "behavior_123456_2020-10-13_13-10-10!"
        )
        self.assertEqual(1, len(errors))
        self.assertEqual(expected_msg, errors[0]["msg"])

    def test_set_codeocean_configs(self):
        """Tests that the codeocean defaults are set."""
        expected_codeocean_configs = {
            "job_type": "behavior",
            "register_data_settings": {
                "name": "behavior_123456_2020-10-13_13-10-10",
                "tags": ["123456", "behavior", "raw"],
                "mount": "behavior_123456_2020-10-13_13-10-10",
                "source": {
                    "aws": {
                        "bucket": "private",
                        "prefix": "behavior_123456_2020-10-13_13-10-10",
                        "keep_on_external_storage": True,
                        "public": False,
                    }
                },
                "custom_metadata": {
                    "data level": "raw",
                    "experiment type": "behavior",
                    "subject id": "123456",
                },
            },
        }

        self.assertEqual(
            CodeOceanPipelineMonitorConfigs.model_validate_json(
                json.dumps(expected_codeocean_configs)
            ),
            self.example_configs.codeocean_configs,
        )

    def test_set_codeocean_configs_override(self):
        """Tests that the codeocean defaults are set with custom settings."""

        example_configs = BasicUploadJobConfigs(
            project_name="Behavior Platform",
            s3_bucket="open",
            platform=Platform.BEHAVIOR,
            modalities=[
                ModalityConfigs(
                    modality=Modality.BEHAVIOR_VIDEOS,
                    source=(PurePosixPath("dir") / "data_set_2"),
                ),
            ],
            subject_id="123456",
            acq_datetime=datetime(2020, 10, 13, 13, 10, 10),
            codeocean_configs=CodeOceanPipelineMonitorConfigs(
                register_data_settings=DataAssetParams(
                    name="custom_name",
                    mount="custom_mount",
                    tags=list(),
                    custom_metadata=dict(),
                )
            ),
        )

        expected_codeocean_configs = {
            "job_type": "behavior",
            "register_data_settings": {
                "name": "custom_name",
                "tags": ["123456", "behavior"],
                "mount": "custom_mount",
                "source": {
                    "aws": {
                        "bucket": "open",
                        "prefix": "behavior_123456_2020-10-13_13-10-10",
                        "keep_on_external_storage": True,
                        "public": True,
                    }
                },
                "custom_metadata": {
                    "experiment type": "behavior",
                    "subject id": "123456",
                },
            },
        }
        self.assertEqual(
            CodeOceanPipelineMonitorConfigs.model_validate_json(
                json.dumps(expected_codeocean_configs)
            ),
            example_configs.codeocean_configs,
        )


class TestSubmitJobRequest(unittest.TestCase):
    """Tests SubmitJobRequest class"""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up example configs to be used in tests"""

        example_upload_config = BasicUploadJobConfigs(
            project_name="Behavior Platform",
            s3_bucket="some_bucket2",
            platform=Platform.BEHAVIOR,
            modalities=[
                ModalityConfigs(
                    modality=Modality.BEHAVIOR_VIDEOS,
                    source=(PurePosixPath("dir") / "data_set_2"),
                ),
            ],
            subject_id="123456",
            acq_datetime=datetime(2020, 10, 13, 13, 10, 10),
        )
        cls.example_upload_config = example_upload_config

    def test_min_items(self):
        """Tests error is raised if no job list is empty"""

        with self.assertRaises(ValidationError) as e:
            SubmitJobRequest(upload_jobs=[])
        expected_message = (
            "List should have at least 1 item after validation, not 0"
        )
        actual_message = json.loads(e.exception.json())[0]["msg"]
        self.assertEqual(1, len(json.loads(e.exception.json())))
        self.assertEqual(expected_message, actual_message)

    def test_max_items(self):
        """Tests error is raised if job list is greater than maximum allowed"""

        upload_job = BasicUploadJobConfigs(
            **self.example_upload_config.model_dump(round_trip=True)
        )

        with self.assertRaises(ValidationError) as e:
            SubmitJobRequest(upload_jobs=[upload_job for _ in range(0, 1001)])
        expected_message = (
            "List should have at most 1000 items after validation, not 1001"
        )
        actual_message = json.loads(e.exception.json())[0]["msg"]
        self.assertEqual(1, len(json.loads(e.exception.json())))
        self.assertEqual(expected_message, actual_message)

    def test_default_settings(self):
        """Tests defaults are set correctly."""

        upload_job = BasicUploadJobConfigs(
            **self.example_upload_config.model_dump(round_trip=True)
        )

        job_settings = SubmitJobRequest(upload_jobs=[upload_job])
        self.assertIsNone(job_settings.user_email)
        self.assertEqual(
            {EmailNotificationType.FAIL}, job_settings.email_notification_types
        )
        self.assertEqual("transform_and_upload", job_settings.job_type)

    def test_non_default_settings(self):
        """Tests user can modify the settings."""
        upload_job_configs = self.example_upload_config.model_dump(
            round_trip=True
        )

        job_settings = SubmitJobRequest(
            user_email="abc@acme.com",
            email_notification_types={
                EmailNotificationType.BEGIN,
                EmailNotificationType.FAIL,
            },
            upload_jobs=[BasicUploadJobConfigs(**upload_job_configs)],
        )
        self.assertEqual("abc@acme.com", job_settings.user_email)
        self.assertEqual(
            {EmailNotificationType.BEGIN, EmailNotificationType.FAIL},
            job_settings.email_notification_types,
        )

    def test_email_validation(self):
        """Tests user can not input invalid email address."""

        upload_job_configs = self.example_upload_config.model_dump(
            round_trip=True
        )
        with self.assertRaises(ValidationError) as e:
            SubmitJobRequest(
                user_email="some user",
                upload_jobs=[BasicUploadJobConfigs(**upload_job_configs)],
            )
        # email_validator changed error message across versions. We can just
        # do a quick check that the error message at least contains this part.
        expected_error_message = "value is not a valid email address: "
        actual_error_message = json.loads(e.exception.json())[0]["msg"]
        # Check only 1 validation error is raised
        self.assertEqual(1, len(json.loads(e.exception.json())))
        self.assertIn(expected_error_message, actual_error_message)

    def test_propagate_email_settings(self):
        """Tests global email settings is propagated to individual jobs."""

        example_job_configs = self.example_upload_config.model_dump(
            exclude={"user_email", "email_notification_types"}, round_trip=True
        )
        new_job = BasicUploadJobConfigs(
            user_email="xyz@acme.org",
            email_notification_types=[EmailNotificationType.ALL],
            **example_job_configs,
        )
        job_settings = SubmitJobRequest(
            user_email="abc@acme.org",
            email_notification_types={
                EmailNotificationType.BEGIN,
                EmailNotificationType.FAIL,
            },
            upload_jobs=[
                new_job,
                BasicUploadJobConfigs(**example_job_configs),
            ],
        )

        self.assertEqual(
            "xyz@acme.org", job_settings.upload_jobs[0].user_email
        )
        self.assertEqual(
            "abc@acme.org", job_settings.upload_jobs[1].user_email
        )
        self.assertEqual(
            {"all"}, job_settings.upload_jobs[0].email_notification_types
        )
        self.assertEqual(
            {"begin", "fail"},
            job_settings.upload_jobs[1].email_notification_types,
        )

    def test_institution_setting(self):
        """Tests that users can set the institution in the metadata configs."""
        metadata_configs = {
            "raw_data_description_settings": {"institution": Organization.AIBS}
        }
        config = BasicUploadJobConfigs(
            project_name="some project",
            platform=Platform.ECEPHYS,
            modalities=[
                ModalityConfigs(modality=Modality.ECEPHYS, source="some_dir")
            ],
            subject_id="123456",
            acq_datetime=datetime(2020, 1, 2, 3, 4, 5),
            metadata_configs=metadata_configs,
        )
        self.assertEqual(
            Organization.AIBS,
            config.metadata_configs.raw_data_description_settings.institution,
        )

    def test_extra_allow(self):
        """Tests that extra fields can be passed into model."""
        config = BasicUploadJobConfigs(
            project_name="some project",
            platform=Platform.ECEPHYS,
            modalities=[
                ModalityConfigs(modality=Modality.ECEPHYS, source="some_dir")
            ],
            subject_id="123456",
            acq_datetime=datetime(2020, 1, 2, 3, 4, 5),
            extra_field_1="an extra field",
        )
        config_json = config.model_dump_json()
        self.assertEqual(
            config, BasicUploadJobConfigs.model_validate_json(config_json)
        )

    def test_codeocean_configs(self):
        """Tests user defined codeocean_configs"""
        codeocean_configs = CodeOceanPipelineMonitorConfigs(
            pipeline_monitor_capsule_settings=[
                PipelineMonitorSettings(
                    run_params=RunParams(
                        pipeline_id="123-abc", parameters=["param1", "param2"]
                    )
                )
            ],
            additional_raw_data_tags=["custom1", "custom2"],
            raw_data_mount="custom_mount",
        )
        config = BasicUploadJobConfigs(
            project_name="some project",
            platform=Platform.ECEPHYS,
            modalities=[
                ModalityConfigs(modality=Modality.ECEPHYS, source="some_dir")
            ],
            subject_id="123456",
            acq_datetime=datetime(2020, 1, 2, 3, 4, 5),
            codeocean_configs=codeocean_configs,
        )

        config_json = config.model_dump_json(exclude_none=True)
        deser_model = BasicUploadJobConfigs.model_validate_json(config_json)
        self.assertEqual(config, deser_model)

    def test_map_legacy_params(self):
        """Tests legacy fields are mapped to CodeOcean configs."""
        config = BasicUploadJobConfigs(
            project_name="some project",
            platform=Platform.ECEPHYS,
            modalities=[
                ModalityConfigs(modality=Modality.ECEPHYS, source="some_dir")
            ],
            subject_id="123456",
            acq_datetime=datetime(2020, 1, 2, 3, 4, 5),
            input_data_mount="ecephys_opto",
            process_capsule_id="123-def",
        )
        expected_model = {
            "run_params": {
                "capsule_id": "123-def",
                "data_assets": [{"id": "", "mount": "ecephys_opto"}],
            },
            "capture_settings": {
                "tags": ["derived", "123456", "ecephys"],
                "custom_metadata": {
                    "experiment type": "ecephys",
                    "subject id": "123456",
                    "data level": "derived",
                },
            },
        }
        self.assertEqual(
            [
                PipelineMonitorSettings.model_validate_json(
                    json.dumps(expected_model)
                )
            ],
            config.codeocean_configs.pipeline_monitor_capsule_settings,
        )


if __name__ == "__main__":
    unittest.main()
