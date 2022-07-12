# CCASS-Plotter
#### Introduction
This is a project to visualize CCASS Shareholding data from HKEX. The data is updated daily at T+1 and 1-year rolling data is available.<br>
There are two main parts:
1. Scraping
2. Web application
	- SQLite
	Link: http://54.202.152.22:8000/ <br>
	It is hosted in an Amazon EC2 Free Tier instance with limited cpu resources and 1GB RAM. So do expect a bit of slowness, compared to a local host.
	There may be downtime between 01:00 HKT and 01:30 HKT due to a daily restart
	- QuestDB (Productionalization)
	Link: http://210.6.212.233:8000/ <br>
	It is hosted in a machine with 16GB RAM and 6 cores.<br>
	Also, QuestDB is a time-series database which is much more efficient in storing / querying time series data.<br>
	By comparing the two site, the one using QuestDB is return data more swiftly due to faster query.
    
## Scraping
To scrape data from https://www3.hkexnews.hk/sdw/search/searchsdw.aspx
#### Tools used:
- Selenium<br>
For switching dates and stock code
- BeautifulSoup<br>
For parsing the data table
- SQLite3 (A simple database to store the shareholding data)
    - Table 1: CCASS Shareholding by date and stock code
    - Table 2: Stock List by date
- QuestDB (A time series database)
	- Table 1: CCASS Shareholding by date and stock code
	- Table 2: Stock List by date
#### How to run:
0. QuestDB setup (Skip this if you are not using QuestDB)
Please pull the latest QuestDB docker image from and follow the instruction here: https://hub.docker.com/r/questdb/questdb. <br>
I ran this in order to persist the data:
```
$ docker run -p 9000:9000  \
      -p 8812:8812 \
      -v local/dir:/root/.questdb/db \
      questdb/questdb
```
1. Set up .env file
    - DB: QUEST|SQLITE
```
DB=QUEST
```
2. Download chromedriver and save it to project folder<br>
Please check your chrome version (Settings -> About Chrome) and look for the corresponding driver
https://chromedriver.chromium.org/downloads
3. Run scraper.py<br>
Multithreading is available at date level. For each day, there are >5000 stocks to scrape.
```
def main():
    # This is single thread
    scrape_task(0, DATE_RANGE_LIST[::-1][0])
    
    # This is multi thread
    # executor = ThreadPoolExecutor(max_workers=12)
    # jobs = [executor.submit(scrape_task, i, DATE_RANGE_LIST[::-1][i]) for i in range(0, len(DATE_RANGE_LIST))]
```
#### Data Scraped and Stored for the web application:
I only scrape records with shareholdiing > 0.1% for first 2000 stocks (refer to config.py).<br>
Therefore in total 16.67M rows for CCASS shareholding dy date and stock code. In terms of storage space, it takes ~3.4GB for SQLite and 4.3GB for QuestDB.
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
- python-dotenv<br>
To load the .env file and get the environment type (DEV|PROD)
#### How to run:
0. QuestDB setup (Skip this if you are not using QuestDB)
Please pull the latest QuestDB docker image from and follow the instruction here: https://hub.docker.com/r/questdb/questdb. <br>
I ran this in order to persist the data:
```
$ docker run -p 9000:9000  \
      -p 8812:8812 \
      -v local/dir:/root/.questdb/db \
      questdb/questdb
```
1. Set up .env file
    - BASE_ENV: DEV|PROD
    - DB: QUEST|SQLITE
```
BASE_ENV=DEV
DB=QUEST
```
2. Run scrape.py so that table exists in the DB.
As discussed above, the data is in the size of 3-4GB so it is not uploaded.<br>
3. Run app.py
Dash development server will be used if BASE_ENV is DEV, which supports features like hot-reloading, error messages etc.<br>
Waitress server will be used if BASE_ENV is PROD, which gives much better performance than development server.
```
if __name__ == "__main__":
    if env == 'DEV':
        app.run_server(host=HOST, port=PORT, debug=True)
    elif env == 'PROD':
        serve(app.server, host=HOST, port=PORT,)
```
#### How to host:
1. Get a AWS Free tier (t2.micro) Instance
    - It works for SQLite only
	- QuestDB needs at least 2-3 GB Memory from my experience so I am using a local machine to host the Productionized Appliaction
2. Setting the inbound rule and open firewall in the instance
    - Allow traffic from 0.0.0.0/0 for tcp port 8000, 443, 80 and rdp port 3389
	- You may also need to open port 9000 / 8812 if you want to interact with QuestDB
3. Setting up the local environment in the instance
    - Anaconda
    - Chrome
    - Git
	- Docker (QuestDB only)
4. Schedule daily restart / kill job for the web app / container
    - Start at 0100 and Kill at 0059