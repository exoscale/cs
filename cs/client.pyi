from typing import Any, Dict, List, Optional, Union

PY2: bool
text_type = str
string_type = str
integer_types = int
binary_type = bytes
TIMEOUT: int
PAGE_SIZE: int
POLL_INTERVAL: float
EXPIRATION: Any
EXPIRES_FORMAT: str
REQUIRED_CONFIG_KEYS: Any
ALLOWED_CONFIG_KEYS: Any
DEFAULT_CONFIG: Any
PENDING: int
SUCCESS: int
FAILURE: int


def cs_encode(s: Union[str, bytes]) -> str:
    ...


def transform(params: Dict[str, Any]) -> None:
    ...


class CloudStackException(Exception):
    response: Any = ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        ...


class CloudStack:
    verify: Union[str, bool] = ...
    endpoint: str = ...
    key: str = ...
    secret: str = ...
    timeout: Any = ...
    method: Optional[str] = ...
    cert: Optional[str] = ...
    name: Optional[str] = ...
    retry: int = ...
    job_timeout: int = ...
    poll_interval: float = ...
    expiration: Any = ...
    trace: bool = ...

    def __init__(
        self,
        endpoint: str,
        key: str,
        secret: str,
        timeout: Union[str, int] = ...,
        method: Any = ...,
        verify: Optional[str] = ...,
        cert: Optional[str] = ...,
        name: Optional[str] = ...,
        retry: Union[str, int] = ...,
        job_timeout: Optional[int] = ...,
        poll_interval: Any = ...,
        expiration: Any = ...,
        trace: bool = ...,
        dangerous_no_tls_verify: bool = ...,
    ) -> None:
        ...

    def __getattr__(self, command: str) -> Any:
        ...

    def _request(
        self,
        command: Dict[str, str],
        json: bool,
        opcode_name: str,
        fetch_list: bool,
        headers: Optional[Dict],
        **params: Any
    ) -> Union[Dict, List[Dict]]:
        ...

    def _jobresult(
        self,
        jobid: str,
        json: bool,
        headers: Optional[Dict]
    ) -> Dict:
        ...


def read_config_from_ini(ini_group: Optional[str] = ...) -> Dict[str, Any]:
    ...


def read_config(ini_group: Optional[str] = ...) -> Dict[str, Any]:
    ...
