# Deployment (Google Cloud e2-micro VM)

The app runs on one free-tier VM with `docker-compose.prod.yml`: Postgres, the backend, and
Caddy, which serves the built frontend, forwards `/api` to the backend and gets HTTPS by itself.
Synthetic data only (README, non-negotiables): this is a demo, not a service for real documents.

## 1. Create the VM (once)

Google Cloud console → Compute Engine → VM instances → Create instance:

| Setting | Value |
|---|---|
| Region | us-central1, us-west1 or us-east1 (free tier) |
| Machine type | E2 → e2-micro |
| Boot disk | Ubuntu 24.04 LTS (x86/64), Standard persistent disk, 30 GB |
| Firewall | Allow HTTP and Allow HTTPS |

Set a budget alert first (Billing → Budgets & alerts). Note the VM's External IP, e.g.
`34.123.45.67`; the site's address is then `34-123-45-67.sslip.io` (sslip.io maps that name to
the IP, so no domain is needed).

## 2. Prepare the VM (once)

Open the VM's **SSH** button in the console, then:

```bash
# 2 GB of swap: the e2-micro has 1 GB of memory, not enough to build the frontend.
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile
sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Docker, from Docker's own install script.
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Close the SSH window and open it again (so `docker` works without `sudo`), then:

```bash
# The code.
git clone https://github.com/Saifullah1999Pk/pak-tax-filer.git && cd pak-tax-filer
git switch 002-signup   # until it's merged; then main
```

## 3. The server's secrets (once)

Create `.env` in `pak-tax-filer/` with `nano .env`. It is never committed:

```
SITE_ADDRESS=34-123-45-67.sslip.io
POSTGRES_PASSWORD=<a long random password: run `openssl rand -hex 24` and paste the output>
GEMINI_API_KEY=<your key from Google AI Studio>
ADMIN_SECRET_KEY=<another long random value: `openssl rand -hex 32`>
```

Then `chmod 600 .env`, so only your user can read it.

## 4. Start it

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-user --email demo@example.com
```

The first build takes several minutes. Then open `https://34-123-45-67.sslip.io` and log in,
or choose **Create an account** (the `create-user` command is optional).

The internal admin area is at `https://34-123-45-67.sslip.io/admin` (feature 011). Admin accounts
are staff-only and made only from the command line (a new account each time; you're asked for the
password twice; at least 12 characters):

```bash
docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-admin --email you@example.com
```

Build the tax assistant's corpus (feature 006): it downloads FBR's texts, checks each against
its checksum in `app/rag/sources.yaml` and embeds them with Gemini (about 45 passages, under a
minute). Until it is built, the Ask page says the assistant isn't ready yet. Run it again only
when `sources.yaml` changes; a failed build leaves the previous corpus in place.

```bash
docker compose -f docker-compose.prod.yml exec backend python -m app.rag.build
```

## 5. Private bucket for uploads (once; feature 003, FR-018)

Uploads go to a private Cloud Storage bucket instead of the VM's disk. The app reaches it with
the VM's own Google identity, so there is no key to create or store.

1. **Keep the IP:** stopping the VM can change its IP, and with it the site's address. VPC
   network → IP addresses → the VM's external address → **Promote to static IP address**. Check
   the price shown before confirming.
2. **Create the bucket:** Cloud Storage → Buckets → Create. A globally unique name (e.g.
   `pak-tax-filer-uploads-<something>`); location type **Region**, **us-central1** (free tier);
   storage class **Standard**; **Enforce public access prevention** ticked; access control
   **Uniform**; under data protection, turn **soft delete off** (otherwise deleted certificates
   stay recoverable, and billed, for 7 days).
3. **Give the VM's identity this bucket only:** on the VM's page, note its **service account**
   (e.g. `<number>-compute@developer.gserviceaccount.com`; it must not be "No service
   account"). Then the bucket → Permissions → **Grant access** → that account → role **Storage
   Object User**. Newer projects give that account no roles at all, so without this every upload
   fails with "Couldn't reach file storage".
4. **Let the VM use Cloud Storage:** Compute Engine → VM instances → `pak-tax-filer` →
   **Stop**. Then **Edit** → API and identity management → Access scopes → **Set access for each
   API** → Storage: **Read Write** → Save → **Start**. (Scopes only limit; step 3 grants.)
5. On the VM, add `UPLOAD_BUCKET=<the bucket's name>` to `.env`, then start the app as in step 4.

Files uploaded before this stay on the disk volume and keep working.

## 6. Continuous deployment (once; feature 001, User Story 5)

After this, every merge into `main` whose CI passes deploys itself (`.github/workflows/deploy.yml`):
GitHub builds both images, the VM pulls and starts them, and the run checks the live site.

1. **A key just for deploys**, made on your own computer (Git Bash), in a temporary folder:
   ```bash
   mkdir -p ~/deploy-setup && cd ~/deploy-setup
   ssh-keygen -t ed25519 -N "" -C github-deploy -f deploy_key
   cat deploy_key.pub
   ```
2. **On the VM**, allow that key to run only the deploy (one line; paste the whole `.pub` line
   where shown):
   ```bash
   echo 'command="bash /home/'"$USER"'/pak-tax-filer/pak-tax-filer/deploy/deploy.sh",restrict <paste deploy_key.pub here>' >> ~/.ssh/authorized_keys
   ```
   `restrict` turns off shells, terminals and forwarding for this key; the forced command means
   it can run nothing but `deploy.sh`. Note the VM's host key fingerprint for step 3:
   `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`.
3. **The VM's identity**, on your computer: `ssh-keyscan -t ed25519 34.55.150.199 > known_hosts`,
   then `ssh-keygen -lf known_hosts` must show the same fingerprint as step 2. If not, stop.
4. **Secrets and the site address**, on your computer (in `~/deploy-setup`):
   ```bash
   R=awais786/pak-tax-filer
   gh secret set DEPLOY_SSH_KEY --repo $R < deploy_key
   gh secret set DEPLOY_HOST --repo $R --body "<VM user>@34.55.150.199"
   gh secret set DEPLOY_KNOWN_HOSTS --repo $R < known_hosts
   gh variable set SITE_URL --repo $R --body "https://34-55-150-199.sslip.io"
   ```
   Then delete the private key: `cd ~ && rm -rf ~/deploy-setup`. GitHub keeps the only copy.
5. **Check the lock:** `ssh -i <key> <user>@34.55.150.199 whoami` must print "Refused", not a
   name (do this before deleting the key, or skip it; the deploy tests cover it).

Deploys start from `main` only, so the first one runs after these changes are merged. To
redeploy an earlier commit (rollback): Actions → Deploy → Run workflow → enter its SHA.

## Updating

Automatic since section 6. By hand, if ever needed (it builds on the VM, which is slow):

```bash
cd pak-tax-filer && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically when the backend starts.

## Checking on it

- `docker compose -f docker-compose.prod.yml ps`: all three services should be running.
- `docker compose -f docker-compose.prod.yml logs -f backend`: the backend's log.
- Stopping everything: `docker compose -f docker-compose.prod.yml down` (the data stays in its
  volumes; add `-v` only to delete it).
