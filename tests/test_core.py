"""Module to test configs"""

import json
import unittest
from datetime import datetime
from pathlib import PurePosixPath

from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.platforms import Platform
from pydantic import ValidationError

from aind_data_transfer_models.core import (
    BasicUploadJobConfigs,
    BucketType,
    ModalityConfigs,
)


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


class TestBasicUploadJobConfigs(unittest.TestCase):
    """Tests BasicUploadJobConfigs class"""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class"""

        example_configs = BasicUploadJobConfigs(
            processor_full_name="Anna Apple",
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
            metadata_dir=None,
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
        """Tests that an error is raised if an unknown platform is used"""

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


if __name__ == "__main__":
    unittest.main()
