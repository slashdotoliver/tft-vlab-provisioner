from jinja2 import Template

from node_agent.domain.model.environment_models import NetworkConfig

# https://libvirt.org/formatnetwork.html
# language=xml
NETWORK_XML = """
<network>
    <name>{{ net.name }}</name>

    {% if net.mode == 'nat' %}
    <forward mode='nat'/>
    <bridge name='{{ net.bridge_name }}' stp='on' delay='0'/>

    {% if net.ip_address and net.netmask %}
    <ip address='{{ net.ip_address }}' netmask='{{ net.netmask }}'>
        {% if net.dhcp_start and net.dhcp_end %}
        <dhcp>
            <range start='{{ net.dhcp_start }}' end='{{ net.dhcp_end }}'/>
        </dhcp>
        {% endif %}
    </ip>
    {% endif %}
    {% elif net.mode == 'bridge' %}
    <forward mode='bridge'/>
    <bridge name='{{ net.bridge_name }}'/>
    {% endif %}
</network>
"""


def render_network_xml(config: NetworkConfig) -> str:
    return Template(NETWORK_XML).render(net=config)
