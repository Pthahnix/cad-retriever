from cad_retriever.config import Config


def test_config_defaults():
    cfg = Config()
    assert cfg.embed_dim == 512
    assert cfg.clip_dim == 768
    assert cfg.num_views == 6
    assert cfg.image_size == 224
    assert cfg.faiss_nlist == 1024
    assert cfg.faiss_nprobe == 64
    assert cfg.lora_rank == 16
    assert cfg.batch_size_phase1 == 1024
    assert cfg.batch_size_phase2 == 512
    assert cfg.lr_phase1 == 1e-3
    assert cfg.lr_phase2 == 5e-4
    assert cfg.temperature == 0.07


def test_config_paths():
    cfg = Config()
    assert cfg.abc_raw_dir.name == "abc_step"
    assert cfg.usd_dir.name == "abc_usd"
    assert cfg.renders_dir.name == "renders"
    assert cfg.edges_dir.name == "edges"
    assert cfg.sketches_dir.name == "sketches"
    assert cfg.embeddings_dir.name == "embeddings"
    assert cfg.index_path.suffix == ".index"
