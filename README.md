# CCASS-Plotter
#### Introduction
This is a project to visualize CCASS Shareholding data from HKEX. The data is updated daily at T+1 and 1-year rolling data is available.<br>
There are two main parts:
1. Scraping
2. Web application
    - Link: http://54.202.152.22:8000/

## Scraping
To scrape data from https://www3.hkexnews.hk/sdw/search/searchsdw.aspx<br>
In order to reduce data size, I only scrape records with shareholdiing > 0.1% for first 2000 stocks (refer to config.py).<br>
#### Tools used:
- Selenium<br>
For switching dates and stock code
- BeautifulSoup<br>
For parsing the data table
- SQLite3 (A simple database to store the shareholding data)
    - Table 1: CCASS Shareholding by date and stock code
    - Table 2: Stock List by date
#### How to run:
1. Download chromedriver and save it to project folder<br>
Please check your chrome version (Settings -> About Chrome) and look for the corresponding driver
https://chromedriver.chromium.org/downloads
2. Run scraper.py<br>
Multithreading is available at date level. For each day, there are >5000 stocks to scrape.
```
def main():
    # This is single thread
    scrape_task(0, DATE_RANGE_LIST[::-1][0])
    
    # This is multi thread
    # executor = ThreadPoolExecutor(max_workers=12)
    # jobs = [executor.submit(scrape_task, i, DATE_RANGE_LIST[::-1][i]) for i in range(0, len(DATE_RANGE_LIST))]
```

## Web application
A simple interactive dashboard that has two tabs:
- CCASS Shareholding trend visualization
- Transaction finder based on change in CCASS shareholding
#### Tools used:
- Dash<br>
A python library which provides an integrated back and fron end framework for rapid web app development, built on top of plotly.js and react.js.<br>
Dash is selected because it is my first time trying a python based front end.
- Waitress<br>
A production-quality pure-Python WSGI server.
#### How to run:
1. Set up .env file (DEV or PROD)
```
BASE_ENV=DEV
```
2. Run app.py<br>
Dash development server will be used if BASE_ENV is DEV, which supports features like hot-reloading, error messages etc.<br>
Waitress server will be used if BASE_ENV is PROD, which gives much better performance than development server.
```
if __name__ == "__main__":
    env = load_base_env()
    if env == 'DEV':
        app.run_server(host=HOST, port=PORT, debug=True)
    elif env == 'PROD':
        serve(app.server, host=HOST, port=PORT,)
```
#### How to host:
1. Get a AWS Free tier (t2.micro) Instance
2. Setting the inbound rule on AWS management console and open firewall in the instance
    - Allow traffic from 0.0.0.0/0 for tcp port 8000, 443, 80 and rdp port 3389
3. Setting up the local environment in the instance
    - Anaconda
    - Chrome
    - Git
4. Schedule daily restart / kill job for the web app
    - Start at 0005 and Kill at 1155
