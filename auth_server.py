"""OAuth認証サーバーの実装"""

import asyncio
import os
import ssl
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Slack OAuth認証のリダイレクト受信ハンドラー"""

    def do_GET(self):
        # リクエストURLからクエリパラメータを取得
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # OAuth callbackパスのみ処理
        if parsed.path != "/oauth/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        # 認証結果をサーバーに保存
        if hasattr(self.server, "auth_result"):
            if "code" in params:
                self.server.auth_result["code"] = params["code"][0]
                response_html = """
                <html>
                  <head><title>認証完了</title></head>
                  <body>
                    <h1>✅ Slack認証が完了しました</h1>
                    <p>このウィンドウを閉じてターミナルに戻ってください。</p>
                  </body>
                </html>
                """
            elif "error" in params:
                self.server.auth_result["error"] = params["error"][0]
                response_html = f"""
                <html>
                  <head><title>認証エラー</title></head>
                  <body>
                    <h1>❌ Slack認証でエラーが発生しました</h1>
                    <p>エラー内容: <code>{params['error'][0]}</code></p>
                    <p>このウィンドウを閉じてターミナルに戻ってください。</p>
                  </body>
                </html>
                """
            else:
                response_html = """
                <html>
                  <head><title>不明なリクエスト</title></head>
                  <body>
                    <h1>⚠️ リクエストに認証コードが含まれていません</h1>
                    <p>ブラウザのアドレスバーのURLを確認してください。</p>
                  </body>
                </html>
                """

            # ブラウザに結果を表示
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(response_html.encode("utf-8"))

    def log_message(self, format, *args):
        # HTTPリクエストのログを表示しないようにオーバーライド
        return


class AuthServer:
    """OAuth認証サーバー"""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.server: Optional[HTTPServer] = None
        self.port = 0

    def create_self_signed_cert(self) -> Tuple[Optional[str], Optional[str]]:
        """一時ディレクトリに自己署名SSL証明書と秘密鍵を生成"""
        try:
            temp_dir = tempfile.mkdtemp()
            cert_path = os.path.join(temp_dir, "cert.pem")
            key_path = os.path.join(temp_dir, "key.pem")

            subprocess_result = os.system(
                f"openssl req -x509 -newkey rsa:2048 -nodes -keyout {key_path} -out {cert_path} "
                f'-days 365 -subj "/C=JP/ST=Tokyo/L=Tokyo/O=LocalMCP/CN=localhost" 2>/dev/null'
            )

            if subprocess_result != 0:
                return None, None
            return cert_path, key_path
        except Exception:
            return None, None

    def start_callback_server(self) -> Optional[int]:
        """コールバックサーバーを起動し、ポート番号を返す"""
        try:
            # デフォルトポート8443、環境変数で変更可能
            port = int(os.environ.get("SLACK_OAUTH_PORT", "8443"))
            try:
                server = HTTPServer(("localhost", port), OAuthCallbackHandler)
                # 認証結果を保存するための属性を追加
                server.auth_result = {"code": None, "error": None}

                # SSL証明書の適用を試行
                cert_file, key_file = self.create_self_signed_cert()
                if cert_file and key_file:
                    try:
                        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                        ssl_ctx.load_cert_chain(cert_file, key_file)
                        server.socket = ssl_ctx.wrap_socket(
                            server.socket, server_side=True
                        )
                    except Exception:
                        # SSL失敗時はHTTPで続行
                        pass

                self.server = server
                self.port = port

                # バックグラウンドでサーバーを起動
                server_thread = threading.Thread(
                    target=server.serve_forever, daemon=True
                )
                server_thread.start()

                print(f"✅ OAuth callbackサーバーが起動しました (ポート:{port})")
                return port

            except OSError as e:
                print(
                    f"❌ ポート{port}が使用中です。他のプロセスを停止するか、SLACK_OAUTH_PORT環境変数で別のポートを指定してください: {e}"
                )
                return None

        except Exception as e:
            print(f"❌ callbackサーバーの起動に失敗: {e}")
            return None

    def make_oauth_request(self, scope: str) -> Optional[str]:
        """OAuth認証URLを生成してブラウザで開く"""
        if not self.port:
            return None

        redirect_uri = f"https://localhost:{self.port}/oauth/callback"
        base_url = "https://slack.com/oauth/v2/authorize"
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
        }

        req = requests.Request("GET", base_url, params=params)
        oauth_url = req.prepare().url

        if oauth_url:
            print(f"OAuth URL: {oauth_url}")
            print("ブラウザでSlack認証ページを開きます...")
            webbrowser.open(oauth_url)
            return oauth_url
        return None

    async def wait_for_auth_completion(self, timeout: int = 300) -> Optional[str]:
        """OAuth認証の完了を待機し、認証コードを返す"""
        if not self.server or not hasattr(self.server, "auth_result"):
            return None

        start_time = time.time()

        while time.time() - start_time < timeout:
            auth_result = self.server.auth_result

            if auth_result["code"]:
                return auth_result["code"]
            elif auth_result["error"]:
                print(f"❌ OAuth認証エラー: {auth_result['error']}")
                return None

            await asyncio.sleep(1)

        print("❌ OAuth認証がタイムアウトしました")
        return None

    def exchange_code_for_token(self, code: str) -> Dict:
        """認証コードをSlackのOAuthアクセストークンに交換"""
        if not self.port:
            return {"ok": False, "error": "callback server not started"}

        redirect_uri = f"https://localhost:{self.port}/oauth/callback"
        token_url = "https://slack.com/api/oauth.v2.access"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        try:
            resp = requests.post(token_url, data=data)
            result = resp.json()

            # デバッグ情報を出力
            if not result.get("ok"):
                print(f"❌ Slack API エラー詳細:")
                print(f"   Error: {result.get('error')}")
                print(f"   Response: {result}")
                print(f"   Sent redirect_uri: {redirect_uri}")

            return result
        except requests.RequestException as e:
            print(f"❌ アクセストークン取得エラー: {e}")
            return {"ok": False, "error": str(e)}

    def shutdown(self):
        """サーバーを停止"""
        if self.server:
            try:
                self.server.shutdown()
                print("✅ OAuth callbackサーバーを停止しました")
            except Exception as e:
                print(f"callbackサーバーの停止エラー: {e}")
            finally:
                self.server = None
                self.port = 0
