# Campo `retired` en BILL API - Comportamiento Confirmado

## Problema Confirmado

El campo `retired` **NO se puede actualizar** en BILL API:

1. **POST con `retired: true`**: 
   - ✅ Devuelve 200 OK
   - ❌ **Ignora el campo** y siempre crea con `retired: false`

2. **PATCH con `retired: true`**:
   - ✅ Devuelve 200 OK
   - ❌ **No actualiza el campo** (sigue en `false`)

3. **DELETE**:
   - ✅ **Funciona** - Elimina/retira el usuario

## Comportamiento Confirmado

### POST /v3/spend/users
```json
// Request
{
  "email": "[email protected]",
  "firstName": "test2",
  "lastName": "example",
  "role": "MEMBER",
  "retired": true  // ← Se ignora
}

// Response
{
  "uuid": "usr_xxxxx",
  "retired": false  // ← Siempre false, ignora el valor enviado
}
```

### PATCH /v3/spend/users/{userUuid}
```json
// Request
{
  "retired": true  // ← Se ignora
}

// Response
{
  "uuid": "usr_xxxxx",
  "retired": false  // ← No cambia, sigue en false
}
```

### DELETE /v3/spend/users/{userUuid}
```bash
# ✅ Funciona - Elimina/retira el usuario
DELETE /v3/spend/users/usr_xxxxx
# Response: 200 OK (o 204 No Content)
```

## Soluciones

### Opción 1: Usar DELETE para retirar usuarios

Si un usuario tiene `terminationDate` en UKG, usar DELETE en lugar de PATCH:

```python
if termination_date:
    # Usuario terminado - eliminar de BILL
    bill_delete_user(user_uuid)
else:
    # Usuario activo - crear o actualizar normalmente
    bill_post_user(payload)
```

### Opción 2: Mapeo local (recomendado)

Guardar el estado de `retired` en mapeo local basado en `terminationDate`:

```json
{
  "027603": {
    "billUuid": "usr_xxxxx",
    "retired": true,  // ← Basado en terminationDate de UKG
    "terminationDate": "2025-12-31"
  }
}
```

**Ventaja**: No depende de que BILL actualice el campo (que no funciona).

### Opción 3: DELETE y recrear (no recomendado)

1. DELETE el usuario si está terminado
2. No recrearlo hasta que esté activo de nuevo

**Desventaja**: Pierde el UUID del usuario.

## Recomendación Final

**Usar mapeo local** para `retired`:
- Basar el valor en `terminationDate` de UKG
- No intentar actualizar `retired` en BILL (no funciona)
- Si es crítico eliminar usuarios terminados, usar DELETE

## Implementación en Código

```python
# En build-bill-entity.py
termination_date = employee.get("terminationDate")
is_retired = termination_date is not None and termination_date != ""

# NO incluir retired en POST (se ignora)
# Guardar en metadata para mapeo local
metadata = {
    "retired": is_retired,  # Para mapeo local
    "terminationDate": termination_date
}

# Si es crítico eliminar, usar DELETE después de crear
if is_retired:
    # Opción: DELETE el usuario después de crearlo
    # O simplemente guardar en mapeo local
    pass
```

