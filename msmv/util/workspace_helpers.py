import os
import shutil


def setup_workspace(base_dir):
    workspace = os.path.join(base_dir, "workspace")
    os.makedirs(workspace, exist_ok=True)
    return workspace


def clean_workspace(workspace):
    shutil.rmtree(workspace)
