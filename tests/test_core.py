"""Module to test configs"""

import json
import unittest
from datetime import datetime
from pathlib import PurePosixPath

from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.platforms import Platform
from aind_metadata_mapper.models import (
    ProceduresSettings,
    SubjectSettings,
    JobSettings as GatherMetadataJobSettings,
)
from aind_slurm_rest import V0036JobProperties
from pydantic import ValidationError

from aind_data_transfer_models.core import (
    BasicUploadJobConfigs,
    BucketType,
    EmailNotificationType,
    ModalityConfigs,
    SubmitJobRequest,
)
from aind_data_schema_models.modalities import BehaviorVideos


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
                "modalities": {"__all__": {"output_folder_name"}},
            }
        )

        with self.assertRaises(AttributeError) as e:
            BasicUploadJobConfigs(platform="MISSING", **base_configs)
        self.assertEqual("Unknown Platform: MISSING", e.exception.args[0])

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
            configs.metadata_configs.metadata_dir, configs.metadata_dir
        )
        self.assertEqual(
            configs.metadata_configs.directory_to_write_to, "stage"
        )
        self.assertEqual(
            configs.metadata_configs.raw_data_description_settings.name,
            configs.s3_prefix,
        )
        self.assertEqual(
            configs.metadata_configs.raw_data_description_settings.modality,
            [
                BehaviorVideos(
                    name="Behavior videos", abbreviation="behavior-videos"
                )
            ],
        )
        self.assertIsInstance(
            configs.metadata_configs.procedures_settings, ProceduresSettings
        )
        self.assertIsInstance(
            configs.metadata_configs.subject_settings, SubjectSettings
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
        expected_error_message = (
            "value is not a valid email address: "
            "An email address must have an @-sign."
        )
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


if __name__ == "__main__":
    unittest.main()
