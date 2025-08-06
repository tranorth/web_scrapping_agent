# search_utils.py

import os
import requests

from dotenv import load_dotenv
load_dotenv()

from google import genai

PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')

def get_model_name():
    print('Getting model name...')
    client = genai.Client(vertexai=True, project=PROJECT_ID, location='us-central1')
    models = [
        model for model in client.models.list()
        if (
            'gemini' in model.name.lower() and
            'preview' not in model.name.lower() and
            '.' in model.name
        )
    ]

    def get_model_score(model):
        try:
            left = model.name.split('.')[0][-1]
            right = model.name.split('.')[1][0]
            return float(f"{left}.{right}")
        except Exception:
            return None

    # Find models with the highest score
    scored_models = [(model, get_model_score(model)) for model in models]
    max_score = max((score for _, score in scored_models if score is not None), default=0)
    models = [model for model, score in scored_models if score == max_score]

    # Categorize models
    def filter_models(models, keyword, exclude_names=None):
        exclude_names = exclude_names or set()
        return [
            model for model in models
            if keyword in model.name.lower() and model.name not in exclude_names
        ]

    lite_names = {model.name for model in models if 'lite' in model.name.lower()}
    pro_models = filter_models(models, 'pro', exclude_names=lite_names)
    flash_models = filter_models(models, 'flash', exclude_names=lite_names)
    lite_models = filter_models(models, 'lite')

    # Select target model
    target_model = (
        pro_models[0] if pro_models else
        flash_models[0] if flash_models else
        lite_models[0] if lite_models else
        None
    )

    if not target_model:
        print("No models found")
        model_name = None
    else:
        model_name = target_model.name.split('/')[-1]

    return model_name

def download_pdf_bytes(url: str) -> bytes:
    """
    Downloads the PDF from the specified URL and returns its bytes.
    """
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code == 200:
        return response.content
    return None