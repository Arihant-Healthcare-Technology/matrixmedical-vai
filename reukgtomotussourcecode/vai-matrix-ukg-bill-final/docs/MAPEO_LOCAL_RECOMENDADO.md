# Mapeo Local Recomendado para Campos Adicionales

## Problema Identificado

Los campos personalizados (`customFields`) **NO funcionan** en BILL API v3:
- El PATCH con `customFields` devuelve `200 OK`
- Pero el campo **NO se guarda** (no aparece en la respuesta)
- La respuesta solo incluye campos básicos del usuario

## Solución: Mapeo Local

Guardar todos los campos adicionales en un archivo JSON local que mapea `employeeNumber` (UKG) → datos completos incluyendo `billUuid`.

## Estructura del Mapeo

```json
{
  "027603": {
    "billUuid": "usr_57kolfl1m10drb794vk1j2nasg",
    "billId": "VXNlcjozNjQxMDk=",
    "employeeNumber": "027603",
    "email": "[email protected]",
    "firstName": "John",
    "lastName": "Doe",
    "role": "MEMBER",
    "primaryProjectCode": "711",
    "department": "FOPS",
    "terminationDate": null,
    "supervisorEmployeeNumber": "004295",
    "supervisorBillUuid": "usr_xxxxx",
    "directLabor": true,
    "physicalCardEnabled": false,
    "createdAt": "2025-11-20T17:18:56.000+00:00",
    "updatedAt": "2025-11-20T17:18:56.000+00:00"
  }
}
```

## Campos que se guardan en BILL

✅ Estos campos SÍ se guardan en BILL:
- `email` → `email`
- `firstName` → `firstName`
- `lastName` → `lastName`
- `role` → `role`
- `retired` → `retired` (para usuarios inactivos)

## Campos que se guardan SOLO localmente

❌ Estos campos NO se pueden guardar en BILL (guardar localmente):
- `primaryProjectCode` → Project Code
- `Condensed Cost center` → Department
- `terminationDate` → endDate (usar `retired: true` en su lugar)
- `Supervisor` → Manager (si no hay soporte de relación)
- `Direct labor` → Budget (se asigna después, pero el flag se guarda local)
- `Physical Card setting` → (se configura después, pero el flag se guarda local)

## Archivo de Mapeo

**Ubicación**: `data/batch/employee_to_bill_mapping.json`

**Estructura completa**:
```json
{
  "027603": {
    "billUuid": "usr_57kolfl1m10drb794vk1j2nasg",
    "billId": "VXNlcjozNjQxMDk=",
    "ukg": {
      "employeeNumber": "027603",
      "employeeID": "G4A5SM00T030",
      "companyID": "J9A6Y"
    },
    "bill": {
      "email": "[email protected]",
      "firstName": "John",
      "lastName": "Doe",
      "role": "MEMBER",
      "retired": false
    },
    "metadata": {
      "primaryProjectCode": "711",
      "department": "FOPS",
      "terminationDate": null,
      "supervisorEmployeeNumber": "004295",
      "supervisorBillUuid": null,
      "directLabor": true,
      "physicalCardEnabled": false
    },
    "budgets": [
      {
        "budgetUuid": "budget_xxxxx",
        "limit": 1000,
        "recurringLimit": 1000
      }
    ],
    "timestamps": {
      "createdAt": "2025-11-20T17:18:56.000+00:00",
      "updatedAt": "2025-11-20T17:18:56.000+00:00"
    }
  }
}
```

## Ventajas del Mapeo Local

1. **Completo**: Guarda TODOS los campos de UKG, incluso los que BILL no soporta
2. **Trazabilidad**: Mantiene relación entre UKG y BILL
3. **Auditoría**: Timestamps de creación y actualización
4. **Relaciones**: Guarda relaciones de supervisor, budgets, etc.
5. **Búsqueda**: Fácil búsqueda por `employeeNumber` o `billUuid`

## Uso del Mapeo

### Buscar usuario por employeeNumber
```python
mapping = load_mapping()
user_data = mapping.get("027603")
bill_uuid = user_data["billUuid"]
project_code = user_data["metadata"]["primaryProjectCode"]
```

### Buscar supervisor
```python
supervisor_emp_num = user_data["metadata"]["supervisorEmployeeNumber"]
supervisor_data = mapping.get(supervisor_emp_num)
supervisor_bill_uuid = supervisor_data["billUuid"] if supervisor_data else None
```

### Actualizar metadata
```python
mapping["027603"]["metadata"]["primaryProjectCode"] = "712"
mapping["027603"]["updatedAt"] = datetime.now().isoformat()
save_mapping(mapping)
```

## Implementación en el Código

Este mapeo se implementará en:
- `run-bill-batch.py` - Guarda el mapeo después de crear/actualizar usuarios
- `upsert-bill-entity.py` - Lee el mapeo para actualizar relaciones (budgets, managers)

## Nota Final

Aunque BILL no soporte campos personalizados directamente, el mapeo local permite:
- Mantener toda la información de UKG
- Sincronizar cambios desde UKG
- Asignar budgets y otras relaciones usando los UUIDs de BILL
- Consultar información completa cuando sea necesario

