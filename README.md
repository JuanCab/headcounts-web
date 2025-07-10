# headcounts

A simple web app for displaying (reasonably) up-to-date enrollments in courses at [Minnesota State University Moorhead](http://www.mnstate.edu) for the current semester.

**Live demo:** [http://headcounts.herokuapp.com](http://headcounts.herokuapp.com)  

---

## Features

- Search and filter courses by subject, college, term, LASC area, writing intensive, and more
- Responsive, modern UI for desktop and mobile
- Download results as CSV or Excel files
- Summary statistics: credit hours, tuition revenue, empty seats, and more
- Disclaimer: Data is **not real-time**; it is scraped from the [public-facing MinnState-maintained course search tool](https://www.minnstate.edu/courses/).
- Powered by:
  - [Flask](http://flask.pocoo.org/) (web framework)
  - [Bootstrap](https://getbootstrap.com/) (styling)
  - [Polars](https://pola.rs/) (data processing)
  - Hosted on [Heroku](https://www.heroku.com/)

---

## Credits

- **Original version developed by:** [Matthew Craig](https://github.com/mwcraig/)
- **Backend upgraded to use Polars and currently maintained by:** [Juan Cabanela](https://web.mnstate.edu/cabanela/)
- **GUI redesign and front-end development:** [Natoli Tesgera](https://github.com/Natoli74)  

---


## Acknowledgments

- Data processed with [Polars](https://pola.rs/)
- Hosted by [Heroku](https://www.heroku.com/)
- Inspired by the needs of MSUM faculty and staff
- Thanks to [Kenneth Reitz](https://github.com/kennethreitz/) for the [conda buildpack for Heroku](https://github.com/kennethreitz/conda-buildpack)
