# 1. Running SahiDawa on Your Own Computer

> **In short**
> - SahiDawa now runs fully on a Windows laptop: website, API and database.
> - It didn't work straight away. The project's own setup guide is out of date,
>   and its database files are broken.
> - Every problem is listed below with the fix, so the next person can set it
>   up in an hour instead of days.
> - The AI and voice features still don't work, because they need paid API keys.

---

## What SahiDawa is made of

SahiDawa isn't one program but several pieces that work together:

| Piece | What it does | Works locally? |
|---|---|---|
| **Website** | The pages people use | ✅ Yes |
| **API** | Answers the website's questions, like "is this batch recalled?" | ✅ Yes |
| **Database** | Stores medicines, pharmacies, alerts, users | ✅ Yes |
| **Cache (Redis)** | Remembers recent answers so repeat questions are fast | ✅ Yes |
| **Scrapers** | Collect data from government websites (see guide 3) | ✅ Small test run |
| **ML service** | AI features: reading photos on the server, voice | ❌ Not set up, needs API keys |

## Why it runs inside Linux on Windows (WSL)

The project is built for Linux. Windows has a built-in Linux called **WSL**
(Windows Subsystem for Linux), and everything runs inside it. There are three
reasons:

- The database runs in Docker, which lives inside WSL.
- One of the AI libraries has no Windows version at all.
- Installing and running the project is much faster on the Linux side.

You still open the website in your normal Windows browser.

---

## Starting it every day

Nothing keeps running after the laptop restarts, so these four things must be
started each time, in this order.

**For developers**, inside a WSL terminal:
```bash
cd ~/dm/sahidawa-india

npx supabase start            # 1. database
docker start sahidawa-redis   # 2. cache

npm run dev -w apps/api &     # 3. API
npm run dev -w apps/web       # 4. website
```

Then open these in any browser:

| Address | What you see |
|---|---|
| http://localhost:3000/en | The SahiDawa website |
| http://localhost:4000/health | A short message saying the API is healthy |
| http://localhost:54323 | Supabase Studio: look inside the database tables |

---

## Setting it up for the first time

**For developers.** Needs WSL (Ubuntu 24.04) with Docker.

```bash
# 1. Install Node.js version 22 (the project needs exactly this version)
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
. ~/.nvm/nvm.sh && nvm install 22 && nvm alias default 22
npm i -g npm@11.12.1

# 2. Download the code
mkdir -p ~/dm && cd ~/dm
git clone https://github.com/Dreammonks/sahidawa-india.git
cd sahidawa-india
git remote add upstream https://github.com/RatLoopz/sahidawa-india.git

# 3. Settings files (these hold keys; never commit them)
cp .env.example .env
cp .env.example apps/web/.env.local

# 4. Install everything (~1.8 GB)
npm install

# 5. Build the shared code FIRST, or the API won't start
npm run build -w @sahidawa/types -w @sahidawa/validators -w @sahidawa/shared

# 6. First time only: create the Redis cache container
docker run -d --name sahidawa-redis -p 6379:6379 redis:7-alpine
```

Then set up the database as described in "Problem 2" below.

**Keys still missing:** Gemini, Sarvam, OpenAI, Cloudinary and Google
credentials. Without them, the AI chat, voice, photo upload for reports and
recall alerts don't work.

---

## Problems found, and how each was fixed

### Problem 1 — The project's own setup guide is out of date

`docs/getting-started/local-setup.md` is wrong in four places:

| The guide says | What is actually true |
|---|---|
| Use Node.js 20 or newer | You need **Node.js 22** |
| If install fails, add `--legacy-peer-deps` | **Not needed.** A plain `npm install` works on Linux |
| Just start the API with `npm run dev` | **It crashes** unless the shared code is built first (step 5 above) |
| `docker compose up` starts everything | **It doesn't start the database.** That's a separate `npx supabase start` |

### Problem 2 — The database files are broken

**What should happen:** when the database starts, it runs 109 "migration"
files one after another, and together they create all the tables.

**What actually happens:** it stops partway with an error. This isn't a
problem on our laptop: the project's own automatic tests on GitHub fail the
same way. Three files are at fault:

| Problem | In plain words |
|---|---|
| Two files have the same number (`20260712000000`) | Like two pages both numbered 12; the database refuses the second |
| `20260724000000_fix_pharmacy_missing_schema.sql` | Changes an existing database function without removing the old one first |
| `20260730000000_add_performance_indexes.sql` | Tries to speed up columns that don't exist |

**How it was worked around** (on this laptop only, not saved to the project):
1. Gave the duplicate file a new number.
2. Added a small file that removes the old pharmacy functions first.
3. Switched off the broken speed-up file.
4. Told Supabase not to run the files itself (`supabase/config.toml`).
5. Ran the files by hand instead:

```bash
DB=supabase_db_sahidawa-india
for f in $(ls supabase/migrations/*.sql | sort); do
  docker exec -i $DB psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q < $f \
    || echo "FAILED: $f"
done
docker exec -i $DB psql -U postgres -d postgres -q < supabase/seed.sql
```

**Result:** 107 of 109 files worked, and all 46 tables and the sample data were
created. The two that still fail:

| File | What doesn't work because of it |
|---|---|
| `20260627010000_fix_search_medicines_text_trgm_usage` | Nothing visible. Medicine search still works, with default settings |
| `20260806000000_knn_pharmacy_search` | The "nearest open pharmacy" feature |

**Proper fix:** correct these files in the main project, so everyone can start
the database with one command.

### Problem 3 — The website works inside Linux but not in the Windows browser

**What you see:** the website loads when checked from inside WSL, but the
Windows browser says it can't connect.

**Why:** some Windows laptops quietly reserve ranges of network ports for
their own use. On this laptop, ports 2967–3066 and 3702–4401 were reserved.
That covers **3000** (the website) and **4000** (the API), so Windows couldn't
pass them through to WSL. The cause was a Windows setting that let it reserve
ports that low.

**Check** (Windows PowerShell):
```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```
If 3000 or 4000 falls inside a listed range, this is your problem.

**Fix** (PowerShell, **run as Administrator**, one time):
```powershell
netsh int ipv4 set dynamicport tcp start=49152 num=16384
netsh int ipv6 set dynamicport tcp start=49152 num=16384
wsl --shutdown
net stop winnat
net start winnat
```
This puts back the normal Windows setting and releases the reserved ports.
Afterwards both addresses work in the Windows browser.

### Problem 4 — WSL loses its internet connection after that fix

**What you see:** inside WSL, nothing online loads (GitHub, Google, anything).

**Fix** (PowerShell, **run as Administrator**):
```powershell
wsl --shutdown
Restart-Service hns -Force
```
If it still has no internet, restart Windows.

### Problem 5 — The website and API stop by themselves

If you start them with a one-off command from Windows, they stop as soon as
that command finishes. Start them from an open WSL terminal and leave it
open.

### Problem 6 — Another program is using port 8000

SahiDawa's AI service wants port 8000. If another program already uses it,
the API wrongly reports the AI service as "up". **Fix:** in `.env`, set
`ML_PORT=8010` and `ML_SERVICE_URL=http://127.0.0.1:8010`.

### Problem 7 — Code changes don't show up

If you edit files from Windows Explorer (through `\\wsl.localhost\...`), the
website doesn't notice the change. Edit from inside WSL instead.

---

## Where things stand

| | Status |
|---|---|
| Website, API, database, cache | ✅ Running |
| Reachable from the Windows browser | ✅ Yes, after the Problem 3 fix |
| AI service | ❌ Not set up |
| Database workarounds | Kept on this laptop only; not proper fixes for the project |
