<img src="/assets/full.png" alt="team spiral racing logo" width="400"/>
<a href="https://github.com/Team-Spiral-Racing/data-service/releases"><img src="https://img.shields.io/github/v/release/Team-Spiral-Racing/data-service?color=f56827"></a>
<a href="https://github.com/Team-Spiral-Racing/data-service/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Team-Spiral-Racing/data-service"></a>

# Team Spiral Racing Data Service
The Team Spiral Racing Data Service is run serverlessly on CRON. It gathers data from various sources and saves it to the TSR MongoDB instance. CRON jobs are run via [cron-job.org](http://cron-job.org/) and are scheduled to run every at certain intervals. Requests are authenticated with a Bearer token to ensure there are no unauthorized requests.

## Statuses

#### TSR YouTube
- Interval: 6 hours (+ 15 minute offset)
- Status: ![TSR YouTube status](https://api.cron-job.org/jobs/6348392/f47775860db9872a/status-1.svg)

#### TSR Blog
- Interval: 1 hours (+ 15 minute offset)
- Status:  ![TSR Blog status](https://api.cron-job.org/jobs/6380415/8e63cd423f631df3/status-1.svg)

## Running Locally
1. Clone the repository.
2. Install dependencies via `pip install -r requirements.txt`.
3. Create a `.env` following the `sample.env` format.
4. Run app via `flask --app server run`.

## License
This project is licensed under the GNU General Public License. See `LICENSE` for more information.
