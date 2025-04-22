import streamlit as st
from PIL import Image
import io
import os
import requests
import base64
from dotenv import load_dotenv
from datetime import datetime
import urllib.request
import streamlit.components.v1 as components
from my_modules import model_create
import openai
import trimesh
from gear_model import gear_app

# 環境変数読み込み
load_dotenv(".env")

# APIキーは環境変数から取得またはStreamlit Secretsから取得
open_api_key = os.getenv("OPENAI_API_KEY") or st.secrets["OPENAI_API_KEY"]
# sta_api_key = os.getenv('STABILITY_API_KEY') or st.secrets['STABILITY_API_KEY']
tripo_api_key = os.getenv('TRIPO_API_KEY') or st.secrets['TRIPO_API_KEY']

# OpenAIクライアント初期化（v1以降）
openai.api_key = open_api_key 

# tripo関係のurl
tripo_upload_url = "https://api.tripo3d.ai/v2/openapi/upload"       # 画像アップロード用
tripo_task_url = "https://api.tripo3d.ai/v2/openapi/task"           # モデル生成タスク実行用


# セッション変数の初期化
if 'app_state' not in st.session_state:
    st.session_state['app_state'] = 'normal'
if 'anime_image_bytes' not in st.session_state:
    st.session_state['anime_image_bytes'] = None
if 'model_file_path' not in st.session_state:
    st.session_state['model_file_path'] = None
if "generated_url" not in st.session_state:
    st.session_state["generated_url"] = None
if "temp_filename" not in st.session_state:
    st.session_state["temp_filename"] = None
if "image_description" not in st.session_state:
    st.session_state["image_description"] = None
if "uploaded_image" not in st.session_state:
    st.session_state["uploaded_image"] = None

def normal_app():

    # 隠しボタンの設置 - 右上の小さなスペースに透明感のあるボタンを配置
    col1, col2, col3 = st.columns([6, 6, 1])
    with col3:
        if st.button("", help=""):
            # 秘密アプリ（歯車）状態に切り替え
            st.session_state['app_state'] = 'secret'
            st.rerun()

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

    uploaded_file = st.file_uploader("画像をアップロード（PNG, JPG）",
                                     type=["png", "jpg", "jpeg"])

    # =============================
    # 画像アップロード・生成ステップ
    # =============================
    if uploaded_file:
        # 新しく画像がアップロードされた場合のみ読み込む
        input_image = Image.open(uploaded_file).convert("RGB")
        st.session_state["uploaded_image"] = input_image
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
                # 画像解析コメントをsession_stateに保存
                description = response.choices[0].message.content
                st.session_state["image_description"] = description


            st.success("画像特徴の抽出完了")
            st.write("GPTによる説明（折りたたみ）")
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
                # 生成した画像のURLを取得・保存
                generated_url = image_response.data[0].url
                st.session_state["generated_url"] = generated_url


                # ダウンロード用に保存
                temp_filename = f"anime_{datetime.now():%Y%m%d%H%M%S}.png"
                st.session_state["temp_filename"] = temp_filename
                urllib.request.urlretrieve(generated_url, temp_filename)
                with open(temp_filename, "rb") as f:
                    st.session_state["anime_image_bytes"] = f.read()

    if st.session_state.get("generated_url"):
        # 生成画像画像表示
        st.image(st.session_state["generated_url"],
                 caption=f"{style_option}で変換された画像",
                 use_column_width=True)

        # ダウンロードボタン
        st.download_button(
            label="アニメ画像をダウンロード",
            data=st.session_state["anime_image_bytes"],
            file_name=st.session_state["temp_filename"],
            mime="image/png"
        )

    # =========================
    # 3Dモデル生成ステップ
    # =============================
    # 3Dモデル生成クラスからインスタンスを設定
    ModelCreate = model_create.ModelCreate(tripo_api_key,
                                           tripo_upload_url,
                                           tripo_task_url)


    if st.session_state.get("anime_image_bytes"):
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

                st.success("3Dモデル生成完了 🎉")

            else:
                st.error("3Dモデル生成に失敗しました")
    # =============================
    # 表示
    # =============================
    if st.session_state.get("model_file_path"):
        st.subheader("生成された3Dモデルビュー")

        with open(st.session_state["model_file_path"], "rb") as f:
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



    # =============================
    # GLB → STL変換とダウンロード
    # =============================
    if st.session_state.get("model_file_path"):
        st.subheader("📦 3DモデルをSTL形式でダウンロード")

        # GLBファイルのパスを取得
        glb_path = st.session_state["model_file_path"]

        # GLBファイルからメッシュを読み込み
        mesh = trimesh.load(glb_path, file_type='glb')

        # STL形式でバイナリデータに変換
        stl_io = io.BytesIO()                   # メモリ上のバイナリファイルを扱う
        mesh.export(stl_io, file_type='stl')    # メッシュ化した3DモデルをSTLに変換してバイナリに書き込み
        stl_data = stl_io.getvalue()            # バイナリをbytes型で取得

        # ダウンロードボタン（変換と一体化）
        st.download_button(
            label="STL形式に変換してダウンロード",
            data=stl_data,
            file_name=os.path.basename(glb_path).replace(".glb", ".stl"),
            mime="application/sla"
        )


if st.session_state['app_state'] == 'normal':
    normal_app()
else:
    gear_app()

