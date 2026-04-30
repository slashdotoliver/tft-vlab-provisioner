CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ==============================================================================
-- FUNCIONES DE UTILIDAD
-- ==============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- TIPOS DE DATOS
-- ==============================================================================
CREATE TYPE lease_status AS ENUM ('active', 'suspended', 'cancelled', 'completed');
CREATE TYPE lease_actual_vm_state AS ENUM ('pending', 'starting', 'running', 'paused', 'terminating_by_user', 'terminating', 'terminated', 'terminated_by_user', 'error');
CREATE TYPE lease_type AS ENUM ('scheduled', 'on-demand');
CREATE TYPE transaction_type AS ENUM ('deposit', 'lease_reservation', 'lease_extension', 'penalty', 'refund');

-- ==============================================================================
-- TABLAS DE IDENTIDAD, ACCESO Y POLÍTICAS
-- ==============================================================================

CREATE TABLE roles (
    id UUID DEFAULT uuidv7(),
    name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_roles PRIMARY KEY (id),
    CONSTRAINT uq_roles_name UNIQUE (name)
);

CREATE TABLE users (
    id UUID DEFAULT uuidv7(),
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id UUID NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT fk_users_roles FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
);
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- TABLAS DE PROYECTOS
-- ==============================================================================

CREATE TABLE projects (
    id UUID DEFAULT uuidv7(),
    slug VARCHAR(32) NOT NULL,
    name VARCHAR(100) NOT NULL,
    owner_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_projects PRIMARY KEY (id),
    CONSTRAINT uq_projects_slug UNIQUE (slug),
    CONSTRAINT uq_projects_name UNIQUE (name),
    CONSTRAINT fk_projects_owners FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE project_users (
    user_id UUID NOT NULL,
    project_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_project_users PRIMARY KEY (user_id, project_id),
    CONSTRAINT fk_pu_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_pu_projects FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE templates (
    id UUID DEFAULT uuidv7(),
    slug VARCHAR(32) NOT NULL,
    name VARCHAR(100) NOT NULL,
    vcpus INTEGER NOT NULL,
    ram_mb INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    CONSTRAINT pk_templates PRIMARY KEY (id),
    CONSTRAINT uq_templates_slug UNIQUE (slug),
    CONSTRAINT uq_templates_name UNIQUE (name),
    CONSTRAINT chk_templates_vcpus CHECK (vcpus > 0),
    CONSTRAINT chk_templates_ram CHECK (ram_mb >= 1)
);

CREATE TABLE template_disks (
    id UUID DEFAULT uuidv7(),
    template_id UUID NOT NULL,
    base_volume_path VARCHAR(255) NOT NULL,
    disk_size_gb INTEGER NOT NULL,
    boot_order INTEGER NOT NULL,
    target_bus VARCHAR(20) DEFAULT 'virtio',
    disk_driver VARCHAR(20) DEFAULT 'qemu',
    disk_subdriver VARCHAR(20) DEFAULT 'qcow2',
    CONSTRAINT pk_template_disks PRIMARY KEY (id),
    CONSTRAINT fk_td_templates FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE,
    CONSTRAINT chk_td_size CHECK (disk_size_gb > 0)
);

CREATE TABLE template_interfaces (
    id UUID DEFAULT uuidv7(),
    template_id UUID NOT NULL,
    network_type VARCHAR(50) NOT NULL DEFAULT 'nat',
    bridge_name VARCHAR(50) NOT NULL,
    model_type VARCHAR(20) DEFAULT 'virtio',
    CONSTRAINT pk_template_interfaces PRIMARY KEY (id),
    CONSTRAINT fk_tn_templates FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
);

CREATE TABLE project_templates (
    project_id UUID NOT NULL,
    template_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_tenant_templates PRIMARY KEY (project_id, template_id),
    CONSTRAINT fk_tt_tenants FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_tt_templates FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
);

-- ==============================================================================
-- TABLAS DE INFRAESTRUCTURA Y RESERVAS
-- ==============================================================================

CREATE TABLE nodes (
    id VARCHAR(100) NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    total_cpus INTEGER NOT NULL,
    total_ram_mb INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_nodes PRIMARY KEY (id),
    CONSTRAINT uq_nodes_hostname UNIQUE (hostname),
    CONSTRAINT chk_nodes_total_cpus CHECK (total_cpus > 0),
    CONSTRAINT chk_nodes_total_ram CHECK (total_ram_mb > 0)
);
CREATE TRIGGER update_nodes_updated_at BEFORE UPDATE ON nodes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE leases (
    id UUID DEFAULT uuidv7(),
    domain_uuid UUID NOT NULL,
    user_id UUID NOT NULL,
    node_id VARCHAR(100) NOT NULL,
    template_id UUID NOT NULL,
    time_range TSTZRANGE NOT NULL,
    lease_status lease_status NOT NULL DEFAULT 'active',
    actual_state lease_actual_vm_state DEFAULT 'pending',
    type lease_type NOT NULL,
    is_permanent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    instructions TEXT,
    CONSTRAINT pk_leases PRIMARY KEY (id),
    CONSTRAINT fk_leases_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_leases_nodes FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE RESTRICT,
    CONSTRAINT fk_leases_templates FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE RESTRICT,
    CONSTRAINT chk_leases_time_range CHECK (upper(time_range) > lower(time_range))
);
CREATE TRIGGER update_leases_updated_at BEFORE UPDATE ON leases FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE lease_interfaces (
    id UUID DEFAULT uuidv7(),
    lease_id UUID NOT NULL,
    template_interface_id UUID NOT NULL,
    mac_address VARCHAR(17) NOT NULL,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_lease_interfaces PRIMARY KEY (id),
    CONSTRAINT fk_li_leases FOREIGN KEY (lease_id) REFERENCES leases(id) ON DELETE CASCADE,
    CONSTRAINT fk_li_template_interfaces FOREIGN KEY (template_interface_id) REFERENCES template_interfaces(id) ON DELETE RESTRICT,
    CONSTRAINT uq_li_mac_address UNIQUE (mac_address)
);

CREATE TABLE lease_disks (
    id UUID DEFAULT uuidv7(),
    lease_id UUID NOT NULL,
    template_disk_id UUID NOT NULL,
    volume_path VARCHAR(255) NOT NULL,
    target_dev VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_lease_disks PRIMARY KEY (id),
    CONSTRAINT fk_ld_leases FOREIGN KEY (lease_id) REFERENCES leases(id) ON DELETE CASCADE,
    CONSTRAINT fk_ld_template_disks FOREIGN KEY (template_disk_id) REFERENCES template_disks(id) ON DELETE RESTRICT
);

-- ==============================================================================
-- ÍNDICES DE OPTIMIZACIÓN
-- ==============================================================================

CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_project_users_project_id ON project_users(project_id);
CREATE INDEX idx_template_disks_template_id ON template_disks(template_id);
CREATE INDEX idx_template_interfaces_template_id ON template_interfaces(template_id);
CREATE INDEX idx_project_templates_project_id ON project_templates(project_id);
CREATE INDEX idx_leases_user_id ON leases(user_id);
CREATE INDEX idx_leases_node_id ON leases(node_id);
CREATE INDEX idx_leases_template_id ON leases(template_id);
CREATE INDEX idx_lease_interfaces_lease_id ON lease_interfaces(lease_id);
CREATE INDEX idx_lease_disks_lease_id ON lease_disks(lease_id);

CREATE INDEX idx_leases_time_range_gist ON leases USING GIST (time_range);
CREATE INDEX idx_leases_actual_state ON leases(actual_state);
CREATE INDEX idx_nodes_is_active ON nodes(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_lease_interfaces_mac ON lease_interfaces(mac_address);
-- CREATE INDEX idx_point_transactions_wallet_id ON point_transactions(wallet_id);
-- CREATE INDEX idx_point_transactions_lease_id ON point_transactions(lease_id);

-- ==============================================================================
-- NOTIFICACIONES
-- ==============================================================================
CREATE OR REPLACE FUNCTION notify_daemon_on_lifecycle_change()
RETURNS TRIGGER AS $$
DECLARE
    channel_name TEXT;
    payload TEXT;
BEGIN
    IF NEW.lease_status IS DISTINCT FROM OLD.lease_status THEN
        channel_name := 'events_' || NEW.node_id;
        payload := json_build_object(
            'event_type', 'lease_status_changed',
            'lease_id', NEW.id,
            'new_status', NEW.lease_status
        )::text;
        PERFORM pg_notify(channel_name, payload);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_notify_on_lease_update
AFTER UPDATE ON leases
FOR EACH ROW EXECUTE FUNCTION notify_daemon_on_lifecycle_change();

