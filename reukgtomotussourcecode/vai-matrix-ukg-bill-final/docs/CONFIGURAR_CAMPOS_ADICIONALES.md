# Configuración de Campos Adicionales UKG → BILL

## Campos Básicos (se envían en POST inicial)

Estos campos se pueden enviar directamente al crear el usuario:

```json
{
  "email": "[email protected]",
  "firstName": "John",
  "lastName": "Doe",
  "role": "MEMBER"
}
```

---

## Campos Adicionales (requieren pasos posteriores)

### 1. **employeeNumber → id**

**No se envía**: BILL genera automáticamente un `uuid` e `id` al crear el usuario. El `employeeNumber` de UKG se debe guardar como referencia externa o en metadata.

**Solución**: Guardar el mapeo `employeeNumber → BILL uuid` localmente.

---

### 2. **primaryProjectCode → Project Code**

**⚠️ COMPORTAMIENTO OBSERVADO**: El PATCH con `customFields` devuelve 200 OK pero **NO guarda el campo**. La respuesta no incluye `customFields` en el JSON.

**Nota sobre la documentación**: 
- La documentación oficial de BILL (https://developer.bill.com/docs/budgets-and-users) solo menciona estos campos para usuarios: `email`, `firstName`, `lastName`, `role`
- NO documenta soporte para `customFields` en el endpoint `/v3/spend/users`
- BILL tiene endpoints para campos personalizados, pero son para **transacciones** (`/v3/spend/transactions/{transactionId}/custom-fields`), no para usuarios

**Opción A: Campo personalizado (NO FUNCIONA - Verificado empíricamente)**
```bash
# ❌ ESTO NO FUNCIONA - El campo no se guarda
# Prueba realizada: PATCH devuelve 200 OK pero el campo NO aparece en la respuesta
curl -X PATCH \
  "https://gateway.stage.bill.com/connect/v3/spend/users/{userUuid}" \
  -H "apiToken: {apiToken}" \
  -H "Content-Type: application/json" \
  -d '{
    "customFields": {
      "projectCode": "711"
    }
  }'
# Respuesta: 200 OK pero el campo NO aparece en la respuesta JSON
```

**✅ Opción B: Guardar en metadata local (RECOMENDADO)**
- Guardar `primaryProjectCode` en el mapeo local junto con el `uuid` de BILL.
- Estructura del mapeo:
```json
{
  "027603": {
    "billUuid": "usr_57kolfl1m10drb794vk1j2nasg",
    "billId": "VXNlcjozNjQxMDk=",
    "employeeNumber": "027603",
    "primaryProjectCode": "711",
    "department": "FOPS"
  }
}
```

**Opción C: Verificar si requiere configuración previa en BILL**
- Los campos personalizados pueden requerir configuración previa en la interfaz web de BILL
- Contactar soporte de BILL para habilitar campos personalizados en la API

---

### 3. **terminationDate → endDate**

**Actualizar usuario con fecha de terminación:**
```bash
# PATCH para actualizar usuario (verificar si BILL soporta endDate)
curl -X PATCH \
  "https://gateway.stage.bill.com/connect/v3/spend/users/{userUuid}" \
  -H "apiToken: {apiToken}" \
  -H "Content-Type: application/json" \
  -d '{
    "endDate": "2025-12-31",
    "retired": true
  }'
```

**Nota**: Verificar en la documentación de BILL si existe el campo `endDate` o si se usa `retired: true` para usuarios inactivos.

---

### 4. **Supervisor → Manager**

**Paso 1**: Asegurarse de que el supervisor ya existe en BILL y obtener su `uuid`.

**Paso 2**: Asignar relación de manager (verificar si BILL soporta esta relación):
```bash
# Opción A: Si BILL soporta campo manager en el usuario
curl -X PATCH \
  "https://gateway.stage.bill.com/connect/v3/spend/users/{userUuid}" \
  -H "apiToken: {apiToken}" \
  -H "Content-Type: application/json" \
  -d '{
    "manager": {
      "uuid": "{supervisorUuid}"
    }
  }'
```

**Opción B**: Si no hay soporte directo, guardar la relación en metadata local.

---

### 5. **Physical Card setting**

**Configurar tarjeta física para el usuario:**
```bash
# Verificar endpoint de tarjetas en BILL API
# Probablemente: POST /v3/spend/cards o similar
curl -X POST \
  "https://gateway.stage.bill.com/connect/v3/spend/cards" \
  -H "apiToken: {apiToken}" \
  -H "Content-Type: application/json" \
  -d '{
    "userUuid": "{userUuid}",
    "type": "PHYSICAL",
    "settings": {
      "enabled": true
    }
  }'
```

**Nota**: Consultar documentación de BILL sobre Vendor Cards para más detalles.

---

### 6. **Direct labor (checkbox) → Budget**

**Asignar usuario a un presupuesto:**
```bash
# PUT para agregar usuario a un budget
curl -X PUT \
  "https://gateway.stage.bill.com/connect/v3/spend/budgets/{budgetUuid}/members/{userUuid}" \
  -H "apiToken: {apiToken}" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 1000,
    "recurringLimit": 1000
  }'
```

**Flujo completo:**
1. Crear o identificar el budget existente
2. Obtener el `budgetUuid`
3. Asignar el usuario al budget con el límite correspondiente

**Documentación**: https://developer.bill.com/docs/budgets-and-users#add-a-user-to-a-budget

---

### 7. **Condensed Cost center → Department**

**⚠️ Mismo problema que Project Code**: `customFields` no funciona.

**Opción A: Campo personalizado (NO FUNCIONA - Mismo problema)**
```bash
# ❌ ESTO NO FUNCIONA - El campo no se guarda
curl -X PATCH \
  "https://gateway.stage.bill.com/connect/v3/spend/users/{userUuid}" \
  -H "apiToken: {apiToken}" \
  -H "Content-Type: application/json" \
  -d '{
    "customFields": {
      "department": "FOPS"
    }
  }'
```

**✅ Opción B: Guardar en metadata local (RECOMENDADO)**
- Guardar `Condensed Cost center` en el mapeo local junto con el `uuid` de BILL.
- Ver estructura en Opción B del punto 2.

---

## Flujo Completo Recomendado

### Paso 1: Crear usuario básico
```bash
POST /v3/spend/users
{
  "email": "[email protected]",
  "firstName": "John",
  "lastName": "Doe",
  "role": "MEMBER"
}
```

**Respuesta:**
```json
{
  "uuid": "{userUuid}",
  "id": "{userId}",
  "email": "[email protected]",
  "firstName": "John",
  "lastName": "Doe",
  "role": "MEMBER"
}
```

### Paso 2: Guardar mapeo local
```json
{
  "027603": {
    "billUuid": "{userUuid}",
    "billId": "{userId}",
    "employeeNumber": "027603",
    "primaryProjectCode": "711",
    "department": "FOPS",
    "supervisorEmployeeNumber": "004295"
  }
}
```

### Paso 3: Actualizar campos adicionales (si están soportados)
- PATCH para `endDate`, `projectCode`, `department` (si BILL los soporta)
- PUT para asignar a `budget`
- POST para configurar `physical card`

### Paso 4: Asignar manager (si está soportado)
- PATCH para establecer relación de manager

---

## Verificación de Endpoints

Para verificar qué campos adicionales soporta BILL API, puedes:

1. **Consultar documentación**: https://developer.bill.com/reference/api-reference-overview
2. **Probar con GET**: Obtener un usuario existente para ver qué campos devuelve
3. **Probar con PATCH**: Intentar actualizar campos y ver qué acepta la API

```bash
# Obtener usuario para ver estructura completa
curl -X GET \
  "https://gateway.stage.bill.com/connect/v3/spend/users/{userUuid}" \
  -H "apiToken: {apiToken}" \
  -H "Accept: application/json" | jq '.'
```

---

## Notas Importantes

1. **Campos personalizados**: Pueden requerir configuración previa en la interfaz de BILL
2. **Relaciones**: Manager y Budget requieren que las entidades relacionadas existan primero
3. **Metadata local**: Algunos campos pueden no tener equivalente en BILL y deben guardarse localmente
4. **Orden de operaciones**: Crear usuario → Obtener UUID → Actualizar campos adicionales → Asignar relaciones

---

## Próximos Pasos

1. Probar creación de usuario básico
2. Verificar respuesta para ver campos disponibles
3. Probar PATCH para actualizar campos
4. Implementar en `upsert-bill-entity.py` cuando esté listo

