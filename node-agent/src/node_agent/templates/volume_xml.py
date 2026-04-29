from pathlib import Path

from jinja2 import Template

from node_agent.domain.model.desired_state_entities import DesiredDisk

# https://libvirt.org/formatstorage.html#storage-volume-general-metadata
# language=xml
VOL_XML = """
<volume>
    <name>{{ disk.volume_name }}</name>
    <capacity unit="bytes">{{ disk.disk_size_gb * 2**30 }}</capacity>
    <allocation unit="bytes">0</allocation>
    <target>
        <format type='{{ disk.disk_subdriver }}'/>
        <!-- <permissions>
            <mode>0644</mode>
        </permissions> -->
    </target>
    {% if backing_vol_path %}
    <backingStore>
        <path>{{ backing_vol_path }}</path>
        <format type='{{ disk.disk_subdriver }}'/>
    </backingStore>
    {% endif %}
</volume>
"""


def render_volume_xml(config: DesiredDisk, vms_pool_path: Path, bases_pool_path: Path | None) -> str:
    backing_vol_path: str | None = str(bases_pool_path / config.base_volume_name) if bases_pool_path else None
    volume_file_path: str = str(vms_pool_path / config.volume_name)
    return Template(VOL_XML).render(disk=config, backing_vol_path=backing_vol_path, volume_file_path=volume_file_path)
