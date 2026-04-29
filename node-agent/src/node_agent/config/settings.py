import logging
import tomllib
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from node_agent.domain.attempt import raises
from node_agent.domain.model.environment_models import EnvironmentConfig, NetFSPoolConfig, NetworkConfig


class DatabaseConfigModel(BaseModel):
    user: str
    password: str
    host: str = "localhost"
    port: int = 5432
    db_name: str = "lab_db"

    @property
    def sqlalchemy_url(self) -> str:
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"

    @property
    def psycopg_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}?keepalives=1&keepalives_idle=5&keepalives_interval=2&keepalives_count=3"


class NetworkConfigModel(BaseModel):
    name: str
    mode: Literal["nat", "bridge"]
    bridge_name: str
    ip_address: str | None = None
    netmask: str | None = None
    dhcp_start: str | None = None
    dhcp_end: str | None = None

    def to_domain(self) -> NetworkConfig:
        return NetworkConfig(**self.model_dump())


class NetFSPoolConfigModel(BaseModel):
    name: str
    source_host: str
    source_dir: str
    target_path: str
    is_readonly: bool = False

    def to_domain(self) -> NetFSPoolConfig:
        return NetFSPoolConfig(**self.model_dump())


class EnvironmentConfigModel(BaseModel):
    required_arch: str = "x86_64"
    requires_hw_virtualization: bool = True
    requires_nested_virtualization: bool = True

    def to_domain(self) -> EnvironmentConfig:
        return EnvironmentConfig(**self.model_dump())

class ConfigParseError(Exception):
    ...


class AppConfig(BaseModel):
    service_name: str = "node-agent"
    node_name: str
    logging_level: int = logging.INFO
    libvirt_uri: str = "qemu:///system"

    database: DatabaseConfigModel
    environment: EnvironmentConfigModel = Field(default_factory=EnvironmentConfigModel)

    main_network: NetworkConfigModel
    templates_pool: NetFSPoolConfigModel
    store_pool: NetFSPoolConfigModel

    networks: list[NetworkConfigModel] = Field(default_factory=list)
    netfs_pools: list[NetFSPoolConfigModel] = Field(default_factory=list)

    @field_validator("logging_level", mode="before")
    @classmethod
    def parse_logging_level(cls, value):
        if isinstance(value, str):
            levels = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARN": logging.WARNING,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            return levels.get(value.upper(), logging.INFO)
        return value

    def get_all_networks(self) -> tuple[NetworkConfig, ...]:
        all_nets = [self.main_network] + self.networks
        return tuple(net.to_domain() for net in all_nets)

    def get_all_pools(self) -> tuple[NetFSPoolConfig, ...]:
        all_pools = [self.templates_pool, self.store_pool] + self.netfs_pools
        return tuple(pool.to_domain() for pool in all_pools)

    @classmethod
    @raises(ConfigParseError)
    def from_toml(cls, path: str) -> AppConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**data)
