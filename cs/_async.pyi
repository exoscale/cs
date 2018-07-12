from . import CloudStack
from .client import transform
from typing import Any

class AIOCloudStack(CloudStack):
    def __getattr__(self, command: str) -> Any: ...
