# Flux — daily astronomy preprints

*New science, per unit time.*

Flux collects the new papers posted to arXiv in the categories you follow and sorts them for you each morning. It marks the papers that match your keywords or the authors you follow, shows a pick of the day from landmark papers, and sends one notification to your phone. You can also turn on plain-language summaries in English and Hindi.

It runs entirely on free GitHub services. There's no server for you to look after.

## How it works

```
arXiv RSS feeds ──► GitHub Actions (every morning, 06:45 IST)
                      │  scripts/flux_daily.py
                      │   • collects new papers in your categories
                      │   • marks keyword / author matches
                      │   • optional AI summaries (English + Hindi)
                      │   • chooses the pick of the day
                      ├──► docs/data/*.json  ──► GitHub Pages ──► Flux app on your phone
                      └──► ntfy notification ──► your phone
```

Some terms used in this guide:

- **Repository (repo)**: a project folder stored on GitHub.
- **GitHub Actions**: GitHub's free service for running a script on a schedule. Here it runs the daily job.
- **GitHub Pages**: GitHub's free web hosting. It serves the Flux app from the `docs/` folder.
- **Secret**: a private value (such as a password or key) that you store in the repo settings. The daily job can read it, but nobody visiting the repo can see it.
- **PWA (progressive web app)**: a website that installs on your phone like an app, with its own icon and full-screen window. Flux is one.
- **ntfy**: a free, open-source notification app. Your daily job posts a message to a "topic" (a channel name you choose), and the ntfy app on your phone shows it.
- **API key**: a password that lets a program use a paid service. You only need one for the optional AI summaries.

## What's in this folder

| Path | What it is |
|---|---|
| `config.json` | **Your settings**: categories, keywords, authors, app address. |
| `picks.json` | The list of landmark papers used for the pick of the day. Add your own. |
| `scripts/flux_daily.py` | The daily job. Uses only the Python standard library. |
| `scripts/make_icons.py` | Redraws the app icons (needs Pillow). You only need it if you change the icon. |
| `.github/workflows/daily.yml` | Tells GitHub Actions when and how to run the daily job. |
| `docs/` | The Flux app (`index.html`, icons, offline support). `docs/data/` is filled in by the daily job. |
| `tests/fixtures/` | Sample arXiv files, for testing the script without internet access. |

---

## Setup, step by step

Setup takes about 20 minutes, all done in the browser on github.com.

### Step 1: Create the repository

1. Sign in to github.com.
2. Click **+** (top right), then **New repository**.
3. Set **Repository name** to `flux`.
4. Choose **Public**. GitHub Pages is free for public repositories. Your papers list is public anyway, and your secrets stay private.
5. Leave everything else as it is and click **Create repository**.

### Step 2: Upload the files

1. On the new repository page, click **uploading an existing file**.
2. Unzip `flux.zip` on your computer. Open the `flux` folder and drag **everything inside it** onto the upload page: `config.json`, `picks.json`, `README.md`, and the `docs`, `scripts` and `tests` folders.
3. Click **Commit changes**.
4. The `.github` folder is usually hidden on Windows and macOS, so create it directly on GitHub:
   - Click **Add file**, then **Create new file**.
   - In the name box type exactly `.github/workflows/daily.yml`. Typing each `/` creates a folder.
   - Open `.github/workflows/daily.yml` from the zip in a text editor, copy all of it, and paste it into the large box.
   - Click **Commit changes**.

### Step 3: Edit your settings

1. In the repository, click `config.json`, then the pencil icon (Edit).
2. Change `app_url` to `https://YOUR-GITHUB-USERNAME.github.io/flux/`, using your real GitHub username.
3. Change these settings if you want:
   - **`categories`**: arXiv category codes. Common ones: `astro-ph.GA` (galaxies), `astro-ph.CO` (cosmology), `astro-ph.EP` (exoplanets and planetary), `astro-ph.HE` (high energy), `astro-ph.IM` (instrumentation and methods), `astro-ph.SR` (solar and stellar), `gr-qc` (gravity).
   - **`keywords`**: words to watch for in titles and abstracts. Matching ignores upper/lower case and also matches inside longer words, so `spectroscop` matches both "spectroscopy" and "spectroscopic".
   - **`authors`**: surnames (or parts of names) to follow.
   - **`include_cross_lists`**: `true` also includes papers from other categories that their authors cross-listed to yours.
   - **`archive_days`**: how many days of papers to keep for search (30 by default).
4. Click **Commit changes**.

### Step 4: Turn on GitHub Pages (hosting the app)

1. Click **Settings** (the tab at the top of the repo).
2. In the left menu, click **Pages**.
3. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
4. Set **Branch** to `main` and the folder to `/docs`, then click **Save**.
5. After a minute or two, the page shows "Your site is live at https://YOUR-USERNAME.github.io/flux/".

