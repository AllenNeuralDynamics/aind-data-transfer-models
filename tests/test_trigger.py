"""Module to test trigger"""

import unittest
from pydantic import ValidationError

from aind_data_schema_models.modalities import Modality, Ecephys, Fib
from aind_data_transfer_models.trigger import TriggerConfigModel


class TestTriggerConfigModel(unittest.TestCase):
    """Tests TestTriggerConfigModel class"""

    def test_upload_and_run(self):
        """Test default_output_folder_name property"""
        config = TriggerConfigModel(
            job_type="ecephys",
            bucket="my-bucket",
            prefix="ecephys_0000",
            asset_name=None,
            mount=None,
            input_data_asset_id=None,
            input_data_mount=None,
            process_capsule_id=None,
            capsule_version=None,
            results_suffix="processed",
            input_data_asset_name=None,
            output_bucket="some-externa-bucket",
        )
        self.assertEqual(config.job_type, "ecephys")
        self.assertEqual(config.bucket, "my-bucket")
        self.assertEqual(config.prefix, "ecephys_0000")
        self.assertEqual(config.asset_name, "ecephys_0000")
        self.assertEqual(config.mount, "ecephys_0000")

        # passing upload info and input data asset id should fail
        with self.assertRaises(ValueError):
            config = TriggerConfigModel(
                job_type="ecephys",
                bucket="my-bucket",
                prefix="ecephys_0000",
                asset_name=None,
                mount=None,
                input_data_asset_id="0101",
                input_data_mount=None,
                process_capsule_id=None,
                capsule_version=None,
                results_suffix="processed",
            )

    def test_multiple_assets(self):
        """Test default behavior with multiple assets"""
        config = TriggerConfigModel(
            job_type="ecephys",
            input_data_asset_id="0000;0001",
            input_data_mount="mount1;mount2",
            input_data_asset_name="ecephys_session",
        )
        self.assertEqual(config.input_data_asset_id, ["0000", "0001"])
        self.assertEqual(config.input_data_mount, ["mount1", "mount2"])

        # passing multiple assets with only no mount points
        with self.assertRaises(ValueError):
            config = TriggerConfigModel(
                job_type="ecephys",
                input_data_asset_id="0000;0001",
                input_data_mount=None,
                input_data_asset_name="ecephys_session",
            )

        # passing multiple assets with only no input_data_asset_name
        with self.assertRaises(ValueError):
            config = TriggerConfigModel(
                job_type="ecephys",
                input_data_asset_id="0000;0001",
                input_data_mount="mount1;mount2",
            )

        # passing multiple assets with unmatched mount points
        with self.assertRaises(ValueError):
            config = TriggerConfigModel(
                job_type="ecephys",
                input_data_asset_id="0000;0001",
                input_data_mount="mount1;mount2;mount3",
                input_data_asset_name="ecephys_session",
            )

    def test_modalities_parsing(self):
        """Test modalities field"""
        config = TriggerConfigModel(
            job_type="run_generic_pipeline",
            process_capsule_id="0000",
            capsule_version="1.0",
            modalities=["ecephys", "fib"],
        )
        self.assertIsInstance(config.modalities[0], Ecephys)
        self.assertIsInstance(config.modalities[1], Fib)

        config = TriggerConfigModel(
            job_type="run_generic_pipeline",
            process_capsule_id="0000",
            capsule_version="1.0",
            modalities=[Modality.ECEPHYS, Modality.FIB],
        )
        self.assertIsInstance(config.modalities[0], Ecephys)
        self.assertIsInstance(config.modalities[1], Fib)

        # emtpy list will set modality to None
        config = TriggerConfigModel(
            job_type="run_generic_pipeline",
            process_capsule_id="0000",
            capsule_version="1.0",
            modalities=[],
        )
        self.assertEqual(config.modalities, None)

        # wrong modality type
        with self.assertRaises(ValidationError):
            config = TriggerConfigModel(
                job_type="run_generic_pipeline",
                process_capsule_id="0000",
                capsule_version="1.0",
                modalities=[1, 2],
            )

        # wrong modality abbreviation
        with self.assertRaises(KeyError):
            config = TriggerConfigModel(
                job_type="run_generic_pipeline",
                process_capsule_id="0000",
                capsule_version="1.0",
                modalities=["ecpys", "fibb"],
            )

    def test_run_generic_pipeline(self):
        """Test run_generic_pipeline"""
        config = TriggerConfigModel(
            job_type="run_generic_pipeline",
            process_capsule_id="0000",
            capsule_version="1.0",
        )
        self.assertEqual(config.job_type, "run_generic_pipeline")
        self.assertEqual(config.process_capsule_id, "0000")
        self.assertEqual(config.capsule_version, "1.0")

        with self.assertRaises(ValueError):
            config = TriggerConfigModel(
                job_type="run_generic_pipeline",
                process_capsule_id=None,
                capsule_version="1.0",
            )

    def test_legacy_fields(self):
        """Test legacy fields"""
        config = TriggerConfigModel(
            job_type="ecephys",
            input_data_point="0000",
            input_data_mount=None,
            capsule_id="0101",
            process_capsule_id=None,
        )
        assert config.input_data_mount == "0000"
        assert config.process_capsule_id == "0101"
