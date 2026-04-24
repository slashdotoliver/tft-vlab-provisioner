from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSTZRANGE, Range
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase): ...


class TemplateModel(Base):
    __tablename__ = "templates"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    vcpus: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)

    disks: Mapped[list[TemplateDiskModel]] = relationship()
    network_interfaces: Mapped[list[TemplateNetworkInterfaceModel]] = relationship()


class TemplateDiskModel(Base):
    __tablename__ = "template_disks"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("templates.id", ondelete="CASCADE"))
    base_volume_path: Mapped[str] = mapped_column(String(255))
    disk_size_gb: Mapped[int] = mapped_column(Integer)
    boot_order: Mapped[int] = mapped_column(Integer)
    target_bus: Mapped[str] = mapped_column(String(20), default="virtio")
    disk_driver: Mapped[str] = mapped_column(String(20), default="qemu")
    disk_subdriver: Mapped[str] = mapped_column(String(20), default="qcow2")


class TemplateNetworkInterfaceModel(Base):
    __tablename__ = "template_interfaces"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("templates.id", ondelete="CASCADE"))
    network_type: Mapped[str] = mapped_column(String(50))
    bridge_name: Mapped[str] = mapped_column(String(50))
    model_type: Mapped[str] = mapped_column(String(20), default="virtio")


class LeaseModel(Base):
    __tablename__ = "leases"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    domain_uuid: Mapped[UUID] = mapped_column()
    user_id: Mapped[UUID] = mapped_column()
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"))
    template_id: Mapped[UUID] = mapped_column(ForeignKey("templates.id"))
    time_range: Mapped[Range] = mapped_column(TSTZRANGE)
    lease_status: Mapped[str] = mapped_column(String)
    actual_state: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    is_permanent: Mapped[bool] = mapped_column(Boolean, default=False)
    instructions: Mapped[str | None] = mapped_column(Text)

    template: Mapped[TemplateModel] = relationship()
    interfaces: Mapped[list[LeaseNetworkInterfaceModel]] = relationship()
    disks: Mapped[list[LeaseDiskModel]] = relationship()


class LeaseNetworkInterfaceModel(Base):
    __tablename__ = "lease_interfaces"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    lease_id: Mapped[UUID] = mapped_column(ForeignKey("leases.id", ondelete="CASCADE"))
    template_interface_id: Mapped[UUID] = mapped_column(ForeignKey("template_interfaces.id", ondelete="RESTRICT"))
    mac_address: Mapped[str] = mapped_column(String(17), unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))

    template_interface: Mapped[TemplateNetworkInterfaceModel] = relationship()


class LeaseDiskModel(Base):
    __tablename__ = "lease_disks"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    lease_id: Mapped[UUID] = mapped_column(ForeignKey("leases.id", ondelete="CASCADE"))
    template_disk_id: Mapped[UUID] = mapped_column(ForeignKey("template_disks.id", ondelete="RESTRICT"))
    volume_path: Mapped[str] = mapped_column(String(255))
    target_dev: Mapped[str] = mapped_column(String(20))

    template_disk: Mapped[TemplateDiskModel] = relationship()
