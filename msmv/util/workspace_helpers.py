import os
import shutil

"""Utility class to manage workspaces"""


class WorkspaceHelpers:
    @staticmethod
    def setup_workspace(base_dir):
        workspace = os.path.join(base_dir, "workspace")
        os.makedirs(workspace, exist_ok=True)
        return workspace

    @staticmethod
    def clean_workspace(workspace):
        shutil.rmtree(workspace)
