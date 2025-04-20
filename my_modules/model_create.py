import requests
import json
import time
import os
from datetime import datetime



class ModelCreate():

    # クラスが呼ばれた時の初期化処理
    def __init__(self, api_key, upload_ulr, task_url):
        self.api_key = api_key          # TRIPOのAPIキー
        self.upload_url = upload_ulr    # アップロードURL
        self.task_url = task_url        # モデル変換タスクURL

    # 画像をTripoサーバーにアップロードする処理
    def upload_image(self, image):
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        # リクエストとして投げるファイルを整理
        files = {'file': (os.path.basename(image), open(image, 'rb'), 'image/png')}
        # 画像ファイルのアップロードをリクエスト
        response = requests.post(self.upload_url, headers=headers, files=files)

        # tokenを取り出し
        token = response.json()['data']['image_token']

        return token
    
    def image_to_model(self, image_token):
        # ヘッダー
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 画像のトークンをデータとして渡す
        data = {
            "type": "image_to_model",
            "file": {
                "type": "png",
                "file_token": image_token
            }
        }

        # 画像からモデルを生成するリクエスト
        response = requests.post(self.task_url, headers=headers, json=data)

        # 生成したモデルを取りに行くのに必要なurlを作るため、タスクidを取り出し
        task_id = response.json()['data']['task_id']

        # 生成したモデルを取りに行くのに必要なurlを作成
        result_url = self.task_url + '/' + task_id

        return result_url
    

    # ModelCreate クラスに待機メソッドを追加
    def wait_for_task_completion(self, result_url, timeout=300, interval=5):
        """
        タスクが完了するまで待機する

        Parameters:
        - result_url: タスク結果を取得するURL
        - timeout: タイムアウト時間（秒）
        - interval: ポーリング間隔（秒）

        Returns:
        - タスク結果のJSON
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        start_time = time.time()
        while time.time() - start_time < timeout:
            # タスク実行結果を取得
            result = requests.get(result_url, headers=headers).json()

            # ステータスをチェック
            status = result['data']['status']
            if status == 'success':
                return result
            elif status == 'failed':
                raise Exception(f"タスクが失敗しました: {result}")

            # 処理中の場合は待機
            time.sleep(interval)

        raise TimeoutError(f"タスクが{timeout}秒以内に完了しませんでした")
    
    def model_download(self, task_result):
        try:
            # 正しい場所からURLを取得
            model_url = task_result["data"]["result"]["pbr_model"]["url"]
        except KeyError:
            raise Exception("task_resultに正しい'model_url'が含まれていません")

        # 保存先のディレクトリを作成
        os.makedirs("./download_models", exist_ok=True)
        filename = f"model_{datetime.now():%Y%m%d_%H%M%S}.glb"
        model_file_path = os.path.join("./download_models", filename)

        # ダウンロードして保存
        response = requests.get(model_url)
        if response.status_code != 200:
            raise Exception(f"モデルのダウンロードに失敗しました: {response.status_code}")
        
        with open(model_file_path, "wb") as f:
            f.write(response.content)

        return model_file_path

 