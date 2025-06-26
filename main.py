import os
import ssl
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()


def make_oauth_request(client_id: str, redirect_uri: str, scope: str):
    """
    SlackのOAuth認証URLを生成してブラウザで開く

    Args:
        client_id: SlackアプリのClient ID
        redirect_uri: リダイレクトURL
        scope: 要求するスコープ

    Returns:
        str: 生成されたOAuth URL
    """
    base_url = "https://slack.com/oauth/v2/authorize"

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
    }

    try:
        # URLを生成（実際のリクエストは送信しない）
        response = requests.Request("GET", base_url, params=params)
        prepared = response.prepare()
        oauth_url = prepared.url

        print(f"OAuth URL: {oauth_url}")
        print("ブラウザでSlack認証ページを開いています...")

        # ブラウザでURLを開く
        webbrowser.open(oauth_url)

        return oauth_url

    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


# グローバル変数で認証コードを保存
auth_code = None
auth_error = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """OAuth認証コールバックを処理するHTTPハンドラー"""

    def do_GET(self):
        global auth_code, auth_error

        # URLを解析してクエリパラメータを取得
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        # 認証コードまたはエラーを取得
        if "code" in query_params:
            auth_code = query_params["code"][0]
            response_html = """
            <html>
            <head><title>認証完了</title></head>
            <body>
                <h1>✅ 認証が完了しました！</h1>
                <p>認証コード: <code>{}</code></p>
                <p>このウィンドウを閉じてターミナルに戻ってください。</p>
            </body>
            </html>
            """.format(
                auth_code
            )
        elif "error" in query_params:
            auth_error = query_params["error"][0]
            response_html = """
            <html>
            <head><title>認証エラー</title></head>
            <body>
                <h1>❌ 認証エラー</h1>
                <p>エラー: <code>{}</code></p>
                <p>このウィンドウを閉じてターミナルに戻ってください。</p>
            </body>
            </html>
            """.format(
                auth_error
            )
        else:
            response_html = """
            <html>
            <head><title>不明なリクエスト</title></head>
            <body>
                <h1>⚠️ 不明なリクエスト</h1>
                <p>認証コードまたはエラーが見つかりませんでした。</p>
            </body>
            </html>
            """

        # レスポンスを送信
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(response_html.encode("utf-8"))

    def log_message(self, format, *args):
        # ログメッセージを無効化（コンソール出力をクリーンに保つため）
        pass


def start_callback_server(port=8443, use_https=True):
    """OAuth認証コールバックを受け取るローカルサーバーを起動"""
    try:
        server = HTTPServer(("localhost", port), OAuthCallbackHandler)

        if use_https:
            # 自己署名証明書を生成
            cert_file, key_file = create_self_signed_cert()
            if cert_file and key_file:
                # HTTPSサーバーとして設定
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(cert_file, key_file)
                server.socket = context.wrap_socket(server.socket, server_side=True)
                print(f"✅ HTTPSサーバーを作成しました")
            else:
                print("❌ HTTPS証明書の生成に失敗しました。")
                return None, None, False

        return server, port, use_https

    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ ポート {port} は既に使用されています。")
            print(
                f"ポート {port} を使用している他のプロセスを終了してから再試行してください。"
            )
            return None, None, False
        else:
            print(f"❌ サーバーの起動に失敗しました: {e}")
            return None, None, False


def create_self_signed_cert():
    """自己署名証明書を生成"""
    try:
        # 一時ディレクトリに証明書を作成
        temp_dir = tempfile.mkdtemp()
        cert_file = os.path.join(temp_dir, "cert.pem")
        key_file = os.path.join(temp_dir, "key.pem")

        # opensslコマンドを使用して自己署名証明書を生成
        import subprocess

        cmd = [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            key_file,
            "-out",
            cert_file,
            "-days",
            "365",
            "-nodes",
            "-subj",
            "/C=JP/ST=Tokyo/L=Tokyo/O=Test/CN=localhost",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"証明書の生成に失敗しました: {result.stderr}")

        return cert_file, key_file
    except Exception as e:
        print(f"❌ 証明書生成エラー: {e}")
        print(
            "代替案: HTTPSなしでSlackアプリの設定を変更するか、ngrokなどのツールを使用してください。"
        )
        return None, None


def exchange_code_for_token(
    client_id: str, client_secret: str, code: str, redirect_uri: str
):
    """
    認証コードをアクセストークンに交換

    Args:
        client_id: SlackアプリのClient ID
        client_secret: SlackアプリのClient Secret
        code: 認証コード
        redirect_uri: リダイレクトURL

    Returns:
        dict: トークン交換のレスポンス
    """
    token_url = "https://slack.com/api/oauth.v2.access"

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ トークン交換エラー: {e}")
        return None


