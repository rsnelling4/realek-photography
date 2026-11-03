# Client preview tool

Turns a folder of unedited photos into a draft 25-40 photo preview. Currently built:
the local filter and AI selection, with a report page for judging the picks.

    pip install -r tools/preview/requirements.txt
    python tools/preview/draft.py "path/to/shoot" --no-ai    # local only, nothing is sent
    python tools/preview/draft.py "path/to/shoot"            # sends small numbered copies to Claude

The AI step needs `ANTHROPIC_API_KEY` in the repo's `.env` file. Reports are written to
`tools/preview/_work/<shoot>/report.html`, which git ignores because they contain client photos.

Originals are only read. Tests run offline: `python tools/preview/tests/test_pipeline.py`
