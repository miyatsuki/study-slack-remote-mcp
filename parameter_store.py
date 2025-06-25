"""AWS Parameter Store client for secure configuration management"""

import os
from typing import Dict, Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from storage_interface import is_cloud_environment


class ParameterStoreClient:
    """AWS Parameter Store client for secure configuration"""
    
    def __init__(self, region: str = None):
        self.region = region or os.getenv("AWS_REGION", "ap-northeast-1")
        self.ssm_client = None
        self._parameter_cache = {}
        
        if is_cloud_environment():
            if not BOTO3_AVAILABLE:
                raise ImportError("boto3 is required for Parameter Store. Install with: pip install boto3")
            
            try:
                self.ssm_client = boto3.client('ssm', region_name=self.region)
                print(f"✅ Parameter Store クライアントを初期化しました (リージョン: {self.region})")
            except NoCredentialsError:
                print("❌ AWS認証情報が見つかりません。IAMロールまたは環境変数を設定してください。")
                raise
            except Exception as e:
                print(f"❌ Parameter Store 接続エラー: {e}")
                raise
        else:
            print("💻 ローカル環境 - Parameter Store をスキップ、環境変数を使用")
    
    def get_parameter(self, parameter_name: str, decrypt: bool = True) -> Optional[str]:
        """
        Get parameter value from Parameter Store
        
        Args:
            parameter_name: Parameter name (e.g., '/slack-mcp/dev/client-id')
            decrypt: Whether to decrypt SecureString parameters
            
        Returns:
            Parameter value or None if not found
        """
        # Local environment - use environment variables
        if not is_cloud_environment() or not self.ssm_client:
            # Map parameter names to environment variable names
            env_var_map = {
                '/slack-mcp/client-id': 'SLACK_CLIENT_ID',
                '/slack-mcp/client-secret': 'SLACK_CLIENT_SECRET',
                '/slack-mcp/service-base-url': 'SERVICE_BASE_URL',
                # Environment-specific mappings
                '/slack-mcp/dev/client-id': 'SLACK_CLIENT_ID',
                '/slack-mcp/dev/client-secret': 'SLACK_CLIENT_SECRET',
                '/slack-mcp/dev/service-base-url': 'SERVICE_BASE_URL',
                '/slack-mcp/staging/client-id': 'SLACK_CLIENT_ID',
                '/slack-mcp/staging/client-secret': 'SLACK_CLIENT_SECRET',
                '/slack-mcp/staging/service-base-url': 'SERVICE_BASE_URL',
                '/slack-mcp/prod/client-id': 'SLACK_CLIENT_ID',
                '/slack-mcp/prod/client-secret': 'SLACK_CLIENT_SECRET',
                '/slack-mcp/prod/service-base-url': 'SERVICE_BASE_URL'
            }
            env_var = env_var_map.get(parameter_name)
            if env_var:
                return os.getenv(env_var)
            return None
        
        # Check cache first
        if parameter_name in self._parameter_cache:
            return self._parameter_cache[parameter_name]
        
        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=decrypt
            )
            
            value = response['Parameter']['Value']
            # Cache the value
            self._parameter_cache[parameter_name] = value
            
            print(f"✅ Parameter Store からパラメータを取得: {parameter_name}")
            return value
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ParameterNotFound':
                print(f"⚠️ パラメータが見つかりません: {parameter_name}")
            else:
                print(f"❌ Parameter Store エラー ({parameter_name}): {e}")
            return None
        except Exception as e:
            print(f"❌ パラメータ取得エラー ({parameter_name}): {e}")
            return None
    
    def get_slack_config(self) -> Dict[str, Optional[str]]:
        """
        Get all Slack-related configuration parameters
        
        Returns:
            Dictionary with client_id, client_secret, and service_base_url
        """
        # Check if parameter names are provided via environment variables (ECS deployment)
        client_id_param = os.getenv('SLACK_CLIENT_ID_PARAM')
        client_secret_param = os.getenv('SLACK_CLIENT_SECRET_PARAM')
        service_base_url_param = os.getenv('SERVICE_BASE_URL_PARAM')
        
        if client_id_param and client_secret_param and service_base_url_param:
            # Use parameter names from environment variables (cloud deployment)
            config = {
                'client_id': self.get_parameter(client_id_param, decrypt=False),
                'client_secret': self.get_parameter(client_secret_param, decrypt=True),
                'service_base_url': self.get_parameter(service_base_url_param, decrypt=False)
            }
        else:
            # Fallback to default parameter names (local deployment)
            env_name = os.getenv('MCP_ENV', 'dev')
            config = {
                'client_id': self.get_parameter(f'/slack-mcp/{env_name}/client-id', decrypt=False),
                'client_secret': self.get_parameter(f'/slack-mcp/{env_name}/client-secret', decrypt=True),
                'service_base_url': self.get_parameter(f'/slack-mcp/{env_name}/service-base-url', decrypt=False)
            }
        
        # Validate required parameters
        missing_params = [key for key, value in config.items() if value is None and key in ['client_id', 'client_secret']]
        if missing_params:
            if is_cloud_environment():
                print(f"❌ 必須パラメータが見つかりません: {missing_params}")
                print("💡 Parameter Store に以下のパラメータを設定してください:")
                for param in missing_params:
                    param_name = f"/slack-mcp/{param.replace('_', '-')}"
                    print(f"   {param_name}")
            else:
                print(f"❌ 必須環境変数が見つかりません: {[p.upper() for p in missing_params]}")
                print("💡 .env ファイルまたは環境変数を設定してください")
        
        return config
    
    def refresh_cache(self):
        """Clear parameter cache to force refresh"""
        self._parameter_cache.clear()
        print("🔄 Parameter Store キャッシュをクリアしました")


# Global parameter store client instance
_parameter_store_client = None

def get_parameter_store_client() -> ParameterStoreClient:
    """Get global parameter store client instance"""
    global _parameter_store_client
    if _parameter_store_client is None:
        _parameter_store_client = ParameterStoreClient()
    return _parameter_store_client