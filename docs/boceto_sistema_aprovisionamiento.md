# Introducción

Este documenta explica el sistema de aprovisionamiento de infraestructura con el objetivo de permitir el alquiler de recursos estáticos distribuidos en varias máquinas físicas Linux. El sistema se encarga de instanciar máquinas virtuales y volúmenes efímeros en base a unas plantillas predefinidas. La finalidad principal es facilitar un entorno donde los profesores puedan gestionar proyectos para sus asignaturas, asignando plantillas de dominios ya preparadas y probadas para que los estudiantes matriculados las utilicen. Para lograr esto sin saturar la infraestructura subyacente, el sistema organiza las peticiones mediante un orquestador que calcula y asegura la disponibilidad futura de los recursos.

# Terminología

* **Aprovisionamiento / Arrendamiento / Alquiler (*Lease*):** Contrato temporal en el que se apuntan y garantizan los recursos computacionales destinados a un dominio durante unas fechas de inicio y final concretas.
* **Arrendamiento Bajo demanda (*Best-effort provisioning*):** Tipo de arrendamiento en el que el usuario intenta solicitar la instanciación inmediata o muy próxima de los recursos. Si hay hueco en ese preciso instante, se otorgan; si no, se rechazan.
* **Arrendamiento en Reserva / Planificado (*Advance Reservation*):** Tipo de arrendamiento en el que el usuario selecciona con antelación (por ejemplo, un día antes) una ventana temporal futura en el calendario a la que se compromete a usar los recursos.
* **Nodo:** Máquina que expone parte de su capacidad total de aprovisionamiento (vCPUs, RAM, almacenamiento y ancho de banda de red) al sistema para alojar los arrendamientos.
* **Máquina virtual / Dominio:** El entorno virtualizado resultante. Se utilizará el término "dominio" derivado de la nomenclatura de libvirt.
* **Instancia / Creación / Definición de un dominio efímero:** Proceso en el que el agente del nodo clona los volúmenes base por NFS hacia volúmenes efímeros, crea las interfaces de red y arranca el dominio. Al finalizar el arrendamiento, todos estos recursos temporales se destruyen irreversiblemente.
* **Sobre-asignación (*Over-committing*):** Capacidad del planificador para derivar lógicamente más recursos totales de loss que tiene físicamente el nodo.
* **Ranura de tiempo (*Slot / Time Quantum*):** Unidad de tiempo mínima y discreta en la que se alinean obligatoriamente todos los arrendamientos (por ejemplo, bloques exactos de 15 o 30 minutos).
* **Asignación temprana (*Early binding*):** Estrategia que consiste en emparejar un arrendamiento con un nodo físico específico en el mismo momento en el que el usuario realiza la reserva.
* **Asignación tardía (*Late-binding*):** Estrategia que consiste en admitir el arrendamiento en el calendario global, pero posponer la elección del nodo físico hasta poco antes de que empiece, permitiendo al sistema adaptarse al estado real del clúster en ese momento.

# Requisitos del sistema

El sistema trabaja sobre varias abstracciones: las **plantillas**, que definen los recursos que un dominio necesita (vCPUs, RAM, almacenamiento e interfaz de red) y que están asociadas a volúmenes base preinstalados; los **arrendamientos** (*leases*), que representan la petición y el uso temporal de estas plantillas; y los **proyectos**, que son las agrupaciones que vinculan plantillas específicas con los usuarios autorizados a instanciarlas.

En la gestión y autorización del sistema se definen tres niveles de roles jerárquicos. Las acciones permitidas funcionan en cascada, donde cada rol superior hereda los permisos del inferior:

1. **Rol 'estudiante' (usuario normal):** Puede consultar los proyectos a los que pertenece y gestionar arrendamientos de las plantillas que tiene disponibles. Puede visualizar su histórico de alquileres, cancelar peticiones pendientes y, una vez tenga un arrendamiento activo, consultar su estado y obtener los datos de conexión (como la IP) para acceder al dominio.
2. **Rol 'profesor':** Tiene la capacidad de crear proyectos y asociar a estos las plantillas predefinidas que se van a usar en un curso. Es el encargado de administrar a los estudiantes matriculados, otorgándoles acceso a los recursos del proyecto.
3. **Rol administrador:** Posee la capacidad total de gestionar al resto de usuarios, crear las plantillas base del sistema y modificar a voluntad todas las políticas y configuraciones del planificador central.

La infraestructura del repositorio se divide en tres módulos interconectados:

