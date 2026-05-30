"""Convert STEP files to OpenUSD format."""
import subprocess
from pathlib import Path
from tqdm import tqdm


def convert_step_to_usd(step_path: Path, usd_path: Path):
    """Convert a single STEP file to USD using Omniverse Kit CAD Converter.
    Falls back to OCP mesh export if converter unavailable.
    """
    usd_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["omni_cad_converter", "--input", str(step_path), "--output", str(usd_path)],
            check=True, capture_output=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        _fallback_ocp_convert(step_path, usd_path)


def _fallback_ocp_convert(step_path: Path, usd_path: Path):
    """Fallback: convert STEP to STL via OCP, then to USD via usdcat."""
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(step_path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Failed to read STEP: {step_path}")
    reader.TransferRoots()
    shape = reader.OneShape()

    mesh = BRepMesh_IncrementalMesh(shape, 0.1)
    mesh.Perform()

    stl_path = usd_path.with_suffix(".stl")
    writer = StlAPI_Writer()
    writer.Write(shape, str(stl_path))

    # Convert STL to USD via usdcat (if available)
    try:
        subprocess.run(["usdcat", str(stl_path), "-o", str(usd_path)],
                       check=True, capture_output=True)
        stl_path.unlink()
    except FileNotFoundError:
        # Keep STL as fallback render input
        stl_path.rename(usd_path.with_suffix(".stl"))


def convert_all(step_dir: Path, usd_dir: Path):
    """Convert all STEP files to USD."""
    step_files = sorted(step_dir.rglob("*.step"))
    print(f"Converting {len(step_files)} STEP files to USD")
    failed = []
    for f in tqdm(step_files, desc="Converting STEP→USD"):
        out = usd_dir / f"{f.stem}.usd"
        if out.exists():
            continue
        try:
            convert_step_to_usd(f, out)
        except Exception as e:
            failed.append((f.name, str(e)))
    if failed:
        fail_log = usd_dir / "conversion_failures.txt"
        fail_log.write_text("\n".join(f"{n}: {e}" for n, e in failed))
        print(f"WARNING: {len(failed)} conversions failed. See {fail_log}")
