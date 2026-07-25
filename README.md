# Headcounts

A Flask web app for browsing course enrollment data at [Minnesota State University Moorhead](http://www.mnstate.edu). Data is scraped from the public MinnState course search tool and served as a searchable, filterable table with download support and an analytics dashboard.

---

## Features

- Search and filter courses by subject, college, term, LASC area, writing intensive, and more
- Responsive, modern UI for desktop and mobile
- Download full results as CSV or Excel, or export the current filtered view as CSV
- Summary statistics: student credit hours, tuition revenue, empty seats, and more
- Analytics dashboard with historical enrollment trends by term
- Deployed with Docker (gunicorn, Traefik-managed in production)
- Data is **not real-time** — scraped from the [public MinnState course search tool](https://www.minnstate.edu/courses/)
- Powered by [Flask](http://flask.pocoo.org/), [Polars](https://pola.rs/), [DataTables](https://datatables.net/), and [Chart.js](https://www.chartjs.org/)

---

## Updating for a New Semester

Run the scraper for the new term code, then feed the output to the updater:

```bash
docker compose exec headcounts python scrape.py --year-term <term-code>
docker compose exec headcounts python update_data_table.py <path-to-scraped-csv>
```

`update_data_table.py` will merge the new data into the main dataset and add the term to `config_terms.py` automatically. Afterward, update `DEFAULT_TERM` in `config.py` to point to the new term.

See `Developer-Reference.md` for the full workflow and file-by-file details.

---

## Credits

- UI icons: [Font Awesome](https://fontawesome.com/)
- Fonts: [Google Fonts](https://fonts.google.com/) (Public Sans, IBM Plex Sans)
- Original version: [Matthew Craig](https://github.com/mwcraig/)
- Backend and Polars migration: [Juan Cabanela](https://web.mnstate.edu/cabanela/)
- Front-end redesign: [Natoli Tesgera](https://github.com/Natoli74)
- Docker deployment, infrastructure, and data pipeline: [Laween Al-Sulaivany](https://github.com/laween-alsulaivany)
