"""One-off config sanity check. OK to delete after running."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import config  # noqa: E402

print("CATVTON_PYTHON =", config.CATVTON_PYTHON)
print("python exists  =", os.path.exists(config.CATVTON_PYTHON))
print("CATVTON_BASE   =", config.CATVTON_BASE_MODEL_PATH)
print("CATVTON_RESUME =", config.CATVTON_RESUME_PATH)
print("base local?    =", os.path.exists(config.CATVTON_BASE_MODEL_PATH))
print("resume local?  =", os.path.exists(config.CATVTON_RESUME_PATH))
print("first 3 parts  :", config.CATVTON_COMMAND_TEMPLATE[:3])
print("USE_CONDA_WRAPPER =", config.USE_CONDA_WRAPPER)
