import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import boto3
from moto import mock_dynamodb
from token_storage import LocalFileTokenStorage
from storage_dynamodb import DynamoDBStorage


class TestLocalFileTokenStorage:
    """Test cases for LocalFileTokenStorage"""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test storage initialization"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            storage = LocalFileTokenStorage(temp_file)
            assert storage.file_path == Path(temp_file)
            assert temp_file.endswith('.jsonl')
        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_save_and_get_item(self):
        """Test saving and retrieving items"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            storage = LocalFileTokenStorage(temp_file)
            
            # Save item
            test_data = {"access_token": "test_token", "user_id": "U123"}
            await storage.save_item("test_key", test_data)
            
            # Get item
            retrieved = await storage.get_item("test_key")
            assert retrieved == test_data
            
            # Get non-existent item
            none_item = await storage.get_item("non_existent")
            assert none_item is None
        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_delete_item(self):
        """Test deleting items"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            storage = LocalFileTokenStorage(temp_file)
            
            # Save and delete item
            await storage.save_item("test_key", {"data": "test"})
            await storage.delete_item("test_key")
            
            # Verify deletion
            retrieved = await storage.get_item("test_key")
            assert retrieved is None
        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_scan_items(self):
        """Test scanning all items"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            storage = LocalFileTokenStorage(temp_file)
            
            # Save multiple items
            await storage.save_item("key1", {"data": "test1"})
            await storage.save_item("key2", {"data": "test2"})
            await storage.save_item("key3", {"data": "test3"})
            
            # Scan all items
            items = await storage.scan_items()
            assert len(items) == 3
            assert any(item["data"] == "test1" for item in items.values())
            assert any(item["data"] == "test2" for item in items.values())
            assert any(item["data"] == "test3" for item in items.values())
        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self):
        """Test cleanup of expired tokens"""
        import time
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_file = f.name
        
        try:
            storage = LocalFileTokenStorage(temp_file)
            
            # Save items with different expiry times
            current_time = int(time.time())
            
            # Expired token
            await storage.save_item("expired", {
                "data": "expired",
                "expires_at": current_time - 3600  # 1 hour ago
            })
            
            # Valid token
            await storage.save_item("valid", {
                "data": "valid",
                "expires_at": current_time + 3600  # 1 hour from now
            })
            
            # Token without expiry
            await storage.save_item("no_expiry", {
                "data": "no_expiry"
            })
            
            # Cleanup
            await storage.cleanup_expired_tokens()
            
            # Verify results
            items = await storage.scan_items()
            assert len(items) == 2
            assert "valid" in items
            assert "no_expiry" in items
            assert "expired" not in items
        finally:
            os.unlink(temp_file)


class TestDynamoDBStorage:
    """Test cases for DynamoDBStorage"""

    @pytest.mark.asyncio
    @mock_dynamodb
    async def test_init(self, mock_env):
        """Test DynamoDB storage initialization"""
        with patch.dict(os.environ, mock_env):
            storage = DynamoDBStorage()
            assert storage.table_name == "test-slack-tokens"
            assert storage.region == "us-east-1"

    @pytest.mark.asyncio
    @mock_dynamodb
    async def test_ensure_table_exists(self, mock_env):
        """Test table creation"""
        with patch.dict(os.environ, mock_env):
            storage = DynamoDBStorage()
            await storage._ensure_table_exists()
            
            # Verify table was created
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = dynamodb.Table('test-slack-tokens')
            assert table.table_status == 'ACTIVE'
            assert table.key_schema[0]['AttributeName'] == 'client_id'

    @pytest.mark.asyncio
    @mock_dynamodb
    async def test_save_and_get_item(self, mock_env):
        """Test saving and retrieving items from DynamoDB"""
        with patch.dict(os.environ, mock_env):
            storage = DynamoDBStorage()
            
            # Save item
            test_data = {
                "access_token": "test_token",
                "user_id": "U123",
                "team_id": "T123"
            }
            await storage.save_item("test_client_id", test_data)
            
            # Get item
            retrieved = await storage.get_item("test_client_id")
            assert retrieved["access_token"] == "test_token"
            assert retrieved["user_id"] == "U123"
            
            # Get non-existent item
            none_item = await storage.get_item("non_existent")
            assert none_item is None

    @pytest.mark.asyncio
    @mock_dynamodb
    async def test_delete_item(self, mock_env):
        """Test deleting items from DynamoDB"""
        with patch.dict(os.environ, mock_env):
            storage = DynamoDBStorage()
            
            # Save and delete item
            await storage.save_item("test_client_id", {"data": "test"})
            await storage.delete_item("test_client_id")
            
            # Verify deletion
            retrieved = await storage.get_item("test_client_id")
            assert retrieved is None

    @pytest.mark.asyncio
    @mock_dynamodb
    async def test_scan_items(self, mock_env):
        """Test scanning all items from DynamoDB"""
        with patch.dict(os.environ, mock_env):
            storage = DynamoDBStorage()
            
            # Save multiple items
            await storage.save_item("client1", {"data": "test1"})
            await storage.save_item("client2", {"data": "test2"})
            await storage.save_item("client3", {"data": "test3"})
            
            # Scan all items
            items = await storage.scan_items()
            assert len(items) == 3
            assert "client1" in items
            assert "client2" in items
            assert "client3" in items

    @pytest.mark.asyncio
    @mock_dynamodb
    async def test_cleanup_expired_tokens(self, mock_env):
        """Test cleanup of expired tokens in DynamoDB"""
        import time
        
        with patch.dict(os.environ, mock_env):
            storage = DynamoDBStorage()
            
            # Save items with TTL
            current_time = int(time.time())
            
            # This item should be cleaned up by DynamoDB TTL
            await storage.save_item("expired", {
                "data": "expired",
                "expires_at": current_time - 3600
            })
            
            # Valid token
            await storage.save_item("valid", {
                "data": "valid",
                "expires_at": current_time + 3600
            })
            
            # Note: DynamoDB TTL cleanup is async and not immediate
            # For testing, we just verify the cleanup method runs without error
            await storage.cleanup_expired_tokens()
            
            # All items should still be present (TTL is async)
            items = await storage.scan_items()
            assert len(items) == 2