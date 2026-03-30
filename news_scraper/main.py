import news_scraper
from datetime import datetime, time, timedelta

if __name__ == '__main__':
    news_source = input('Enter the news source: ')

    last_three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d') 
    week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    month = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d') 

    time_periods = {} 
    time_periods[1] = last_three_days
    time_periods[2] = week
    time_periods[3] = month

    print("Select the time period: ")
    print("1. Last Three Days")
    print("2. Week")
    print("3. Month")
    date = time_periods[int(input())]

    news_scraper.get_news(news_source, date)
