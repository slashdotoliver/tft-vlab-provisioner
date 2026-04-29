from pathlib import Path

from jinja2 import Template

from node_agent.domain.model.desired_state_entities import DesiredVirtualMachine

# https://libvirt.org/formatdomain.html
# language=xml
DOMAIN_XML = """
<domain type="kvm">
    <name>{{ vm.lease_id }}</name>
    <uuid>{{ vm.domain_uuid }}</uuid>

    <memory unit="KiB">{{ vm.ram_mb * 1024 }}</memory>
    <vcpu placement="static">{{ vm.vcpus }}</vcpu>

    <os>
        <type arch="x86_64" machine="q35">hvm</type>
        <boot dev="hd"/>
    </os>

    <features>
        <acpi/>
        <apic/>
    </features>

    <cpu mode="host-model" check="partial"/>

    <on_poweroff>destroy</on_poweroff>
    <on_reboot>restart</on_reboot>
    <on_crash>destroy</on_crash>

    <devices>
        {% if emulator_path %}
        <emulator>{{ emulator_path }}</emulator>
        {% endif %}

        {% for disk in vm.disks %}
        <disk type="file" device="disk">
            <driver name="{{ disk.disk_driver }}" type="{{ disk.disk_subdriver }}"/>
            <source file="{{ vms_pool_path }}/{{ disk.volume_name }}"/>
            <target dev="{{ disk.target_dev }}" bus="{{ disk.target_bus }}"/>

            {% if disk.base_volume_name %}
            <backingStore type="file">
                <format type="{{ disk.disk_subdriver }}"/>
                <source file="{{ bases_pool_path }}/{{ disk.base_volume_name }}"/>
            </backingStore>
            {% else %}
            <backingStore/>
            {% endif %}
        </disk>
        {% endfor %}

        {% for net in vm.networks %}
        {% if net.network_type == 'bridge' %}
        <interface type="bridge">
            <mac address="{{ net.mac_address }}"/>
            <source bridge="{{ net.bridge_name }}"/>
            <model type="{{ net.model_type }}"/>
        </interface>
        {% elif net.network_type == 'nat' %}
        <interface type="network">
            <mac address="{{ net.mac_address }}"/>
            <source network="{{ net.bridge_name }}"/>
            <model type="{{ net.model_type }}"/>
        </interface>
        {% endif %}
        {% endfor %}

        <serial type="pty">
            <target type="isa-serial" port="0"/>
        </serial>

        <console type="pty">
            <target type="serial" port="0"/>
        </console>

        <video>
            <model type="virtio" heads="1" primary="yes"/>
        </video>

        <channel type='unix'>
            <target type='virtio' name='org.qemu.guest_agent.0'/>
            <address type='virtio-serial' controller='0' bus='0' port='1'/>
        </channel>

        <rng model="virtio">
            <backend model="random">/dev/urandom</backend>
        </rng>

        <controller type="usb" model="none"/>
        <memballoon model="none"/>
    </devices>
</domain>
"""


def render_domain_xml(
    vm_spec: DesiredVirtualMachine, bases_pool_path: Path, vms_pool_path: Path, emulator_path: str | None = None
) -> str:
    """Renders the Libvirt DOMAIN XML based on the desired state."""
    return Template(DOMAIN_XML).render(
        vm=vm_spec,
        bases_pool_path=str(bases_pool_path),
        vms_pool_path=str(vms_pool_path),
        emulator_path=emulator_path,
    )
