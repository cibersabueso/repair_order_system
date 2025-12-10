# Sistema de Gestión de Órdenes de Reparación

Sistema backend desarrollado con FastAPI para administrar el ciclo de vida de órdenes de reparación (Repair Orders) en una red de talleres automotrices.

## Arquitectura

El proyecto implementa **Arquitectura Hexagonal (Ports & Adapters)** con las siguientes capas:

```
src/
├── domain/           # Núcleo de negocio (entidades, value objects, reglas)
├── application/      # Casos de uso y orquestación
└── infrastructure/   # Adaptadores (repositorios, API REST)
```

### Domain Layer

Contiene las reglas de negocio puras, completamente aisladas de frameworks y tecnologías externas:

- **Entities**: `RepairOrder` (aggregate root), `Service`, `Component`, `Authorization`
- **Value Objects**: `Money` con redondeo half-even para precisión monetaria
- **Enums**: `OrderStatus`, `ErrorCode`
- **Events**: `DomainEvent` para trazabilidad de cambios
- **Exceptions**: Excepciones tipadas del dominio
- **Ports**: Interfaces (contratos) para repositorios

### Application Layer

Orquesta los casos de uso sin conocer detalles de infraestructura:

- **CommandHandler**: Procesador de comandos que implementa todas las operaciones
- **DTOs**: Objetos de transferencia para entrada/salida

### Infrastructure Layer

Implementaciones concretas de los puertos definidos en el dominio:

- **InMemoryRepairOrderRepository**: Adaptador de persistencia en memoria
- **FastAPI Router**: Adaptador HTTP para exponer la API REST

## Principios SOLID Aplicados

| Principio | Implementación |
|-----------|----------------|
| **Single Responsibility** | Cada clase tiene una única responsabilidad (ej: `Money` solo maneja valores monetarios) |
| **Open/Closed** | El sistema permite agregar nuevas operaciones sin modificar `CommandHandler` existente |
| **Liskov Substitution** | `InMemoryRepairOrderRepository` puede sustituirse por cualquier implementación de `RepairOrderRepository` |
| **Interface Segregation** | Interfaces pequeñas y específicas (ej: `RepairOrderRepository` solo define operaciones CRUD) |
| **Dependency Inversion** | La capa de aplicación depende de abstracciones (`RepairOrderRepository`), no de implementaciones concretas |

## Máquina de Estados

```
CREATED ──► DIAGNOSED ──► AUTHORIZED ──► IN_PROGRESS ──► COMPLETED ──► DELIVERED
    │            │             │              │               │
    └────────────┴─────────────┴──────────────┴───────────────┘
                              │                     │
                              ▼                     │
                         CANCELLED ◄────────────────┘
                              ▲
                              │
               WAITING_FOR_APPROVAL ◄──── (excede 110%)
                              │
                              └──► AUTHORIZED (re-autorización)
```

## Reglas de Negocio Implementadas

- **R1**: Toda orden inicia en estado `CREATED`
- **R2**: Solo se pueden modificar servicios antes de la autorización
- **R3-R4**: Transiciones de estado validadas
- **R5**: Cálculo de autorización con IVA 16%: `authorized_amount = subtotal × 1.16`
- **R6**: Validación de autorización antes de iniciar trabajo
- **R7**: Control de sobrecostos al 110%: `limit = authorized_amount × 1.10`
- **R8**: Re-autorización cuando se excede el límite
- **R9-R10**: Validaciones de completado y entrega
- **R11**: Cancelación bloquea operaciones posteriores
- **R12**: Precisión monetaria con redondeo half-even

## Instalación

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

## Ejecución

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en `http://localhost:8000`

## Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/commands` | Procesa un lote de comandos |
| POST | `/api/v1/reset` | Reinicia el repositorio |
| GET | `/health` | Health check |

## Ejemplo de Uso

```bash
curl -X POST http://localhost:8000/api/v1/commands \
  -H "Content-Type: application/json" \
  -d '{
    "commands": [
      {
        "op": "CREATE_ORDER",
        "ts": "2025-03-01T09:00:00Z",
        "data": {
          "order_id": "R001",
          "customer": "ACME",
          "vehicle": "ABC-123"
        }
      }
    ]
  }'
```

## Operaciones Soportadas

| Operación | Descripción |
|-----------|-------------|
| `CREATE_ORDER` | Crea una nueva orden |
| `ADD_SERVICE` | Agrega un servicio con componentes |
| `SET_STATE_DIAGNOSED` | Marca el diagnóstico como completo |
| `AUTHORIZE` | Autoriza la orden (calcula IVA) |
| `SET_STATE_IN_PROGRESS` | Inicia el trabajo |
| `SET_REAL_COST` | Registra costo real de un servicio |
| `TRY_COMPLETE` | Intenta completar la orden |
| `REAUTHORIZE` | Re-autoriza con nuevo monto |
| `DELIVER` | Marca como entregada |
| `CANCEL` | Cancela la orden |

## Tests

```bash
pytest tests/ -v
```

### Casos de Prueba Cubiertos

1. Flujo completo hasta `DELIVERED`
2. Excede 110% → `WAITING_FOR_APPROVAL` + error `REQUIRES_REAUTH`
3. Exactamente 110% → Permite completar
4. Re-autorización exitosa
5. Iniciar sin autorización → error `SEQUENCE_ERROR`
6. Modificar tras autorización → error `NOT_ALLOWED_AFTER_AUTHORIZATION`
7. Cancelación de orden
8. Autorizar sin servicios → error `NO_SERVICES`
9. Validación de redondeo half-even

## Estructura del Proyecto

```
repair_order_system/
├── main.py                           # Punto de entrada FastAPI
├── requirements.txt                  # Dependencias
├── README.md                         # Este archivo
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── repair_order.py       # Aggregate root
│   │   │   ├── service.py
│   │   │   ├── component.py
│   │   │   └── authorization.py
│   │   ├── value_objects/
│   │   │   └── money.py              # Value object con half-even
│   │   ├── enums/
│   │   │   ├── order_status.py
│   │   │   └── error_code.py
│   │   ├── events/
│   │   │   └── domain_event.py
│   │   ├── exceptions/
│   │   │   └── domain_exceptions.py
│   │   └── ports/
│   │       └── repositories.py       # Interfaces (ports)
│   ├── application/
│   │   ├── use_cases/
│   │   │   └── command_handler.py    # Procesador de comandos
│   │   └── dtos/
│   │       ├── commands.py
│   │       └── responses.py
│   └── infrastructure/
│       ├── adapters/
│       │   └── in_memory_repository.py
│       └── api/
│           └── router.py             # FastAPI router
└── tests/
    └── test_repair_orders.py         # Tests unitarios e integración
```

## Decisiones de Diseño

1. **Money como Value Object**: Garantiza inmutabilidad y redondeo consistente en todas las operaciones monetarias.

2. **RepairOrder como Aggregate Root**: Encapsula toda la lógica de negocio relacionada con órdenes, servicios y autorizaciones.

3. **Command Pattern**: Cada operación se modela como un comando, facilitando la auditoría y el procesamiento batch.

4. **Domain Events**: Registro automático de todos los cambios de estado para trazabilidad completa.

5. **Excepciones Tipadas**: Cada tipo de error tiene su propia excepción, facilitando el manejo diferenciado.

6. **Inyección de Dependencias**: El repositorio se inyecta en el handler, permitiendo fácil testing y cambio de implementaciones.
