# video-games
Video games stuff

## Structure

```
nba2k/
├── NBA_2K26_Best_Shots.md
├── NBA_2K26_Center_Builds.md
├── NBA_2K26_Competitive_Builds.md
├── NBA_2K26_Moves_Controls.md
└── ratings/
    ├── config.json          # Grade scale, positions, weights, player list
    ├── ratings.json         # Local ratings (manual entry)
    ├── rate.py              # CLI output (reads local ratings.json)
    ├── pull_ratings.py      # Pulls from Google Sheets, generates data.json
    ├── generate_local.py    # Generates data.json from local ratings.json
    ├── requirements.txt
    └── docs/
        ├── index.html       # GitHub Pages site
        └── data.json        # Generated ratings data for the site
```

## NBA 2K Ratings Setup

### 1. Create the Google Form

Create a Google Form with these fields:
- **Voter Name** (short text)
- **Player** (dropdown — list all players from config.json)
- **Position** (dropdown — PG, SG, SF, PF, C)
- **Category grades** (one dropdown per category, options: S, A, B, C, D, F)

> Note: Since categories differ by position, you may want one form section per position,
> or create separate forms per position. The simplest approach is one form with all possible
> categories and voters just fill in the ones relevant to the position they selected.

### 2. Link Form to Google Sheets

The form auto-creates a response spreadsheet. Note the Sheet ID from the URL:
```
https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
```

### 3. Set up Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or reuse one)
3. Enable the Google Sheets API
4. Create a Service Account → download the JSON key
5. Share the response spreadsheet with the service account email

### 4. Configure

For local use, place the credentials JSON as `nba2k/ratings/credentials.json` and add `sheet_id` to config.json.

For GitHub Actions, add these repo secrets:
- `GOOGLE_CREDENTIALS` — the full JSON content of the service account key
- `SHEET_ID` — the spreadsheet ID

### 5. GitHub Pages

Enable GitHub Pages in repo settings → Source: `Deploy from a branch` → Branch: `main`, folder: `/nba2k/ratings/docs`.

### 6. Embed the Form

Add `"form_url"` to the config section of data.json, or update pull_ratings.py to include it. Use the form's embed URL (Form → Send → Embed → copy the src URL).

### Running Locally

```bash
cd nba2k/ratings

# Generate site data from local ratings.json (no Google needed)
python generate_local.py

# Or pull from Google Sheets
pip install -r requirements.txt
python pull_ratings.py

# View the site
open docs/index.html
```
