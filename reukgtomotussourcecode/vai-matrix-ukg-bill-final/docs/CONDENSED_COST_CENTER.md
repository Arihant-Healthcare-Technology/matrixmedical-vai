# Condensed Cost center en UKG

## Resultado de Búsqueda en Documentación Oficial

Según la búsqueda en la documentación oficial de UKG:

### ❌ NO está disponible en REST API estándar

Según la documentación oficial:
- **NO está disponible** en los endpoints REST estándar de UKG Pro
- **NO está** en `/personnel/v1/employee-employment-details` ❌
- **NO está** en otros endpoints REST estándar ❌

### ✅ Solo disponible en SOAP (Employee Job Service)

El campo "Condensed Cost center" **solo está disponible** en el **Employee Job Service (SOAP)**:
- **Servicio**: Employee Job Service
- **Protocolo**: SOAP 1.2
- **Endpoint**: `http://services.ultipro.com/services/EmployeeJob`
- **Método**: `GetJobByEmployeeIdentifier`
- **Documentación**: https://developer.ukg.com/hcm/docs/employee-job-service#employee-job-object

**Similar a DirectLabor**: Ambos campos están en el mismo servicio SOAP.

### ⚠️ Posibles Alternativas en REST (depende de configuración)

1. **orgLevel fields** - Puede estar mapeado a uno de estos (configuración específica):
   - `orgLevel1Code`
   - `orgLevel2Code`
   - `orgLevel3Code`
   - `orgLevel4Code`
   - **Nota**: Esto depende de cómo esté configurado en tu organización

2. **User Defined Fields (UDF)** - Si está configurado como campo personalizado:
   - Puede estar en User Defined Fields
   - Requiere consultar la tabla de UDF
   - Depende de la configuración específica de tu organización

## Comandos para Verificar

### 1. Verificar en employee-employment-details

```bash
curl -X GET \
  "https://service4.ultipro.com/personnel/v1/employee-employment-details?employeeNumber=027603" \
  -H "Authorization: Basic {token}" \
  -H "us-customer-api-key: {apiKey}" \
  -H "Accept: application/json" | jq '.' | grep -i "cost\|center\|condensed"
```

### 2. Ver orgLevel fields

```bash
curl -X GET \
  "https://service4.ultipro.com/personnel/v1/employee-employment-details?employeeNumber=027603" \
  -H "Authorization: Basic {token}" \
  -H "us-customer-api-key: {apiKey}" \
  -H "Accept: application/json" | jq '{orgLevel1Code, orgLevel2Code, orgLevel3Code, orgLevel4Code}'
```

### 3. Ver todas las keys disponibles

```bash
curl -X GET \
  "https://service4.ultipro.com/personnel/v1/employee-employment-details?employeeNumber=027603" \
  -H "Authorization: Basic {token}" \
  -H "us-customer-api-key: {apiKey}" \
  -H "Accept: application/json" | jq 'keys' | grep -i "cost\|center\|org\|level"
```

### 4. Verificar en configuration (cost centers)

```bash
curl -X GET \
  "https://service4.ultipro.com/configuration/v1/cost-centers" \
  -H "Authorization: Basic {token}" \
  -H "us-customer-api-key: {apiKey}" \
  -H "Accept: application/json" | jq '.'
```

## Próximos Pasos

1. **Ejecutar los comandos curl** para ver qué campos están disponibles
2. **Revisar la respuesta completa** de `employee-employment-details` con `DEBUG=1`
3. **Verificar si está en orgLevel** - uno de los orgLevel puede ser el cost center
4. **Si no está en REST**, probablemente está en Employee Job Service (SOAP)

## Conclusión

Según la documentación oficial de UKG:

1. **"Condensed Cost center" NO está en REST API estándar** ❌
2. **Solo está disponible en Employee Job Service (SOAP)** ✅
3. **Puede estar mapeado a orgLevel** (depende de configuración) ⚠️
4. **Puede estar en User Defined Fields** (si está configurado como UDF) ⚠️

## Recomendación

**Opción 1: Usar SOAP** (si es crítico)
- Implementar cliente SOAP para Employee Job Service
- Similar a DirectLabor

**Opción 2: Usar orgLevel** (si está mapeado)
- Verificar cuál de los orgLevel corresponde al cost center en tu organización
- Ejecutar los comandos curl para verificar

**Opción 3: Valor por defecto o mapeo local**
- Si no es crítico, usar valor por defecto o mapeo manual
- Guardar en mapeo local cuando se obtenga el valor

**Recomendación**: Primero verificar si está en orgLevel ejecutando los comandos curl. Si no está, usar SOAP o mapeo local.

