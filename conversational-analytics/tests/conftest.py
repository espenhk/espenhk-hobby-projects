from pathlib import Path

import pytest
from fjordroast.duck import get_connection
from fjordroast.semantic.loader import load_semantic_model

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEMANTIC_MODEL_DIR = PROJECT_ROOT / "semantic_model"


@pytest.fixture(scope="session")
def semantic_model():
    return load_semantic_model(SEMANTIC_MODEL_DIR)


@pytest.fixture(scope="session")
def duck_con():
    con = get_connection()
    yield con
    con.close()
