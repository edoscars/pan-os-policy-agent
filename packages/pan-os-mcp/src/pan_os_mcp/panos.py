from panos.firewall import Firewall
from typing import Any
from pydantic import SecretStr
from functools import lru_cache
from pan_os_mcp import config

class FirewallConn:

    def __init__(self, host: str, api_key: SecretStr, vsys: str) -> None:
        self._fw = Firewall(hostname=host, api_key=api_key.get_secret_value(), vsys=vsys)

    @property
    def client(self) -> Firewall:
        return self._fw
    
    def health_check(self) -> dict[str, Any]:
        return self._fw.op("show system info", xml=False)

@lru_cache(maxsize=1)
def get_firewall() -> FirewallConn:
    settings = config.get_settings()
    return FirewallConn(settings.panos_host, settings.panos_api_key, settings.panos_vsys)

if __name__ == "__main__":
    fw = get_firewall()
    print(fw.health_check())
