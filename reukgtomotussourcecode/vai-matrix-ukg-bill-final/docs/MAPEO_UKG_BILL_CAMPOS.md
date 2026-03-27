# Mapeo UKG → BILL: Campos Disponibles

## Campos que SÍ se pueden mapear directamente en BILL API

Estos campos están **documentados y soportados** en la API de BILL para usuarios:

| Campo UKG | Campo BILL | Estado | Notas |
|-----------|------------|-------|-------|
| `emailAddress` | `email` | ✅ **SÍ** | Requerido, se envía en POST |
| `firstName` | `firstName` | ✅ **SÍ** | Requerido, se envía en POST |
| `lastName` | `lastName` | ✅ **SÍ** | Requerido, se envía en POST |
| `role` | `role` | ✅ **SÍ** | Requerido, valores: ADMIN, AUDITOR, BOOKKEEPER, MEMBER, NO_ACCESS |
| `terminationDate` | `retired` | ❌ **NO FUNCIONA** | POST ignora `retired: true`, PATCH no actualiza. Usar DELETE o mapeo local |

**Total: 4 campos completos + 1 parcial**

---

## Campos que NO se pueden mapear directamente en BILL API

Estos campos **NO están soportados** en la API de BILL para usuarios:

| Campo UKG | Campo BILL | Estado | Razón |
|-----------|------------|-------|-------|
| `employeeNumber` | `id` | ❌ **NO** | BILL genera su propio `uuid` e `id` automáticamente |
| `primaryProjectCode` | `Project Code` | ❌ **NO** | CustomFields son solo para transacciones, no usuarios |
| `Supervisor` | `Manager` | ❌ **NO** | No hay soporte de relación manager en la API de usuarios |
| - | `Physical Card setting` | ❌ **NO** | Requiere configuración separada, no es campo de usuario |
| `Direct labor` (checkbox) | `Budget` | ⚠️ **PARCIAL** | Se asigna usuario a budget después, pero el flag no se guarda |
| `Condensed Cost center` | `Department` | ❌ **NO** | CustomFields son solo para transacciones, no usuarios |
| `terminationDate` | `endDate` | ❌ **NO** | No existe campo `endDate`, solo `retired: true/false` |

**Total: 6 campos no soportados + 1 parcial**

---

## Resumen

### ✅ Campos que se envían en POST /v3/spend/users:
```json
{
  "email": "[email protected]",        // ← emailAddress
  "firstName": "John",                 // ← firstName
  "lastName": "Doe",                   // ← lastName
  "role": "MEMBER"                     // ← role
}
```

### ⚠️ Campo parcial (terminationDate):
```json
{
  "retired": true  // ← Si terminationDate existe, usar retired: true
                   //    NO se guarda la fecha exacta
}
```

### ❌ Campos que NO se pueden enviar:
- `id` (BILL lo genera)
- `projectCode` (no soportado)
- `manager` (no soportado)
- `endDate` (no existe, solo `retired`)
- `department` (no soportado)
- `physicalCard` (no es campo de usuario)
- `budget` (se asigna después, pero no es campo del usuario)

---

## Solución: Mapeo Local

Para los campos que NO se pueden mapear directamente, usar **mapeo local**:

```json
{
  "027603": {
    "billUuid": "usr_57kolfl1m10drb794vk1j2nasg",
    "billId": "VXNlcjozNjQxMDk=",
    "employeeNumber": "027603",              // ← Guardar localmente
    "primaryProjectCode": "711",             // ← Guardar localmente
    "department": "FOPS",                    // ← Guardar localmente
    "supervisorEmployeeNumber": "004295",   // ← Guardar localmente
    "directLabor": true,                     // ← Guardar localmente
    "physicalCardEnabled": false,            // ← Guardar localmente
    "terminationDate": "2025-12-31"          // ← Guardar localmente (fecha completa)
  }
}
```

---

## Flujo Recomendado

### Paso 1: Crear usuario en BILL (solo campos soportados)
```bash
POST /v3/spend/users
{
  "email": "[email protected]",
  "firstName": "John",
  "lastName": "Doe",
  "role": "MEMBER"
}
```

### Paso 2: Guardar mapeo local (todos los campos)
```json
{
  "027603": {
    "billUuid": "usr_xxxxx",
    "employeeNumber": "027603",
    "primaryProjectCode": "711",
    "department": "FOPS",
    "supervisorEmployeeNumber": "004295",
    "directLabor": true,
    "terminationDate": "2025-12-31"
  }
}
```

### Paso 3: Asignar a Budget (si aplica)
```bash
PUT /v3/spend/budgets/{budgetUuid}/members/{userUuid}
{
  "limit": 1000,
  "recurringLimit": 1000
}
```

### Paso 4: Configurar Physical Card (si aplica)
```bash
# Verificar endpoint de tarjetas en documentación
POST /v3/spend/cards
{
  "userUuid": "usr_xxxxx",
  "type": "PHYSICAL"
}
```

---

## Conclusión

**Solo 4 campos se pueden mapear directamente:**
1. ✅ `emailAddress` → `email`
2. ✅ `firstName` → `firstName`
3. ✅ `firstName` → `lastName`
4. ✅ `role` → `role`

**Todos los demás campos requieren mapeo local o configuración adicional.**

