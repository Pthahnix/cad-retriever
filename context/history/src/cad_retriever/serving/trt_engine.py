"""TensorRT engine export and inference for production serving."""
import torch
import numpy as np
from pathlib import Path


def export_to_onnx(encoder, output_path: Path, image_size: int = 224):
    """Export sketch encoder to ONNX for TensorRT compilation."""
    encoder.eval()
    dummy_input = torch.randn(1, 3, image_size, image_size).cuda()
    torch.onnx.export(
        encoder,
        dummy_input,
        str(output_path),
        input_names=["image"],
        output_names=["embedding"],
        dynamic_axes={"image": {0: "batch"}, "embedding": {0: "batch"}},
        opset_version=17,
    )
    print(f"ONNX model exported to {output_path}")


def build_trt_engine(onnx_path: Path, engine_path: Path, fp16: bool = True):
    """Build TensorRT engine from ONNX model.
    Requires: tensorrt Python package installed.
    Run: trtexec --onnx=model.onnx --saveEngine=model.engine --fp16
    """
    import subprocess
    cmd = [
        "trtexec",
        f"--onnx={onnx_path}",
        f"--saveEngine={engine_path}",
        "--minShapes=image:1x3x224x224",
        "--optShapes=image:1x3x224x224",
        "--maxShapes=image:16x3x224x224",
    ]
    if fp16:
        cmd.append("--fp16")
    subprocess.run(cmd, check=True)
    print(f"TensorRT engine saved to {engine_path}")


class TRTInference:
    """TensorRT inference wrapper. Falls back to PyTorch if TRT unavailable."""

    def __init__(self, engine_path: Path | None = None, encoder=None):
        self.trt_available = False
        self.encoder = encoder
        if engine_path and engine_path.exists():
            try:
                import tensorrt as trt
                self._load_engine(engine_path)
                self.trt_available = True
            except ImportError:
                pass

    def _load_engine(self, engine_path: Path):
        import tensorrt as trt
        logger = trt.Logger(trt.Logger.WARNING)
        with open(engine_path, "rb") as f:
            self.engine = trt.Runtime(logger).deserialize_cuda_engine(f.read())
        self.context = self.engine.create_execution_context()

    def infer(self, image_tensor: torch.Tensor) -> np.ndarray:
        if self.trt_available:
            return self._infer_trt(image_tensor)
        with torch.no_grad():
            return self.encoder(image_tensor).cpu().numpy()

    def _infer_trt(self, image_tensor: torch.Tensor) -> np.ndarray:
        batch_size = image_tensor.shape[0]
        self.context.set_input_shape("image", image_tensor.shape)
        output = torch.empty(batch_size, 512, device="cuda")
        self.context.execute_v2([image_tensor.data_ptr(), output.data_ptr()])
        return output.cpu().numpy()
