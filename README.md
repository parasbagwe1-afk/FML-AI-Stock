# FAstockFlow

Server-rendered Flask implementation of the FAstockFlow stock, FIFO, payment, outstanding, and inter-company control system.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask init-db
flask seed-data
flask run
```

Default seeded admin credentials are controlled by `.env`:

- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

## Docker

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8000`.

The container runs `flask init-db` and `flask seed-data` on startup. Both commands are idempotent for a fresh deploy and normal restarts.

## Ubuntu Docker Compose Deploy

Install Docker once on the server, then deploy from the repository:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Log out and back in after `usermod`, then:

```bash
git clone https://github.com/parasbagwe1-afk/FML-AI-Stock.git
cd FML-AI-Stock
cp .env.example .env
nano .env
docker compose up -d --build
```

For later updates after pushing from your laptop:

```bash
cd FML-AI-Stock
git pull --ff-only
docker compose up -d --build --force-recreate
docker compose logs -f web
```

If the server still shows an old import error after pulling, force a clean image rebuild once:

```bash
docker compose down
docker compose build --no-cache web
docker compose up -d
```

## Notes

- MySQL is the production target.
- SQLite is supported for tests and quick local smoke checks.
- Stock is never edited directly. Opening stock, purchase, sale, and transfer documents create FIFO layers and ledger entries.
