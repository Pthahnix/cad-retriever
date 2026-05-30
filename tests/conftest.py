import pytest
from pathlib import Path
from cad_retriever.config import Config


@pytest.fixture
def config(tmp_path):
    return Config(data_root=tmp_path)
