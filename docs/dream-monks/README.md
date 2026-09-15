# Dream Monks — Work on SahiDawa

This folder explains the work Dream Monks has done on its copy of SahiDawa.
It is written in plain English, so you don't need to be a developer to follow
it. Parts meant only for developers are clearly marked.

*Last updated: 15 September 2026*

## What is SahiDawa?

SahiDawa ("correct medicine") is a free, open-source website that helps people
in India stay safe with medicines. People can check whether a medicine is real,
find cheaper versions, find a pharmacy nearby, and see government recall
warnings. Dream Monks made its own copy (a "fork") of the project to study it
and build on it.

## The three guides

| Guide | Read it to learn | Status |
|---|---|---|
| [1. Running SahiDawa on your own computer](local-setup.md) | How to get the whole project running on a Windows laptop, what went wrong, and how each problem was fixed | ✅ Runs locally |
| [2. Barcode product lookup](barcode-product-lookup.md) | A new feature: scan the barcode on any pack and SahiDawa tells you what the product is | ✅ Built and tested |
| [3. How SahiDawa collects its data](scraping.md) | Where the medicine data comes from, how it is collected automatically, and what a live test showed | ✅ Tested with a small sample |

**Short on time?** Read the "In short" box at the top of each guide.

## Words used in these guides

| Word | Meaning |
|---|---|
| **Website** | The pages people see and click (runs at `localhost:3000`) |
| **API** | The server the website asks for data behind the scenes (runs at `localhost:4000`) |
| **Database** | Where all the data is stored (SahiDawa uses Supabase, a database platform built on PostgreSQL) |
| **localhost** | "This computer". The project runs on your own laptop, not on the internet |
| **Migration** | A file that creates or changes database tables, run in order |
| **Scraper** | A small program that visits a website and copies data from it |
| **Barcode** | The striped code on a pack; the numbers under it identify the product |
| **CDSCO** | India's national drug regulator |
| **Jan Aushadhi** | The government scheme selling low-cost generic medicines |
| **Branch** | A separate line of work in the code, kept apart until it is ready |
| **Commit** | One saved, labelled change to the code |

## Where the code is

| Branch | What is in it |
|---|---|
| `feature/barcode-product-lookup` | The barcode lookup feature and two bug fixes (guide 2) |
| `feature/etl-small-scrape-demo` | A fix for a broken data source and a small scraping demo (guide 3) |
| `feature/dream-monks-docs` | These guides |
