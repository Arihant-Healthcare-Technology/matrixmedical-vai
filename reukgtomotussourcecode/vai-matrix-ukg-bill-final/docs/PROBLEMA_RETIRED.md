# Problema: PATCH retired no actualiza

## Problema Reportado

El PATCH con `{"retired": true}` devuelve `200 OK` pero el campo **NO se actualiza** en la respuesta.

**Request:**
```json
PATCH /v3/spend/users/{userUuid}
{
  "retired": true
}
```

**Response:**
```json
{
  "id": "VXNlcjozNjQxMTg=",
  "uuid": "usr_b7m8dukr2949v6cg8b5rnupd3c",
  "firstName": "test2",
  "lastName": "example",
  "email": "test2@example.com",
  "retired": false,  // ← NO cambió, sigue en false
  "role": "MEMBER",
  "createdTime": "2025-11-20T20:18:05.000+00:00"
}
```

## Posibles Causas

1. **El campo `retired` no es actualizable vía PATCH**
   - Puede requerir DELETE endpoint
   - Puede requerir endpoint específico para retirar usuarios

2. **Permisos insuficientes**
   - Puede requerir rol ADMIN para retirar usuarios
   - Verificar permisos del token API

3. **Formato incorrecto**
   - Puede requerir formato diferente
   - Puede requerir campos adicionales

4. **Limitación de la API**
   - BILL puede no permitir actualizar `retired` directamente
   - Puede requerir DELETE y recrear

## Soluciones a Probar

### Opción 1: Usar DELETE endpoint (si existe)

```bash
# Verificar si existe DELETE endpoint
curl -X DELETE \
  "https://gateway.stage.bill.com/connect/v3/spend/users/usr_b7m8dukr2949v6cg8b5rnupd3c" \
  -H "apiToken: {apiToken}" \
  -H "Accept: application/json"
```

### Opción 2: Verificar documentación de actualización

Consultar: https://developer.bill.com/reference/updateuser

### Opción 3: Intentar con PUT (full update)

```bash
curl -X PUT \
  "https://gateway.stage.bill.com/connect/v3/spend/users/usr_b7m8dukr2949v6cg8b5rnupd3c" \
  -H "apiToken: {apiToken}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test2@example.com",
    "firstName": "test2",
    "lastName": "example",
    "role": "MEMBER",
    "retired": true
  }'
```

### Opción 4: Verificar si requiere campo adicional

Algunas APIs requieren un campo `version` o `etag` para actualizaciones.

## Nota

Si `retired` no se puede actualizar vía PATCH, la solución puede ser:
- Usar DELETE para eliminar/retirar usuarios
- O simplemente no actualizar `retired` y guardar el estado en mapeo local

