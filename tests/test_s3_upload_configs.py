"""Tests for s3_upload_configs module"""

import unittest
from pathlib import PurePosixPath

from aind_data_transfer_models.s3_upload_configs import (
    S3UploadJobConfigs,
    S3UploadSubmitJobRequest,
)


class TestS3UploadJobConfigs(unittest.TestCase):
    """Tests S3UploadJobConfigs class methods"""

    def test_s3_prefix_pattern(self):
        """Tests s3_prefix is computed correctly."""
        example_scratch_configs = S3UploadJobConfigs(
            s3_bucket="scratch",
            s3_prefix="anna.apple/data_set_2",
            user_email="anna.apple@acme.co",
            input_source=(PurePosixPath("dir") / "data_set_2"),
            force_cloud_sync=False,
        )
        self.assertEqual(
            "anna.apple/data_set_2", example_scratch_configs.s3_prefix
        )


class TestS3UploadSubmitJobRequest(unittest.TestCase):
    """Tests S3UploadSubmitJobRequest class"""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class"""
        example_scratch_configs = S3UploadJobConfigs(
            s3_bucket="scratch",
            s3_prefix="anna.apple/data_set_2",
            user_email="anna.apple@acme.co",
            input_source=(PurePosixPath("dir") / "data_set_2"),
            force_cloud_sync=False,
        )
        example_archive_configs = S3UploadJobConfigs(
            s3_bucket="archive",
            s3_prefix="ephys_project/data_set_2",
            user_email="anna.apple@acme.co",
            input_source=(PurePosixPath("dir") / "data_set_2"),
            force_cloud_sync=False,
        )
        cls.example_scratch_configs = example_scratch_configs
        cls.example_archive_configs = example_archive_configs

    def test_submit_job_request(self):
        """Test submit_job_request"""
        submit_job_request = S3UploadSubmitJobRequest(
            upload_jobs=[
                self.example_scratch_configs,
                self.example_archive_configs,
            ]
        )
        self.assertEqual("s3_upload", submit_job_request.job_type)
        self.assertIsNotNone(submit_job_request)


if __name__ == "__main__":
    unittest.main()
