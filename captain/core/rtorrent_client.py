import xmlrpc.client
from pathlib import Path
from typing import TypeAlias
from urllib import parse

InfoHashType: TypeAlias = str


def _parse_magnet_link(magnet_link: str) -> dict[str, str]:
    return dict(parse.parse_qsl(parse.urlsplit(magnet_link).query))


def extract_magnet_link_info_hash(magnet_link: str) -> InfoHashType:
    urn_btih_prefix = "urn:btih:"
    xt = _parse_magnet_link(magnet_link)["xt"]
    assert xt.startswith(urn_btih_prefix)
    return xt[len(urn_btih_prefix) :]


class Torrent:
    def __init__(self, client: xmlrpc.client.ServerProxy, info_hash: InfoHashType):
        self._client = client
        self._info_hash = info_hash

    @property
    def info_hash(self) -> InfoHashType:
        return self._info_hash

    def exists(self) -> bool:
        try:
            self._client.d.hash(self._info_hash)
            return True
        except xmlrpc.client.Fault as e:
            if "could not find info-hash" in str(e).lower():
                return False
            raise

    def start(self) -> None:
        self._client.d.start(self.info_hash)

    def stop(self) -> None:
        self._client.d.stop(self.info_hash)

    def erase(self) -> None:
        self._client.d.erase(self.info_hash)

    @property
    def name(self) -> str:
        return self._client.d.name(self._info_hash)

    @property
    def is_multi_file(self) -> bool:
        return bool(self._client.d.is_multi_file(self._info_hash))

    @property
    def is_meta(self) -> bool:
        return bool(self._client.d.is_meta(self._info_hash))

    @property
    def is_complete(self) -> bool:
        return bool(self._client.d.complete(self._info_hash))

    @property
    def base_path(self) -> Path:
        return Path(self._client.d.base_path(self._info_hash))

    @property
    def size_bytes(self) -> int:
        return self._client.d.size_bytes(self._info_hash)

    @property
    def download_rate(self) -> int:
        return self._client.d.down.rate(self._info_hash)

    @property
    def completed_bytes(self) -> int:
        return self._client.d.completed_bytes(self._info_hash)


class RtorrentClient:
    def __init__(self, rtorrent_uri: str):
        self._client = xmlrpc.client.ServerProxy(rtorrent_uri)

    def start_torrent(self, magnet_link: str) -> Torrent:
        info_hash = extract_magnet_link_info_hash(magnet_link)
        self._client.load.start("", magnet_link)
        return Torrent(self._client, info_hash)
