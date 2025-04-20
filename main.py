import streamlit as st
from PIL import Image
import io
import os
import requests
import base64
from dotenv import load_dotenv
from datetime import datetime
import urllib.request  # ✅ これを追加！
import streamlit.components.v1 as components
from my_modules import model_create
import openai


# 環境変数読み込み
load_dotenv(".env")

# APIキーは環境変数から取得またはStreamlit Secretsから取得
open_api_key = os.getenv("OPENAI_API_KEY") or st.secrets["OPENAI_API_KEY"]
# sta_api_key = os.getenv('STABILITY_API_KEY') or st.secrets['STABILITY_API_KEY']
tripo_api_key = os.getenv('TRIPO_API_KEY') or st.secrets['TRIPO_API_KEY']

# if not api_key:
#     st.error("APIキーが見つかりません。")
#     st.stop()

# OpenAIクライアント初期化（v1以降）
openai.api_key = open_api_key 

# tripo関係のurl
tripo_upload_url = "https://api.tripo3d.ai/v2/openapi/upload"       # 画像アップロード用
tripo_task_url = "https://api.tripo3d.ai/v2/openapi/task"           # モデル生成タスク実行用



# セッション変数の初期化
if 'anime_image_bytes' not in st.session_state:
    st.session_state['anime_image_bytes'] = None
if 'model_file_path' not in st.session_state:
    st.session_state['model_file_path'] = None

# UI構成
st.title("写真 → 2Dアニメ変換 → 3Dモデル生成アプリ")

# サイドバーにスタイル選択オプションを追加
st.sidebar.header("スタイル設定")
style_option = st.sidebar.radio(
    "アートスタイルを選択してください:",
    ["ほのぼの風・やさしい水彩風",
     "キラキラ風・シネマティック風",
     "王道少年まんが風・元気アニメ風",
     "ゆるふわ日常風・ふんわりキャラ風",
     "レトロアニメ風、昭和・平成初期風",
     "ミニキャラやデフォルメ",
     "マンガ風・モノクロインクスタイル"]
)

# サイドバーに画像の影響度を調整するスライダーを追加
image_strength = st.sidebar.slider(
    "アニメ変換における元画像の影響度（低いほどアニメ化が強く出る）",
    min_value=0.1,
    max_value=1.0,
    value=0.35,
    step=0.05
)

uploaded_file = st.file_uploader("画像をアップロード（PNG, JPG）", type=["png", "jpg", "jpeg"])

    # ========== 写真 → アニメ風画像（GPTベース） ==========
if uploaded_file:
    input_image = Image.open(uploaded_file).convert("RGB")
    st.image(input_image, caption="アップロード画像")

    if st.button("① アニメ風に変換（GPTベース）"):
        with st.spinner("GPT-4oで画像を解析中..."):
            # 画像 → base64
            buf = io.BytesIO()
            input_image.save(buf, format="PNG")
            base64_image = base64.b64encode(buf.getvalue()).decode("utf-8")

            # GPT-4oに画像の特徴を説明させる
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "この画像の特徴を説明してください"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]
                    }
                ]
            )
            description = response.choices[0].message.content

        st.success("画像特徴の抽出完了")
        st.write("🔍 GPTによる説明（折りたたみ）")
        with st.expander("画像の説明"):
            st.write(description)

        with st.spinner("DALL·E 3でアニメ風画像を生成中..."):
            # プロンプトを組み立て
            prompt = f"{style_option} のスタイルで、次の特徴を持つ人物をアニメイラストにしてください: {description}"

            # DALL·E 3で画像生成
            image_response = openai.images.generate(
                model="dall-e-3",
                prompt=prompt,  # ← 上で組み立てたプロンプトを正しく使う
                n=1,
                size="1024x1024"
            )
            generated_url = image_response.data[0].url
            st.image(generated_url, caption=f"{style_option}で変換された画像", use_column_width=True)

            # ダウンロード用に保存
            temp_filename = f"anime_{datetime.now():%Y%m%d%H%M%S}.png"
            urllib.request.urlretrieve(generated_url, temp_filename)

            with open(temp_filename, "rb") as f:
                st.session_state["anime_image_bytes"] = f.read()

            # ダウンロードボタン
            st.download_button(
                label="アニメ画像をダウンロード",
                data=st.session_state["anime_image_bytes"],
                file_name=temp_filename,
                mime="image/png"
            )

# =============================
# ② 3Dモデル生成ステップ
# =============================
# 3Dモデル生成クラスからインスタンスを設定
ModelCreate = model_create.ModelCreate(tripo_api_key,
                                       tripo_upload_url,
                                       tripo_task_url)

if st.session_state["anime_image_bytes"]:
    if st.button("② 3Dモデルを生成"):
        with open("temp_anime_image.png", "wb") as f:
            f.write(st.session_state["anime_image_bytes"])

        with st.spinner("画像をTripoにアップロード中..."):
            image_token = ModelCreate.upload_image("temp_anime_image.png")

        with st.spinner("3Dモデル生成タスクを実行中..."):
            task_url = ModelCreate.image_to_model(image_token)
            result = ModelCreate.wait_for_task_completion(task_url)

        if result["data"]["status"] == "success":

            # モデルパスをセッションに保存
            model_path = ModelCreate.model_download(result)
            st.session_state["model_file_path"] = model_path

            st.subheader("🌀 生成された3Dモデル（GLB）ビュー")

            with open(model_path, "rb") as f:
                glb_bytes = f.read()
                glb_base64 = base64.b64encode(glb_bytes).decode()

            components.html(
                f"""
                <html>
                <head>
                  <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
                </head>
                <body>
                  <model-viewer
                    src="data:model/gltf-binary;base64,{glb_base64}"
                    alt="3D Model"
                    auto-rotate
                    camera-controls
                    camera-orbit="45deg 70deg 2.5m"
                    min-camera-orbit="auto 0deg auto"
                    max-camera-orbit="auto 100deg auto"
                    min-field-of-view="20deg"
                    max-field-of-view="80deg"
                    style="width: 100%; height: 600px; background-color: #f0f0f0;">
                  </model-viewer>
                </body>
                </html>
                """,
                height=650
            )

            st.success("3Dモデル生成完了 🎉")
            st.write(f"保存先: {model_path}")
        else:
            st.error("3Dモデル生成に失敗しました")
# =============================
# ③ 表示
# =============================
if st.session_state.get("model_file_path"):
    st.subheader("生成された3Dモデル（GLB）")
