"""Tests for s3_upload_configs module"""

import unittest
from pathlib import PurePosixPath

from aind_data_transfer_models.s3_upload_configs import (
    S3UploadJobConfigs,
    S3UploadSubmitJobRequest,
)


class TestS3UploadSubmitJobRequest(unittest.TestCase):
    """Tests S3UploadSubmitJobRequest class"""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class"""
        example_scratch_configs = S3UploadJobConfigs(
            s3_bucket="scratch",
            user_email="anna.apple@acme.co",
            input_source=(PurePosixPath("dir") / "data_set_2"),
            force_cloud_sync=False,
        )
        example_archive_configs = S3UploadJobConfigs(
            s3_bucket="archive",
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
        self.assertIsNotNone(submit_job_request)


if __name__ == "__main__":
    unittest.main()
