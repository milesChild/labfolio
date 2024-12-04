import boto3
from typing import Optional, BinaryIO, Union
from botocore.exceptions import ClientError
import json
import pandas as pd
import io

class AWSS3():
    """
    Lightweight class for interacting with AWS S3.
    """

    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, bucket_name: str, region: Optional[str] = 'us-east-1') -> None:
        """
        Initializes a connection to AWS S3.
        :param aws_access_key_id: AWS access key ID
        :param aws_secret_access_key: AWS secret access key
        :param bucket_name: Name of the S3 bucket
        :param region: AWS region (defaults to us-east-1)
        """
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region
        )
        self.bucket = bucket_name
        self.__test_connection()

    def __test_connection(self) -> None:
        """Tests the connection to S3 by listing the bucket contents"""
        try:
            self.s3.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
            print(f'Connected to S3 bucket: {self.bucket}')
        except ClientError as e:
            raise Exception(f'Failed to connect to S3: {str(e)}')

    def get_s3_url(self, s3_key: str) -> str:
        """
        Generates the S3 URL for a given key
        :param s3_key: Path of the file in S3
        :return: Full S3 URL
        """
        return f"s3://{self.bucket}/{s3_key}"

    def upload_file(self, file_path: str, s3_key: str) -> Optional[str]:
        """
        Uploads a file to S3
        :param file_path: Local path to the file
        :param s3_key: Destination path in S3
        :return: S3 URL if successful, None otherwise
        """
        try:
            self.s3.upload_file(file_path, self.bucket, s3_key)
            return self.get_s3_url(s3_key)
        except ClientError as e:
            print(f'Error uploading file: {str(e)}')
            return None

    def upload_fileobj(self, file_obj: BinaryIO, s3_key: str) -> Optional[str]:
        """
        Uploads a file-like object to S3
        :param file_obj: File-like object to upload
        :param s3_key: Destination path in S3
        :return: S3 URL if successful, None otherwise
        """
        try:
            # Reset file pointer to beginning
            file_obj.seek(0)
            # Upload the file object
            self.s3.upload_fileobj(file_obj, self.bucket, s3_key)
            return self.get_s3_url(s3_key)
        except ClientError as e:
            print(f'Error uploading file object: {str(e)}')
            return None

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """
        Downloads a file from S3
        :param s3_key: Path of the file in S3
        :param local_path: Local destination path
        :return: True if successful, False otherwise
        """
        try:
            self.s3.download_file(self.bucket, s3_key, local_path)
            return True
        except ClientError as e:
            print(f'Error downloading file: {str(e)}')
            return False

    def read_json(self, s3_key: str) -> Union[dict, list, None]:
        """
        Reads a JSON file from S3
        :param s3_key: Path of the JSON file in S3
        :return: Parsed JSON data or None if error
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except ClientError as e:
            print(f'Error reading JSON: {str(e)}')
            return None

    def read_csv(self, s3_key: str) -> Optional[pd.DataFrame]:
        """
        Reads a CSV file from S3 into a pandas DataFrame
        :param s3_key: Path of the CSV file in S3
        :return: pandas DataFrame or None if error
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            return pd.read_csv(io.BytesIO(response['Body'].read()))
        except ClientError as e:
            print(f'Error reading CSV: {str(e)}')
            return None

    def delete_file(self, s3_key: str) -> bool:
        """
        Deletes a file from S3
        :param s3_key: Path of the file in S3
        :return: True if successful, False otherwise
        """
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError as e:
            print(f'Error deleting file: {str(e)}')
            return False

    def list_files(self, prefix: str = '') -> list:
        """
        Lists files in the S3 bucket
        :param prefix: Optional prefix to filter results
        :return: List of file keys
        """
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except ClientError as e:
            print(f'Error listing files: {str(e)}')
            return []

    def upload_dataframe(self, df: pd.DataFrame, s3_key: str) -> Optional[str]:
        """
        Uploads a pandas DataFrame directly to S3 as CSV
        :param df: pandas DataFrame to upload
        :param s3_key: Destination path in S3
        :return: S3 URL if successful, None otherwise
        """
        try:
            # Convert DataFrame to CSV buffer in memory
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            
            # Convert to bytes buffer
            csv_bytes = io.BytesIO(csv_buffer.getvalue().encode())
            
            # Upload to S3
            self.s3.upload_fileobj(csv_bytes, self.bucket, s3_key)
            return self.get_s3_url(s3_key)
        except ClientError as e:
            print(f'Error uploading DataFrame: {str(e)}')
            return None
        finally:
            csv_buffer.close()
