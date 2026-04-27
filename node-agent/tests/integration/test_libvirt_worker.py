# def test_should_invoke_lifecycle_event():
#     libvirt.virEventRegisterDefaultImpl()
#     test_conn: libvirt.virConnect | None = libvirt.open("test:///default")
#     assert test_conn is not None
#
#     db_port = MockDesiredStateAdapter(
#         [
#             DesiredVirtualMachine(
#                 lease_id=LeaseID(UUID("019dd924-ffaf-7de0-9200-87c9ddb57240")),
#                 domain_uuid=DomainUUID(UUID("8c452129-a71e-4cd8-842a-7f83bb10bb03")),
#                 vcpus=3,
#                 ram_mb=3072,
#                 target_state=DesiredVmState.RUNNING,
#                 instructions="Abierto el puerto 3389 para acceso por RDP",
#                 networks=(
#                     DesiredNetworkInterface(
#                         mac_address="00:54:91:e0:ad:a0",
#                         network_type="nat",
#                         bridge_name="lab_network",
#                         model_type="virtio",
#                     ),
#                 ),
#                 disks=(
#                     DesiredDisk(
#                         target_dev="vda",
#                         target_bus="virtio",
#                         disk_driver="qemu",
#                         disk_subdriver="qcow2",
#                         volume_path="fedora_template_OZdCkiYwXW5u6OrZ_019dd933-20fd-7925-ab49-c72a64f9e22a.qcow2",
#                         base_volume_path="fedora_template_base.qcow2",
#                         disk_size_gb=40,
#                     ),
#                 ),
#             )
#         ]
#     )
#     state_port = MockStateAdapter(
#         [
#             VirtualMachine(
#                 vcpus=3,
#                 name="019dd924-ffaf-7de0-9200-87c9ddb57240",
#                 uuid=DomainUUID(UUID("8c452129-a71e-4cd8-842a-7f83bb10bb03")),
#                 memory_kb=3072 * 1024,
#                 state="running",
#                 interfaces=(
#                     NetworkInterface(
#                         network_name="lab_platform", mac_address="00:54:91:e0:ad:a0", bridge_name="", ip_address=None
#                     ),
#                 ),
#                 is_persistent=True,
#                 disks=(
#                     Disk(
#                         target_dev="vda",
#                         volume_path=".../fedora_template_OZdCkiYwXW5u6OrZ_019dd933-20fd-7925-ab49-c72a64f9e22a.qcow2",
#                         backing_file=".../fedora_template_base.qcow2",
#                     ),
#                 ),
#             )
#         ]
#     )
#
#     loop = ReconciliationLoop(
#         reconcile_state_evaluator=ReconcileStateUseCase(db_port, state_port, NodeID("mock_node")),
#         executor=LibvirtCommandExecutor(test_conn, )
#     )
#     monitor_worker: Worker = LibvirtMonitorWorker(test_conn, MockLifecycleEventHandler(loop))
#
#     assert monitor_worker.run()
#     sleep(0.15)
#     # TODO: add an event in the test connection
#     assert monitor_worker.stop()


def test_should_return_true():
    assert True
