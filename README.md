# Headcounts

A simple web app for displaying (reasonably) up-to-date enrollments in courses at [Minnesota State University Moorhead](http://www.mnstate.edu) for the current semester.

**Live demo:** [http://ash.mnstate.edu/](http://ash.mnstate.edu/)  

---

## Features

- Search and filter courses by subject, college, term, LASC area, writing intensive, and more
- Responsive, modern UI for desktop
- Download full results as CSV or Excel, or export the current filtered view as CSV
- Summary statistics: credit hours, tuition revenue, empty seats, and more
- Analytics dashboard with historical enrollment trends by term
- Disclaimer: Data is **not real-time**; it is scraped from the [public-facing MinnState-maintained course search tool](https://www.minnstate.edu/courses/).
- Powered by:
  - [Flask](http://flask.pocoo.org/) (web framework)
  - [Polars](https://pola.rs/) (data processing)
  - [DataTables](https://datatables.net/)
  - [Chart.js](https://www.chartjs.org/)

---

## Updating for a New Semester

When data for a new semesters' courses becomes available, the following steps
are needed to update the app:

1. Edit the `DEFAULT_TERM` variable in `config.py` to be a tuple with the
    new term code and name (e.g., `('20265', 'Spring 2026')`)
2. Edit the `SEMESTERS_LIST` list in `config_terms.py` to add a new tuple
    with the new term code and name (e.g., `('20265', 'Spring 2026')`)
    to the list.
3. Edit `daily_update_script.sh` to change the `year_terms` variable to
    a SPACE-delimited list of terms to scrape.
---

## Credits

- UI icons: [Font Awesome](https://fontawesome.com/)
- Fonts: [Google Fonts](https://fonts.google.com/) (Montserrat, Tinos)
- Original version developed by: [Matthew Craig](https://github.com/mwcraig/)
- Backend upgraded to use Polars and currently maintained by: [Juan Cabanela](https://web.mnstate.edu/cabanela/)
- Front-end redesign: [Natoli Tesgera](https://github.com/Natoli74), [Laween Al-Sulaivany](https://github.com/laween-alsulaivany)