* **Módulo agente:** Se ejecuta en cada nodo como un servicio de systemd, escrito en Python utilizando las librerías `libvirt-python` y `sqlalchemy`. Su objetivo es monitorizar el estado estático y dinámico del servidor (recursos totales, dominios definidos, volúmenes, redes). Este módulo lee de la base de datos la tabla de arrendamientos destinados a su nodo específico y se encarga autónomamente de crear y destruir los dominios en base a las fechas acordadas, actualizando en tiempo real el estado de ejecución.
* **Módulo planificador/gestor (Control Plane):** Orquestador central que expone una API RESTFul mediante `fastapi`. Recibe las peticiones de los clientes, verifica las políticas de los usuarios y lee la actualización del estado de los nodos y del calendario para ir tomando las decisiones de admisión y planificación.
* **Interfaz web:** Aplicación web en Angular que actúa como frontend para consumir la API servida por el orquestador.

# Planteamiento del sistema a desarrollar

El planificador decidirá el emparejamiento de los arrendamientos basándose en un cálculo de los recursos que cada nodo puede proporcionar. Los recursos totales de los nodos se consideran estáticos. Asimismo, los arrendamientos son inmutables en su ejecución: no habrá migraciones en caliente entre nodos ni los dominios podrán cambiar de recursos asignados una vez iniciados. Si, por cualquier motivo, el sistema de planificación no lograra cumplir con el arrendamiento justo en el momento de empezarlo, se marcará inmediatamente como suspendido.

Los usuarios podrán elegir dos modalidades de arrendamiento:
* **Arrendamientos con reserva:** Se ubican en el calendario seleccionando con antelación el inicio y el final de la ventana de tiempo.
* **Arrendamientos bajo demanda:** Se solicita al planificador que intente instanciar el dominio con un inicio inmediato o en el *Slot* más próximo disponible.

Para mantener la coherencia, los arrendamientos se rigen por dos campos de estado separados en la base de datos. Uno refleja la perspectiva del planificador y otro refleja la realidad medida por el agente del nodo.

**Estado del ciclo de vida del alquiler (Controlado por el planificador):**
* `active`: El arrendamiento es válido en el calendario y el sistema debe proveer la infraestructura en el tiempo estipulado.
* `suspended`: El planificador no logró asignar a tiempo un nodo con recursos suficientes o falló la orquestación.
* `cancelled`: El usuario propietario ha cancelado el alquiler antes de su ventana de tiempo.
* `completed`: El tiempo estipulado del alquiler ha finalizado (independientemente de que se hayan producido errores reportados por el agente durante la ejecución).

**Estado actual (Controlado por el agente del nodo):**
* `pending`: El arrendamiento no se ha iniciado todavía; está a la espera de su ventana temporal.
* `starting`: El agente está iniciando el dominio, realizando el clonado de volúmenes efímeros y configurando la red virtual.
* `running`: El dominio se ha iniciado correctamente en el hipervisor y está en ejecución.
* `terminating_by_user`: Proceso de destrucción anticipada desencadenado voluntariamente por el usuario.
* `terminating`: Proceso de destrucción desencadenado porque el tiempo del alquiler ha finalizado.
* `terminated`: Liberación de recursos del arrendamiento concluida con éxito tras el fin del tiempo.
* `terminated_by_user`: Limpieza concluida con éxito y producido por la cancelación anticipada del usuario.
* `error`: Se ha producido un fallo que impide que el arrendamiento continúe. El nodo aborta la ejecución y libera los recursos del arrendamiento.

Para garantizar un reparto equitativo de los recursos de hardware, cada arrendamiento descontará una puntuación de consumo al usuario en un intervalo de tiempo determinado (por ejemplo, de forma mensual). Mediante la configuración de políticas aplicadas a los roles, se controlarán los límites de uso de cada usuario en el sistema.

## Políticas

A las configuraciones globales que definen las reglas del orquestador se les denominará **Parámetros del Planificador**. A las configuraciones que se ajustan para controlar el comportamiento y los límites de los usuarios se les llamará **Políticas**. Las políticas se definen a nivel de rol:

* **Límite de Puntos (número):** Cantidad máxima de puntos que un usuario perteneciente a ese rol podrá gastar durante el periodo establecido.
* **Multiplicador de penalización bajo demanda (número):** Factor que incrementa el coste en puntos al solicitar un arrendamiento bajo demanda. Esta política permite penalizar la inmediatez e incentivar la planificación de reservas.
* **Porcentaje máximo de uso de los recursos por este rol (porcentaje):** Límite que define la porción máxima de la infraestructura total que la suma de todos los usuarios de un rol puede acaparar simultáneamente. Su objetivo es garantizar que siempre queden recursos libres para los demás roles.
* **Rango de tiempo de reservas (duración de inicio, duración de final):** Ventana que define el primer y último momento permitido para registrar una reserva en el calendario. Por ejemplo, un rango de `(1 día, 30 días)` obliga a que cualquier reserva se realice con al menos 24 horas de antelación y no más allá del mes siguiente. La duración de inicio debe ser siempre mayor que dos veces el parámetro **Slot**.
* **Tiempo máximo extendible (duración):** Múltiplo del **Slot** que define cuánto tiempo máximo se le permite a un usuario prolongar un arrendamiento que ya ha iniciado. Esta extensión consumirá puntos a la tasa de un alquiler bajo demanda, y solo se concederá si el planificador demuestra que no se invaden reservas futuras en ese mismo nodo.

