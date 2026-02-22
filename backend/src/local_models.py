"""
Local ML models for alloy property prediction.

svr-regressor: γ' solvus temperature (℃)
When trained models are not available, falls back to mock mode.
Set MOCK_MODELS=1 in .env to force mock mode.
"""
import json
import logging
import os
import re
from dotenv import load_dotenv

load_dotenv()
MOCK_MODE = os.environ.get("MOCK_MODELS", "").lower() in ("1", "true", "yes")

logger = logging.getLogger(__name__)
file_dir = os.path.dirname(os.path.realpath(__file__))
models_dir = os.path.join(file_dir, "models")
data_dir = os.path.join(file_dir, "data", "data_for_materials_model")

pipes = None


def _load_dataset(train_dataname: str, n_features: int):
    """Load training data for scaler fitting."""
    import pandas as pd
    path = os.path.join(data_dir, train_dataname)
    if not os.path.exists(path):
        return None
    data = pd.read_csv(path)
    data = data.values
    return data[:, 0:n_features]


def _load_pipes():
    """Lazy load models. Returns None if models not available."""
    global pipes
    if pipes is not None:
        return pipes
    if MOCK_MODE:
        logger.info("MOCK_MODE: Using placeholder responses")
        return None
    try:
        import joblib
        import numpy as np
        from sklearn import preprocessing

        if not os.path.exists(models_dir):
            logger.warning("Models directory not found, using mock mode")
            return None

        # svr-regressor: γ' solvus temperature
        svr_regressor_path = os.path.join(models_dir, "svr_regressor.bin")
        if not os.path.exists(svr_regressor_path):
            logger.warning("svr_regressor.bin not found, using mock mode")
            return None

        solvus_data = _load_dataset("solvus.csv", 24)
        if solvus_data is None:
            logger.warning("solvus.csv not found for scaler, using mock mode")
            return None

        scaler = preprocessing.StandardScaler().fit(solvus_data)
        model = joblib.load(svr_regressor_path)
        pipes = {"svr-regressor": {"model": model, "scaler": scaler}}
        return pipes
    except Exception as e:
        logger.warning(f"Could not load models: {e}, using mock mode")
        return None


def _mock_inference(model_id: str, tab: str):
    """Return placeholder results when models unavailable."""
    if model_id == "gbc-class":
        return False
    if model_id in ("svr-regressor", "gbr-liquidus", "svr-solidus", "gbr-density", "gbr-size"):
        return {"value": "0.00", "unit": "℃" if "temperature" in model_id or "solidus" in model_id or "liquidus" in model_id or "regressor" in model_id else "g/cm3" if "density" in model_id else "mm"}
    if model_id == "gbr-misfit":
        return "0.00"
    return {"error": f"Unknown model: {model_id}"}


def local_model_inference(model_id: str, tab: str):
    pipes = _load_pipes()
    if pipes is None or model_id not in pipes:
        return _mock_inference(model_id, tab)

    try:
        from utils import llm_request
        from prompt_templates import DATA_CLEANING_PROMPT_TEMPLATE
        import numpy as np

        pipe = pipes[model_id]["model"]
        scaler = pipes[model_id].get("scaler")
        input_labels = "Co,Al,W,Ni,Ti,Cr,Ge,Ta,B,Mo,Re,Nb,Mn,Si,V,Fe,Zr,Hf,Ru,Ir,La,Y,Mg,C".split(",")

        def data_cleaner(data, context, labels):
            messages = [
                {"role": "system", "content": "You are a json master and helpful data cleaner."},
                {"role": "user", "content": DATA_CLEANING_PROMPT_TEMPLATE.format(data=data, context=context)}
            ]
            res = llm_request(messages=messages, remote=True)
            import regex as re
            js = re.findall(r"\{.*\}", res, re.DOTALL)
            js = json.loads(js[0].replace("'", '"'))
            arr = [float(js.get(l, 0)) for l in labels]
            return np.array(arr).reshape(1, -1)

        context = "Please map the raw data into a new json with keys being element symbols and values being only float numbers."
        cleaned = data_cleaner(tab, context, input_labels)
        if scaler is not None:
            cleaned = scaler.transform(cleaned)
        res = pipe.predict(cleaned)

        if model_id == "gbc-class":
            return bool(res[0])
        if model_id in ("svr-regressor", "gbr-liquidus", "svr-solidus"):
            return {"value": f"{res[0]:.2f}", "unit": "℃"}
        if model_id == "gbr-density":
            return {"value": f"{res[0]:.2f}", "unit": "g/cm3"}
        if model_id == "gbr-size":
            return {"value": f"{res[0]:.2f}", "unit": "mm"}
        if model_id == "gbr-misfit":
            return f"{res[0]:.2f}"
        return {"error": "model not found"}
    except Exception as e:
        logger.error(f"Inference error for {model_id}: {e}")
        return {"error": str(e)}
