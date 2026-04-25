import logging

from libvirt import VIR_ERR_NO_STORAGE_POOL, VIR_STORAGE_POOL_BUILD_NEW, libvirtError, virConnect, virStoragePool

from node_agent.application.ports.pool_storage_provider import PoolStorageProviderPort
from node_agent.domain.attempt import attempt
from node_agent.domain.model.environment_models import NetFSPoolConfig
from node_agent.domain.model.result import Result
from node_agent.templates.netfs_pool_xml import render_netfs_pool_xml

LOGGER = logging.getLogger(__name__)


class LibvirtPoolStorageAdapter(PoolStorageProviderPort):
    def __init__(self, connection: virConnect):
        self._connection = connection

    def initialize_pool(self, config: NetFSPoolConfig) -> Result[None, Exception]:
        def _ensure_running(pool: virStoragePool) -> Result[None, Exception]:
            def _do_ensure() -> None:
                if not pool.isActive():
                    LOGGER.info(f"Starting pool '{config.name}'...")
                    pool.create()
                if not pool.autostart():
                    pool.setAutostart(1)

            return attempt(_do_ensure, (Exception,))

        return (
            self._get_pool(config)
            .map_error(lambda error: self._create_if_missing(config, error))
            .flat_map(_ensure_running)
        )

    def _get_pool(self, config: NetFSPoolConfig) -> Result[virStoragePool, Exception]:
        return attempt(lambda: self._connection.storagePoolLookupByName(config.name), exceptions=(libvirtError,))

    def _create_if_missing(self, config: NetFSPoolConfig, error: Exception) -> Result[virStoragePool, Exception]:
        if isinstance(error, libvirtError) and error.get_error_code() == VIR_ERR_NO_STORAGE_POOL:
            LOGGER.info(f"Storage pool '{config.name}' not found. Creating pool...")
            return self._define_and_build_pool(config)

        LOGGER.error(f"Unexpected error looking up storage pool '{config.name}'")
        return Result.failure(error)

    def _define_and_build_pool(self, config: NetFSPoolConfig) -> Result[virStoragePool, Exception]:
        def _do_define_and_build() -> virStoragePool:
            pool = self._connection.storagePoolDefineXML(render_netfs_pool_xml(config), 0)
            if pool is None:
                raise Exception(f"Libvirt returned None while defining pool '{config.name}'")

            LOGGER.debug(f"Building target path for storage pool '{config.name}'...")
            pool.build(VIR_STORAGE_POOL_BUILD_NEW)
            return pool

        return attempt(_do_define_and_build, (Exception,))
