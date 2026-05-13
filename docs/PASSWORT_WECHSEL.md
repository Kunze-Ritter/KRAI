# Passwort-Wechsel Anleitung (ohne Datenverlust)

> **Status:** Ausstehend — warten bis aktueller Processor-Lauf abgeschlossen ist
> **Hintergrund:** Die alten Passwörter (`Krai_Secure_Pass123!`, `Admin_Pass123!`, `minioadmin`) sind bekannt und sollten rotiert werden. Docker Volumes bleiben beim Wechsel vollständig erhalten.

---

## Was zu ändern ist

| Dienst | Variable | Alter Wert | Ziel |
|--------|----------|-----------|------|
| PostgreSQL | `DATABASE_PASSWORD` | `Krai_Secure_Pass123!` | Starkes Zufallspasswort |
| PostgreSQL | `POSTGRES_PASSWORD` | `Krai_Secure_Pass123!` | (gleich wie oben) |
| PostgreSQL | `DATABASE_CONNECTION_URL` | embedded altes PW | URL mit neuem PW |
| PostgreSQL | `POSTGRES_URL` | embedded altes PW | URL mit neuem PW |
| MinIO | `OBJECT_STORAGE_ACCESS_KEY` | `minioadmin` | Eigener Username |
| MinIO | `OBJECT_STORAGE_SECRET_KEY` | bereits stark ✅ | — |
| Admin | `DEFAULT_ADMIN_PASSWORD` | `Admin_Pass123!` | Starkes Zufallspasswort |

---

## Schritt-für-Schritt (Stack muss laufen)

### 1. Neue Passwörter generieren

```powershell
# In PowerShell 5 ausführen (powershell.exe, nicht pwsh)
.\setup.ps1
```

Das Script generiert kryptografisch sichere Passwörter und schreibt sie direkt in die `.env`.
**Wichtig:** Das Script überschreibt die `.env` — notiere die generierten Werte vorher!

Alternativ manuell ein Passwort generieren:
```powershell
# Ein einzelnes sicheres Passwort erzeugen
-join ((1..32) | ForEach-Object { [char](Get-Random -Min 48 -Max 122) })
```

---

### 2. PostgreSQL-Passwort live wechseln

```bash
# Neues Passwort IN der laufenden Datenbank setzen
# NEUES_PASSWORT durch den generierten Wert ersetzen
docker exec krai-postgres-prod psql -U krai_user -d krai -c "ALTER USER krai_user WITH PASSWORD 'NEUES_PASSWORT';"
```

Erfolg sieht so aus: `ALTER ROLE`

---

### 3. `.env` aktualisieren

Die folgenden Zeilen in `.env` auf das neue Passwort setzen:

```env
DATABASE_PASSWORD=NEUES_PASSWORT
POSTGRES_PASSWORD=NEUES_PASSWORT
DATABASE_CONNECTION_URL=postgresql://krai_user:NEUES_PASSWORT@krai-postgres:5432/krai
POSTGRES_URL=postgresql://krai_user:NEUES_PASSWORT@localhost:5432/krai
```

---

### 4. MinIO Access Key wechseln (optional)

```bash
# MinIO Console aufrufen: http://localhost:9001
# Login: minioadmin / aktuelles OBJECT_STORAGE_SECRET_KEY
# Unter: Identity → Users → minioadmin → Edit → neuen Access Key setzen
```

Oder via CLI:
```bash
docker exec krai-minio-prod mc alias set local http://localhost:9000 minioadmin $(grep OBJECT_STORAGE_SECRET_KEY .env | cut -d= -f2)
docker exec krai-minio-prod mc admin user add local NEUER_USER NEUES_PASSWORT
# Danach in .env: OBJECT_STORAGE_ACCESS_KEY=NEUER_USER
```

---

### 5. Admin-Passwort wechseln

Entweder über das Laravel Dashboard (http://localhost:80) unter Profil → Passwort ändern,
oder direkt via API:

```bash
# Nach dem Neustart des krai-engine Containers
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Admin_Pass123!"}'
# Dann im Dashboard das Passwort ändern
```

---

### 6. Stack neu starten (nur krai-engine, nicht DB/MinIO!)

```bash
# NUR den API-Container neu starten — DB und MinIO laufen durch
docker-compose restart krai-engine
```

---

## Checklist

- [ ] Processor-Lauf abgeschlossen
- [ ] Neue Passwörter generiert (via `setup.ps1` oder manuell)
- [ ] PostgreSQL: `ALTER USER` ausgeführt
- [ ] `.env` aktualisiert (alle 4 PostgreSQL-Stellen)
- [ ] MinIO Access Key gewechselt
- [ ] Admin-Passwort geändert
- [ ] `docker-compose restart krai-engine` ausgeführt
- [ ] Login-Test: API + Laravel Dashboard
