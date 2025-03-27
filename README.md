# TopTenPonyVideos

A dynamic Flask-based voting platform dedicated to ranking and celebrating pony-related videos from multiple online platforms.

## Features

- User login via Discord OAuth
- Vote on your favorite pony videos (up to 10 videos per voting period)
- Different voting periods with customizable dates
- Admin dashboard for managing voting periods, playlists, and users
- Support for videos from YouTube, Dailymotion, Vimeo, PonyTube, Bilibili, and more
- Historical playlist import from Google Spreadsheets
- Weighted and non-weighted voting options
- Export results in different formats

## System Requirements

- Python 3.8 or higher
- PostgreSQL database
- Linux environment

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/toptenponyvideos.git
cd toptenponyvideos
```

### 2. Set Up a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install flask flask-login flask-sqlalchemy flask-wtf email-validator gunicorn psycopg2-binary requests sqlalchemy google-api-python-client gspread oauth2client oauthlib yt-dlp
```

### 4. Set Up Environment Variables

Duplicate `.env.example` file in the root directory.

```bash
cp .env.example .env
```

Then edit the file with your specific configuration details.

### 5. Set Up the PostgreSQL Database

Install PostgreSQL if not already installed:

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

Create a database and user:

```bash
sudo -u postgres psql

# Inside PostgreSQL command prompt
CREATE DATABASE toptenponyvideos;
CREATE USER toptenuser WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE toptenponyvideos TO toptenuser;
\q
```

Update the `DATABASE_URL` in your `.env` file to match these credentials.

### 6. Initialize the Database

```bash
python reset_database.py
```

This will create all necessary tables and set up an initial admin user.

## Running the Application

### Development Mode

```bash
python main.py
```

This will start the development server on http://0.0.0.0:5000.

### Production Mode

For production deployments, use Gunicorn:

```bash
gunicorn --bind 0.0.0.0:5000 --workers 3 main:app
```

It's recommended to set up Caddy as a reverse proxy for production deployments.

## Setting Up Caddy (Production)

Install Caddy:

```bash
sudo apt update
sudo apt install caddy
```

Edit the Caddyfile

```bash
sudo nano /etc/caddy/Caddyfile
```

Remove everything inside of the Caddyfile

Then enter the following config:
```caddy
https://yourdomain.com {
    reverse_proxy localhost:5000
}
```

Enable the site and restart Nginx:

```bash
sudo systemctl restart caddy
```
Caddy will automatically handle SSL certificates for you!

## Setting Up a Systemd Service

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/toptenponyvideos.service
```

Add the following configuration:

```ini
[Unit]
Description=TopTenPonyVideos Gunicorn Service
After=network.target

[Service]
User=your_username
Group=your_username
WorkingDirectory=/path/to/toptenponyvideos
Environment="PATH=/path/to/toptenponyvideos/venv/bin"
EnvironmentFile=/path/to/toptenponyvideos/.env
ExecStart=/path/to/toptenponyvideos/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 3 main:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable toptenponyvideos
sudo systemctl start toptenponyvideos
sudo systemctl status toptenponyvideos
```

## Configuration Options

Key configuration settings can be found in `config.py`. You can customize:

- Site name and color scheme
- Admin Discord IDs for automatic admin privileges
- Historical playlist settings
- Voting period behavior

## Admin Access

The initial admin user is created based on the `TEST_USER` setting in `config.py`. For production, set `TEST_MODE` to `False` and use Discord OAuth with admin Discord IDs.

## License

This project is licensed under the MIT License - see the LICENSE file for details.