## Parámetros del Planificador

Estas configuraciones son independientes de los roles de usuario. Definen las configuraciones que permiten al planificador discretizar el tiempo continuo y realizar los cálculos de asignación.

* **Slot (duración):** Expresado en minutos, define el bloque mínimo e indivisible de tiempo para planificar. Todos los arrendamientos estarán alineados a este bloque. Debe ser un divisor exacto de 60 (ej. 10, 15, 30 minutos). Si el Slot es de 15, un alquiler siempre abarcará intervalos como 14:15 a 15:00. La duración de cualquier arrendamiento será siempre un múltiplo de este Slot.
* **Rango de tiempo de reasignación (duración de inicio, duración de final):** Ventana de tiempo en la que el orquestador puede reasignar los arrendamientos pendientes. Por ejemplo, el rango `(5 minutos, 2 días)` indica que el sistema intentará buscar un nodo definitivo para todos los alquileres que comiencen en las próximas 48 horas, pero detendrá los intentos de reasignación 5 minutos antes del inicio exacto para no generar conflictos con el agente.
* **Intervalo entre replanificaciones (duración):** Múltiplo del Slot que determina la frecuencia exacta con la que el planificador despierta su bucle reactivo periódico para aplicar la lógica de asignación.

# Sistema de Planificación

El sistema de planificación tiene en cuenta los parámetros globales y las políticas definidas por rol para determinar la posibilidad de realizar un arrendamiento (su admisión) y para aplicar las estrategias de replanificación sobre los arrendamientos existentes. Dado que todos los arrendamientos están alineados en intervalos basados en el Slot, el planificador analiza cada segmento discreto de tiempo de forma independiente en su toma de decisiones.

Las métricas de uso de los recursos de un nodo en un Slot determinado se obtienen sumando cada tipo de recurso monitorizado (vCPUs, RAM, almacenamiento) correspondiente a todas las plantillas de los arrendamientos activos en ese nodo durante dicho Slot. A modo de ejemplo, supóngase que el nodo 1 tiene dos alquileres activos: un arrendamiento de 12:00 a 14:00 con una plantilla asociada de 2 vCPUs, 2 GB de RAM y 40 GB de almacenamiento, y otro arrendamiento de 13:00 a 14:00 con la misma plantilla. Si el valor del Slot es de 1 hora, las métricas de uso proyectadas para el nodo 1 son:
* Slot de 12:00 a 13:00 $\rightarrow$ 2 vCPUs, 2 GB de RAM, 40 GB.
* Slot de 13:00 a 14:00 $\rightarrow$ 4 vCPUs, 4 GB de RAM, 80 GB.

El funcionamiento del sistema de planificación se divide en tres niveles de evaluación:

**1. Control de admisión (Síncrono)**
Actúa en el momento en que la API recibe una petición de arrendamiento. Primero verifica el saldo de puntos del usuario y las políticas de su rol. Seguidamente, suma las proyecciones de las métricas de uso de todos los nodos y comprueba si existe al menos un nodo en todo el clúster capaz de alojar la plantilla durante todos los Slots que abarca la petición. Si el cálculo es viable, el arrendamiento se aprueba y se guarda en la base de datos en estado `pending`.

**2. Bucle de Replanificación (Asíncrono)**
De manera periódica, se reevalúan todos los arrendamientos activos que no hayan iniciado todavía y cuya fecha de comienzo se encuentre dentro del rango de tiempo de reasignación. El objetivo de este bucle es reevaluar el nodo físico asignado en base a la estrategia que la replanificación esté utilizando. Por cada uno de estos alquileres en evaluación, este nivel solicita al tercer nivel que determine el mejor nodo posible para el arrendamiento.

**3. Algoritmo de Asignación / Empaquetado**
Por cada arrendamiento a replanificar, este nivel analiza la lista completa de nodos. Primero, aplica un filtro descartando aquellos nodos que no tengan capacidad libre suficiente en todos y cada uno de los Slots que dura el arrendamiento. Sobre los nodos supervivientes, aplica una estrategia de puntuación. Si se emplea una estrategia de balanceo de carga, se evalúa la proporción de recursos libres por Slot; la puntuación agregada del nodo será el *mínimo* de esas puntuaciones (evaluando así el nodo en base a su Slot más crítico o con menos recursos disponibles). Finalmente, se ejecuta la actualización en base de datos vinculando el arrendamiento al nodo cuya puntuación final haya sido la más favorable.
