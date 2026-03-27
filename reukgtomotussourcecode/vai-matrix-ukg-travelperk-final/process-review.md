# UKG → TravelPerk Integration Process  
Project: vai-matrix-ukg-travelperk  
Status: Work in Progress – this documentation may be updated as new integration versions are released.

---

# High-Level Process Flow

The integration runs in two main phases to correctly handle the supervisor hierarchy required by TravelPerk SCIM:

PHASE 1: Users WITHOUT supervisor (supervisorEmployeeID: null)  
→ Inserted first so their TravelPerk IDs are available  

PHASE 2: Users WITH supervisor  
→ Use the TravelPerk IDs stored during Phase 1  

---

# Step-by-Step Process

## 1. Initialization and Configuration

Example command:

```bash
python run-travelperk-batch.py --company-id J9A6Y --employee-type-codes FTC,HRC,TMC
```

This step:

- Loads `.env` environment variables  
- Ensures required scripts exist  
- Parses and validates arguments  

---

# 2. Fetching Data from UKG

## 2.1 Retrieve Employee Employment Details

```http
GET /personnel/v1/employee-employment-details?companyId=J9A6Y&per_Page=2147483647
```

Returns employment records including:
- employeeNumber  
- employeeID  
- primaryProjectCode  
- terminationDate  
- employeeTypeCode  

Filtering is applied based on `--employee-type-codes` when provided.

---

## 2.2 Retrieve Supervisor Details

```http
GET /personnel/v1/employee-supervisor-details?per_Page=2147483647
```

Builds mappings of:
- employeeNumber → supervisorEmployeeNumber  
- employeeNumber → supervisorEmployeeID  

Used to determine Phase 1 vs Phase 2 processing.

---

# 3. Optional Supervisor Pre-Insertion

Using:

```bash
--insert-supervisor 006488,009299
```

Supervisors are inserted before starting Phase 1, allowing users under them to resolve manager assignments correctly.

---

# 4. PHASE 1: Users Without Supervisor

Filtering rules:
- supervisorEmployeeID is null  
- optional filtering by state (`--states`)  
- optional limit (`--limit`)  

Processing includes:
1. Fetch employment details  
2. Fetch person details  
3. Validate required fields  
4. Build TravelPerk SCIM payload  
5. Insert or update user in TravelPerk  
6. Save employeeNumber → TravelPerk ID mapping  

---

## 4.3 Handling terminationDate

TravelPerk does not support storing an end date.  
Conversion logic:

- terminationDate null or empty → active: true  
- terminationDate present → active: false  

---

# 4.4 Upsert Logic in TravelPerk

If user does not exist → POST  
If user exists → PATCH  

409 Conflict fallback:
- Search by userName  
- If found → PATCH  
- If not found → error  

5xx errors → automatic retry with exponential backoff.

---

# 5. PHASE 2: Users With Supervisor

Steps:

1. Resolve supervisor TravelPerk ID  
   - first from local mapping  
   - otherwise query TravelPerk  
2. Add manager attribute to SCIM payload  
3. Insert or update user  
4. Save mapping  

If supervisor cannot be found, user is created without manager (warning logged).

---

# 6. Final Mapping Storage

Saved to:

```
data/batch/employee_to_travelperk_id_mapping.json
```

Example:

```json
{
  "027603": "207921",
  "004295": "208000",
  "009299": "208001"
}
```

---

# Error Handling Summary

## Required Fields

| Field | Behavior |
|-------|----------|
| employeeNumber | stop process |
| employeeID | stop process |
| emailAddress | stop process |
| firstName | empty allowed |
| lastName | empty allowed |
| primaryProjectCode | optional |

---

# Full Process Summary

1. Initialize environment  
2. Fetch employees from UKG  
3. Fetch supervisor relations  
4. Optional supervisor pre-inserts  
5. Phase 1 processing  
6. Phase 2 processing  
7. Save final mapping  

---

# Example Scenario

Employee: 027603  
Supervisor: 004295  

Payload fields:

- externalId: 027603  
- userName: Farzana.Hoque@matrixmedicalnetwork.com  
- costCenter: 711  
- active: true  

Supervisor field (Phase 2):

```json
{
  "manager": { "value": "207921" }
}
```

---

# Recommended Commands

## Testing

```bash
python run-travelperk-batch.py --company-id J9A6Y --employee-type-codes FTC --limit 1 --dry-run
```

## Production

```bash
python run-travelperk-batch.py --company-id J9A6Y --employee-type-codes FTC,HRC,TMC
```
