# Testi (pytest) — samo PostgreSQL

Testi uporabljajo **izključno PostgreSQL** — enako kot produkcija.
**SQLite v testih ni podprt** (tako kot ni v produkciji).

## Kaj se testira

| Datoteka | Področje |
|----------|----------|
| `test_auth.py` | prijava, menjava gesla, pozabljeno/ponastavitev gesla, rate limit |
| `test_rezervacije.py` | rezervacije, kapaciteta tablic (28), ekskluzivnost, brisanje, IDOR varnost |
| `test_serije.py` | tedenske/celodnevne serije, konfliktno brisanje, kapaciteta, pravice |
| `test_export.py` | CSV izvoz rezervacij in ocenjevanj |

## Lokalni zagon (Docker PostgreSQL)

```bash
# 1. Poženi PostgreSQL 16 (eno enkrat; container ostane)
docker run -d --name sola-test-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=sola_test \
  -p 5432:5432 \
  postgres:16

# 2. Poženi teste
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sola_test \
  pytest tests/ -v
```

Brez `TEST_DATABASE_URL` testi **padejo takoj** z jasno napako (namenoma — brez tihega SQLite fallback-a).

## CI (GitHub Actions)

`.github/workflows/ci.yml` ob vsakem push/PR:
- postavi PostgreSQL 16 service container,
- namesti odvisnosti (Python 3.11 — ista kot produkcijska slika),
- požene `pytest tests/` proti PostgreSQL.