def test_slack_permissions(access_token: str):
    """
    取得したアクセストークンでSlackの権限をテスト

    Args:
        access_token: アクセストークン
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    print("\n=== Slack API 権限テスト ===")

    # 1. channels:read のテスト - チャンネル一覧取得
    print("1. チャンネル一覧取得テスト (channels:read)...")
    try:
        response = requests.get(
            "https://slack.com/api/conversations.list", headers=headers
        )
        response.raise_for_status()
        data = response.json()

        if data.get("ok"):
            channels = data.get("channels", [])
            print(f"✅ 成功: {len(channels)} 個のチャンネルを取得しました")

            # 最初のチャンネル（通常は #general）を選択
            if channels:
                test_channel = channels[0]
                channel_id = test_channel["id"]
                channel_name = test_channel.get("name", "unknown")
                print(f"   テスト用チャンネル: #{channel_name} ({channel_id})")

                # 2. chat:write のテスト - メッセージ送信
                print(f"2. メッセージ送信テスト (chat:write) to #{channel_name}...")
                message_data = {
                    "channel": channel_id,
                    "text": "Hello from OAuth test! 🤖 このメッセージは認証テストです。",
                }

                response = requests.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=headers,
                    json=message_data,
                )
                response.raise_for_status()
                msg_data = response.json()

                if msg_data.get("ok"):
                    print(f"✅ 成功: #{channel_name} にメッセージを送信しました")
                else:
                    print(
                        f"❌ メッセージ送信失敗: {msg_data.get('error', 'unknown error')}"
                    )
            else:
                print("❌ テスト用チャンネルが見つかりません")
        else:
            print(f"❌ チャンネル取得失敗: {data.get('error', 'unknown error')}")

    except requests.exceptions.RequestException as e:
        print(f"❌ API リクエストエラー: {e}")


def main():
    global auth_code, auth_error

    # 使用例
    client_id = "client_id"  # 2.1 でメモしたClient Id
    client_secret = os.getenv("SLACK_CLIENT_SECRET")  # .envファイルから読み込み

    if not client_secret:
        print("❌ SLACK_CLIENT_SECRET が .env ファイルに設定されていません。")
        print("   .env ファイルに以下の形式で設定してください:")
        print("   SLACK_CLIENT_SECRET=your_client_secret_here")
        return

    scope = "chat:write,channels:read"  # 2.3 で設定したScope
    port = 8000  # MCP server port for OAuth callback

    print("=== Slack OAuth 認証開始 ===")

    # 1. ローカルサーバーを起動
    print(f"ローカルサーバーをポート {port} で起動中...")
    server, actual_port, is_https = start_callback_server(port, use_https=True)

    # サーバーの起動に失敗した場合は終了
    if server is None:
        print("❌ サーバーの起動に失敗しました。プログラムを終了します。")
        return

    # プロトコルを決定
    protocol = "https" if is_https else "http"
    redirect_uri = f"{protocol}://localhost:{actual_port}"

    # サーバーを別スレッドで実行
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    print(f"✅ サーバーが起動しました: {redirect_uri}")
    print(
        f"📝 Slackアプリの設定で以下のリダイレクトURIを設定してください: {redirect_uri}"
    )

    if is_https:
        print(
            "⚠️  ブラウザで証明書の警告が表示される場合は「詳細設定」→「localhost に進む (安全ではありません)」をクリックしてください。"
        )

    # 2. OAuth URLを生成してブラウザで開く
    oauth_url = make_oauth_request(client_id, redirect_uri, scope)

    if not oauth_url:
        print("❌ OAuth URL の生成に失敗しました。")
        server.shutdown()
        return

    # 3. 認証コードを待機
    print("Slackでの認証を待機中...")
    print("ブラウザで認証を完了してください。")

    timeout = 300  # 5分間のタイムアウト
    start_time = time.time()

    while auth_code is None and auth_error is None:
        if time.time() - start_time > timeout:
            print("❌ タイムアウトしました。認証を再試行してください。")
            break
        time.sleep(1)

    # 4. 認証結果の処理
    if auth_code:
        print("✅ 認証が完了しました！")

        # 5. 認証コードをアクセストークンに交換
        print("🔄 アクセストークンを取得中...")
        token_response = exchange_code_for_token(
            client_id, client_secret, auth_code, redirect_uri
        )

        if token_response and token_response.get("ok"):
            access_token = token_response.get("access_token")
            print("✅ アクセストークンの取得に成功しました")

            # 6. Slack API の権限をテスト
            test_slack_permissions(access_token)

        else:
            error_msg = (
                token_response.get("error", "unknown error")
                if token_response
                else "no response"
            )
            print(f"❌ アクセストークンの取得に失敗しました: {error_msg}")

    elif auth_error:
        print(f"❌ 認証エラー: {auth_error}")
    else:
        print("❌ 認証がタイムアウトしました")

    # サーバーをシャットダウン
    server.shutdown()
    print("サーバーを停止しました。")


if __name__ == "__main__":
    main()
