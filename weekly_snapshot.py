name: Weekly Snapshot

on:
  workflow_dispatch:
  schedule:
    # Fridays during Daylight Time (EDT = UTC-4): 13:00 UTC == 09:00 ET
    - cron: "0 9 * * FRI"
    # Fridays during Standard Time (EST = UTC-5): 14:00 UTC == 09:00 ET
    - cron: "0 14 * * FRI"

jobs:
  run:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      # Gate: only continue if it's Friday 09:00 in America/New_York
      - name: Ensure it's 09:00 Friday in New York
        run: |
          ny_wday=$(TZ=America/New_York date +%u) # 5 = Friday
          ny_hour=$(TZ=America/New_York date +%H) # 09 = 9am
          echo "NY weekday=$ny_wday hour=$ny_hour"
          if [ "$ny_wday" != "5" ] || [ "$ny_hour" != "09" ]; then
            echo "Not 09:00 Friday in New York—exiting."
            exit 0
          fi

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then
            python -m pip install -r requirements.txt
          else
            python -m pip install openai PyGithub requests python-dotenv
          fi

      - name: Run weekly snapshot
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python weekly_snapshot.py

      - name: Upload report artifact (optional)
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: weekly-snapshot
          path: |
            report.html
            output/**
          if-no-files-found: ignore
