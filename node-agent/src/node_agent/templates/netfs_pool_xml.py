from jinja2 import Template

from node_agent.domain.model.environment_models import NetFSPoolConfig

# https://libvirt.org/formatstorage.html#storage-pool-xml
# https://libvirt.org/formatstorage.html#storage-pool-namespaces
# language=xml
NETFS_POOL_XML = """
<pool xmlns:fs="http://libvirt.org/schemas/storagepool/fs/1.0" type="netfs">
    <name>{{ pool.name }}</name>
    <source>
        <host name="{{ pool.source_host }}"/>
        <dir path="{{ pool.source_dir }}"/>
        <format type="auto"/>
    </source>
    <target>
        <path>{{ pool.target_path }}</path>
        <!-- <permissions>
            <mode>0755</mode>
            <owner>0</owner>
            <group>0</group>
        </permissions> -->
    </target>
    <fs:mount_opts>
        {% if pool.is_readonly %}
        <fs:option name="ro"/>
        {% endif %}
    </fs:mount_opts>
</pool>
"""


def render_netfs_pool_xml(config: NetFSPoolConfig) -> str:
    return Template(NETFS_POOL_XML).render(pool=config)