### Step 5: Let the daily job save its results

1. Still in **Settings**, click **Actions** in the left menu, then **General**.
2. Scroll to **Workflow permissions**.
3. Choose **Read and write permissions** and click **Save**.

### Step 6: Set up phone notifications (ntfy)

1. Install **ntfy** on your phone from the Google Play Store or Apple App Store.
2. Make up a topic name that is hard to guess, for example `flux-pranshu-7k3q9x`. Anyone who knows a topic name can read its messages, so don't use something simple like `flux`. The messages only contain paper titles, but a private name is still better.
3. In the ntfy app, tap **+**, type your topic name and tap **Subscribe**.
4. On GitHub, go to **Settings**, then **Secrets and variables**, then **Actions**, and click **New repository secret**.
5. Set **Name** to `NTFY_TOPIC` and **Secret** to your topic name. Click **Add secret**.

### Step 7 (optional): Turn on AI summaries in English and Hindi

Without this step Flux still works, but it shows only the original abstracts.

1. Create an account at console.anthropic.com and add a small amount of credit.
2. Under **API Keys**, create a key and copy it. It starts with `sk-ant-`.
3. On GitHub, add another repository secret (as in Step 6, parts 4 and 5) with **Name** `ANTHROPIC_API_KEY` and the key as the value.
4. In `config.json`, `summaries.max_papers` limits how many papers are summarised each day (15 by default). Keyword matches are summarised first. Each summary costs a small amount; check the current price for the `claude-haiku-4-5` model on Anthropic's pricing page.

### Step 8: Run it for the first time

1. Click the **Actions** tab.
2. If GitHub asks, click **I understand my workflows, go ahead and enable them**.
3. In the left list, click **Flux daily papers**, then **Run workflow**, then the green **Run workflow** button.
4. Wait about a minute. A green tick means it worked. A red cross means it failed; click the run to see the log, which says what went wrong.
5. If notifications are set up, your phone gets a message.
6. Open `https://YOUR-USERNAME.github.io/flux/` in your phone's browser.

### Step 9: Install Flux on your phone

- **Android (Chrome):** open the app address, tap the **⋮** menu, then **Install app** (on some phones it says **Add to Home screen**).
- **iPhone (Safari):** open the app address, tap **Share** (the square with an up arrow), then **Add to Home Screen**.

Flux now opens from its own icon in a full-screen window. It also works offline with the last papers it loaded.

---

## Daily use

- Each morning at about 06:45 IST the job runs. If arXiv has posted new papers, you get one notification with the number of new papers, your top keyword match and the pick of the day. Tapping it opens Flux.
- arXiv posts new papers Sunday to Thursday nights, US time. So there are **no new papers on Saturday and Sunday mornings in India**; on those days the notification carries only the pick of the day. arXiv also skips some US holidays.
- GitHub sometimes starts scheduled jobs 10–30 minutes late at busy times. That's normal.
- **Today** shows all new papers. Tap a topic tile to filter it, and tap it again to show all.
- **Paper** shows the summary (EN/हिन्दी) or the original abstract, with Read PDF, Save and Share.
- **Search** looks through the last 1, 7 or 30 days of your feed. A link at the bottom searches all of arXiv.
- **Library** keeps your saved papers and reading stats on your phone only.

## Changing things later

- **Topics, keywords, authors:** edit `config.json` on GitHub. The next run uses them.
- **Pick of the day:** edit `picks.json`. Each entry needs only the arXiv ID; the title and abstract are fetched from arXiv. Add `"on": "MM-DD"` to show a paper on a particular date every year.
- **Run it now:** Actions tab → Flux daily papers → Run workflow.
- **Pause it:** Actions tab → Flux daily papers → **⋯** → Disable workflow.

## Testing on your own computer (optional)

You need Python 3.9 or newer. In a terminal, inside the `flux` folder, run:

```
python scripts/flux_daily.py --fixtures tests/fixtures --no-notify --no-summaries
python -m http.server 8000 --directory docs
```

Then open http://localhost:8000 in a browser. The fixture papers are made-up samples with IDs like `0000.00001`. Delete `docs/data/` before uploading so the real data starts fresh.

Without `--fixtures`, the script fetches real papers from arXiv.

## Notes

- The arXiv papers and abstracts belong to their authors. Flux only links to arXiv and shows the abstracts that arXiv's own feeds provide. Thank you to arXiv for use of its open access interoperability.
- AI summaries can contain mistakes. The app labels them and always lets you switch to the original abstract.
- On public repositories, GitHub turns off scheduled jobs after 60 days with no commits. Flux commits new data on most days, so this shouldn't happen. If it does, re-enable the job in the Actions tab.
